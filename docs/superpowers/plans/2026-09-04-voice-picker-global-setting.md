# Voice Picker (Global Accessibility Setting) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator pick which installed browser voice the Listen feature (`useSpeech`/`ListenButton`) speaks with everywhere it appears, persisted once as a global per-user setting rather than per field or per Space.

**Architecture:** Extend the existing schemaless `accessibility_settings` JSON blob (already stored via the generic `user_settings` key/value table — no migration needed) with a third field, `voice_uri`. The Controls → Accessibility page gets a new "Voice" row (native `<select>`, grouped by language via `Intl.DisplayNames`, plus a preview control that reuses `ListenButton` unchanged). `useSpeech` resolves the `SpeechSynthesisVoice` to speak with from either an explicit override (used only by the preview control, so it can audition the currently-selected option before/without depending on the save completing) or the persisted global setting (used by every other call site, unchanged).

**Tech Stack:** FastAPI + Pydantic (backend), Next.js/React + TypeScript + Vitest/RTL (frontend), browser Web Speech API (`SpeechSynthesis`, `SpeechSynthesisVoice`), `Intl.DisplayNames` (stdlib, no new dependency).

**Spec:** This plan implements the voice-picker feature discussed and mocked in the current conversation (Controls → Accessibility section design canvas, approved by the user) and follows on from ADR-0059 (`docs/adr/0059-listen-button-uses-browser-tts-not-fish-audio.md`) and the shipped `useSpeech`/`ListenButton` feature (`docs/superpowers/plans/2026-09-04-listen-button.md`).

## Global Constraints

- No database migration: `accessibility_settings` is a JSON blob under the existing generic `user_settings(chat_id, key, value)` table (`src/database.py`) — old stored rows simply lack `voice_uri`, and `.get("voice_uri", None)` treats that as "no preference," so nothing needs backfilling.
- Validation has exactly one legacy-compatible exception to an otherwise whole-object fallback: `_normalize_accessibility_settings` falls back to defaults entirely if `visual_motion`/`haptic_motion` are missing/wrong-typed, OR if `voice_uri` is *present but the wrong type* (e.g. a number). A **missing** `voice_uri` key — the only shape a pre-this-feature stored row can have — is not an error; it normalizes to `None`, same as an explicit `null`. Don't special-case anything beyond that one exception.
- `voice_uri` is a **required key, nullable value** in the PUT body (`str | None`, no Pydantic default), bounded with `max_length=512` — matches the existing all-fields-required behavior already covered by `test_accessibility_settings_get_put_and_validate`'s 422 case. (Considered making it optional for zero-downtime rollout safety; rejected — this is a single-operator dashboard with one atomic Next.js build, not a fleet with staggered deploys, so the existing all-fields-required contract already used for the other two fields is the right one to extend rather than carve an exception into.)
- Frontend: match `web/components/feed/submit-url-form.tsx`'s exact `<select>` classes (`h-10 rounded-md border border-line bg-canvas px-3 text-sm text-ink outline-none transition-ui focus:border-signal`) — no custom chevron/appearance override, native OS select chrome throughout, consistent with every other select in the product.
- The preview control reuses the existing `ListenButton` component as-is (icon-swap Volume2 ⇄ Square, same classes) rather than a new bespoke control — this is a deliberate, user-approved reuse, not a shortcut to skip.
- `useAccessibilitySettings()`'s module-level `stored`/`loading` state is a singleton across a test file — any test file that renders a hook depending on it needs `resetAccessibilitySettingsForTests()` (or `vi.resetModules()`) plus a `fetch` stub in `beforeEach`, mirroring `web/lib/hooks/useAccessibilitySettings.test.ts`.
- `useSpeech` resolves the persisted voice via `speechSynthesis.getVoices()` at the moment `toggle()` is called, not via its own `voiceschanged` subscription — a deliberate scope cut, not an oversight: sharing a listener/cache across every `ListenButton` instance on a page adds real architectural surface (a second module-scoped singleton alongside `activeClear`) for a narrow edge case (voices not yet loaded *and* a non-default preference already set) that degrades softly today (falls back to the browser's default voice for that one click, matching ADR-0059's existing tolerance for browser-TTS quirks). Revisit only if this proves to be a real complaint, not preemptively.
- No MSW mock handler exists for `/api/controls/accessibility-settings` today (confirmed: `web/lib/mocks/handlers.ts` has no entry for it) — the two existing fields already silently fail and fall back to hardcoded defaults in `NEXT_PUBLIC_API_MOCK=1` mode. `voice_uri` inherits the same pre-existing gap; adding a mock handler for this endpoint is a separate, pre-existing-debt task, out of scope here since this plan doesn't regress anything mock mode already didn't support.
- Run backend tests with `python -m pytest <path> -q` from the repo root (never via `rtk`, per `.claude/rules/rtk-tests.md`). Run all frontend commands (`npx vitest run <path>`, `git add <path>`) from inside `web/`, with paths relative to `web/` (no leading `web/` segment) — matches how this repo's own root `CLAUDE.md` documents running the dashboard (`cd web && npm test`), and how every command in this plan is written.

---

### Task 1: Backend — persist `voice_uri` in the accessibility-settings store

**Files:**
- Modify: `src/database.py:1816-1848`
- Test: `tests/test_database.py:1696-1713`

**Interfaces:**
- Consumes: existing `get_user_setting(chat_id, key)` / `set_user_setting(chat_id, key, value)` (unchanged, `src/database.py:1758-1776`).
- Produces: `get_accessibility_settings(chat_id: int) -> dict[str, bool | str | None]` and `set_accessibility_settings(chat_id: int, *, visual_motion: bool, haptic_motion: bool, voice_uri: str | None) -> dict[str, bool | str | None]` — both now return/accept a `voice_uri` key. Consumed by Task 2.

- [ ] **Step 1: Write the failing test**

Replace the existing roundtrip test in `tests/test_database.py` (lines 1696-1713) with:

```python
@pytest.mark.asyncio
async def test_accessibility_settings_roundtrip_and_normalizes_invalid_values(
    tmp_path, monkeypatch
):
    from src import database

    db_path = tmp_path / "accessibility-settings.db"
    monkeypatch.setattr(database.settings, "DB_PATH", str(db_path))
    await database.init_db()
    defaults = {"visual_motion": True, "haptic_motion": True, "voice_uri": None}
    assert await database.get_accessibility_settings(42) == defaults
    saved = await database.set_accessibility_settings(
        42, visual_motion=False, haptic_motion=True, voice_uri="Microsoft Zira Desktop"
    )
    assert saved == {
        "visual_motion": False,
        "haptic_motion": True,
        "voice_uri": "Microsoft Zira Desktop",
    }
    assert await database.get_accessibility_settings(42) == saved
    for malformed in (
        '{"visual_motion":false}',
        '{"visual_motion":"no"}',
        "{not-json",
        '{"visual_motion":true,"haptic_motion":true,"voice_uri":123}',
    ):
        await database.set_user_setting(42, "dashboard_accessibility_settings", malformed)
        assert await database.get_accessibility_settings(42) == defaults
    # A row saved before this feature shipped has no voice_uri key at all —
    # must be treated as "no preference", not fall back to defaults wholesale.
    await database.set_user_setting(
        42, "dashboard_accessibility_settings", '{"visual_motion":false,"haptic_motion":false}'
    )
    assert await database.get_accessibility_settings(42) == {
        "visual_motion": False,
        "haptic_motion": False,
        "voice_uri": None,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_database.py::test_accessibility_settings_roundtrip_and_normalizes_invalid_values -q`
Expected: FAIL — `set_accessibility_settings() got an unexpected keyword argument 'voice_uri'`.

- [ ] **Step 3: Write minimal implementation**

Replace lines 1816-1848 of `src/database.py` with:

```python
_ACCESSIBILITY_SETTINGS_KEY = "dashboard_accessibility_settings"
_DEFAULT_ACCESSIBILITY_SETTINGS: dict[str, bool | str | None] = {
    "visual_motion": True,
    "haptic_motion": True,
    "voice_uri": None,
}


def _normalize_accessibility_settings(value: object) -> dict[str, bool | str | None]:
    if not isinstance(value, dict):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    visual_motion = value.get("visual_motion")
    haptic_motion = value.get("haptic_motion")
    voice_uri = value.get("voice_uri", None)
    if not isinstance(visual_motion, bool) or not isinstance(haptic_motion, bool):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    if voice_uri is not None and not isinstance(voice_uri, str):
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    return {
        "visual_motion": visual_motion,
        "haptic_motion": haptic_motion,
        "voice_uri": voice_uri,
    }


async def get_accessibility_settings(chat_id: int) -> dict[str, bool | str | None]:
    value = await get_user_setting(chat_id, _ACCESSIBILITY_SETTINGS_KEY)
    if value is None:
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return dict(_DEFAULT_ACCESSIBILITY_SETTINGS)
    return _normalize_accessibility_settings(parsed)


# voice_uri's length isn't re-validated here — this module trusts its only
# caller (the /api/controls PUT route, Task 2) to have already applied
# AccessibilitySettingsIn's max_length=512 bound. Route any other future
# write of this setting through that same API rather than duplicating the
# bound at this layer.
async def set_accessibility_settings(
    chat_id: int, *, visual_motion: bool, haptic_motion: bool, voice_uri: str | None
) -> dict[str, bool | str | None]:
    settings_value: dict[str, bool | str | None] = {
        "visual_motion": visual_motion,
        "haptic_motion": haptic_motion,
        "voice_uri": voice_uri,
    }
    await set_user_setting(
        chat_id, _ACCESSIBILITY_SETTINGS_KEY, json.dumps(settings_value, separators=(",", ":"))
    )
    return settings_value
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_database.py::test_accessibility_settings_roundtrip_and_normalizes_invalid_values -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/database.py tests/test_database.py
git commit -m "feat: persist voice_uri in accessibility settings"
```

---

### Task 2: Backend — expose `voice_uri` on the Controls API

**Files:**
- Modify: `src/api/controls.py:51-53,206-221`
- Test: `tests/test_controls_validation.py:52-61,98-110`

**Interfaces:**
- Consumes: `database.get_accessibility_settings` / `database.set_accessibility_settings` from Task 1.
- Produces: `GET/PUT /api/controls/accessibility-settings` now round-trip `{visual_motion, haptic_motion, voice_uri}`. Consumed by Task 3's frontend type and Task 7's UI.

- [ ] **Step 1: Write the failing test**

Replace both existing tests in `tests/test_controls_validation.py` (lines 52-61 and 98-110):

```python
def test_accessibility_settings_endpoints_roundtrip(controls_client: TestClient) -> None:
    endpoint = "/api/controls/accessibility-settings"
    assert controls_client.get(endpoint).json() == {
        "visual_motion": True,
        "haptic_motion": True,
        "voice_uri": None,
    }
    saved = controls_client.put(
        endpoint,
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": "Daniel"},
    )
    assert saved.json() == {
        "visual_motion": False,
        "haptic_motion": True,
        "voice_uri": "Daniel",
    }
```

```python
def test_accessibility_settings_get_put_and_validate(controls_client: TestClient) -> None:
    response = controls_client.get("/api/controls/accessibility-settings")
    assert response.status_code == 200
    assert response.json() == {
        "visual_motion": True,
        "haptic_motion": True,
        "voice_uri": None,
    }
    response = controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": None},
    )
    assert response.status_code == 200
    assert controls_client.get("/api/controls/accessibility-settings").json() == response.json()
    assert controls_client.put(
        "/api/controls/accessibility-settings", json={"visual_motion": False}
    ).status_code == 422
    assert controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True},
    ).status_code == 422
    assert controls_client.put(
        "/api/controls/accessibility-settings",
        json={"visual_motion": False, "haptic_motion": True, "voice_uri": "x" * 513},
    ).status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_controls_validation.py -k accessibility_settings -q`
Expected: FAIL — responses are missing the `voice_uri` key, and the added missing-`voice_uri` PUT no longer 422s (since the field doesn't exist on the model yet, extra/missing keys are silently ignored).

- [ ] **Step 3: Write minimal implementation**

In `src/api/controls.py`, replace the `AccessibilitySettingsIn` model (lines 51-53). `Field`/`max_length` bound the value since it's persisted to SQLite and echoed back verbatim — a real browser voice name/URI is at most a couple hundred characters, so 512 is generous headroom, not a tight fit:

```python
class AccessibilitySettingsIn(BaseModel):
    visual_motion: bool
    haptic_motion: bool
    voice_uri: str | None = Field(max_length=512)
```

Replace the two route handlers (lines 206-221):

```python
@controls_router.get("/accessibility-settings")
async def get_accessibility_settings(request: Request) -> dict[str, bool | str | None]:
    chat_id: int = request.state.user["id"]
    return await database.get_accessibility_settings(chat_id)


@controls_router.put("/accessibility-settings")
async def update_accessibility_settings(
    body: AccessibilitySettingsIn, request: Request
) -> dict[str, bool | str | None]:
    chat_id: int = request.state.user["id"]
    return await database.set_accessibility_settings(
        chat_id,
        visual_motion=body.visual_motion,
        haptic_motion=body.haptic_motion,
        voice_uri=body.voice_uri,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_controls_validation.py -k accessibility_settings -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/controls.py tests/test_controls_validation.py
git commit -m "feat: expose voice_uri on the accessibility-settings API"
```

---

### Task 3: Frontend — add `voice_uri` to the shared `AccessibilitySettings` type

**Files:**
- Modify: `web/lib/hooks/useAccessibilitySettings.ts`
- Test: `web/lib/hooks/useAccessibilitySettings.test.ts`

**Interfaces:**
- Produces: `AccessibilitySettings` now has `voice_uri: string | null`. `useAccessibilitySettings()`'s returned state includes it (`null` until loaded or saved). Consumed by Task 5 (`useSpeech`) and Task 7 (`AccessibilitySection`).
- Produces: `publishAccessibilitySettingsFromExternalWrite(value: AccessibilitySettings): void` — for a call site with its own independent save flow. Consumed by Task 7.

- [ ] **Step 1: Write the failing test**

Add to `web/lib/hooks/useAccessibilitySettings.test.ts` (new `it` inside the existing `describe` block):

```ts
  it('includes voice_uri in the fallback shape before any load or save', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null })),
    ));
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    expect(result.current).toEqual({
      visual_motion: true,
      haptic_motion: true,
      voice_uri: null,
      loaded: false,
    });
  });

  it('round-trips a saved voice_uri', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: 'Daniel' })),
    ));
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.voice_uri).toBe('Daniel');
  });

  it('saveAccessibilitySetting sends and accepts a string value for voice_uri', async () => {
    // Regression guard: once 'voice_uri' joined keyof AccessibilitySettings,
    // a value param hardcoded to `boolean` would let
    // saveAccessibilitySetting('voice_uri', true) type-check and corrupt the
    // field — this only compiles at all once the signature is generic. Also
    // asserts the actual PUT body, not just the round-tripped response, so a
    // silently-dropped or coerced field would be caught here.
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: 'Daniel' })),
    );
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    await act(async () => {
      await settingsModule.saveAccessibilitySetting('voice_uri', 'Daniel');
    });
    expect(result.current.voice_uri).toBe('Daniel');
    const putCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(JSON.parse(putCall![1].body as string)).toMatchObject({ voice_uri: 'Daniel' });
  });
```

Also replace the two pre-existing tests in this file ("ignores an older overlapping save response" and "does not let a slow initial load overwrite a save that completed first") to include `voice_uri` in every fixture response and every `.toEqual` assertion — this file's own overlapping-save/race-guard logic needs to be proven to carry the new field correctly too, not just the two booleans it was originally written against:

```ts
  it('ignores an older overlapping save response', async () => {
    const first = deferredResponse();
    const second = deferredResponse();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
      })))
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });

    let older!: Promise<void>;
    let newer!: Promise<void>;
    await act(async () => {
      older = settingsModule.saveAccessibilitySetting('visual_motion', false);
      newer = settingsModule.saveAccessibilitySetting('haptic_motion', false);
      second.resolve(new Response(JSON.stringify({
        visual_motion: false,
        haptic_motion: false,
        voice_uri: null,
      })));
      await newer;
      first.resolve(new Response(JSON.stringify({
        visual_motion: false,
        haptic_motion: true,
        voice_uri: null,
      })));
      await older;
    });

    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: false,
      voice_uri: null,
      loaded: true,
    });
  });

  it('does not let a slow initial load overwrite a save that completed first', async () => {
    const load = deferredResponse();
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(load.promise)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ visual_motion: false, haptic_motion: true, voice_uri: null }),
        ),
      );
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await act(async () => {
      await settingsModule.saveAccessibilitySetting('visual_motion', false);
    });
    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: true,
      voice_uri: null,
      loaded: true,
    });

    await act(async () => {
      load.resolve(
        new Response(
          JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null }),
        ),
      );
      await load.promise;
    });

    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: true,
      voice_uri: null,
      loaded: true,
    });
  });
```

Add one more test alongside these — a call site with its own save flow (like `AccessibilitySection` in Task 7) needs a way to publish into the shared store without a slower, independently-triggered `load()` elsewhere clobbering it afterward:

```ts
  it('an external write invalidates a slower in-flight load so it cannot overwrite a fresher value', async () => {
    const load = deferredResponse();
    const fetchMock = vi.fn().mockReturnValueOnce(load.promise);
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    // Simulates AccessibilitySection's own GET/PUT cycle publishing a value
    // it obtained independently, while the shared load() above is still
    // in flight.
    act(() => {
      settingsModule.publishAccessibilitySettingsFromExternalWrite({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: 'Daniel',
      });
    });
    expect(result.current.voice_uri).toBe('Daniel');

    await act(async () => {
      load.resolve(new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
      })));
      await load.promise;
    });

    // The stale load() response must not have clobbered the external write.
    expect(result.current.voice_uri).toBe('Daniel');
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/hooks/useAccessibilitySettings.test.ts`
Expected: FAIL — `result.current` has no `voice_uri` key on every test in the file (including the two pre-existing overlapping-save tests, now updated to expect it), and `publishAccessibilitySettingsFromExternalWrite` doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

In `web/lib/hooks/useAccessibilitySettings.ts`, update the interface and the two hardcoded default objects:

```ts
export interface AccessibilitySettings {
  visual_motion: boolean;
  haptic_motion: boolean;
  voice_uri: string | null;
}
```

Genericize `saveAccessibilitySetting`'s signature — `voice_uri` joining `keyof AccessibilitySettings` means a value param hardcoded to `boolean` would silently let `saveAccessibilitySetting('voice_uri', true)` type-check and corrupt the field:

```ts
export async function saveAccessibilitySetting<K extends keyof AccessibilitySettings>(
  key: K,
  value: AccessibilitySettings[K],
): Promise<void> {
  const generation = ++requestGeneration;
  const previous = stored ?? { visual_motion: true, haptic_motion: true, voice_uri: null };
  const next = { ...previous, [key]: value };
  publishAccessibilitySettings(next);
  try {
    const response = await fetch("/api/controls/accessibility-settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    if (!response.ok)
      throw new Error("Failed to save accessibility settings");
    const saved = (await response.json()) as AccessibilitySettings;
    if (generation === requestGeneration) publishAccessibilitySettings(saved);
  } catch (err) {
    if (generation === requestGeneration) publishAccessibilitySettings(previous);
    throw err;
  }
}
```

In `useAccessibilitySettings`, the returned fallback (line 104):

```ts
  return {
    ...(stored ?? { visual_motion: !reducedMotion, haptic_motion: true, voice_uri: null }),
    loaded: stored !== null,
  };
```

`resetAccessibilitySettingsForTests()` clears `stored`/`loading` but not `requestGeneration` — a stale in-flight promise from a test that ended without awaiting its save could still coincidentally match the counter's value in a later test and publish over it. Bump the counter on reset so any such stale promise's captured generation can never match again:

```ts
export function resetAccessibilitySettingsForTests() {
  stored = null;
  loading = null;
  requestGeneration += 1;
  notify();
}
```

`AccessibilitySection` (Task 7) runs its own independent GET/PUT cycle rather than going through `saveAccessibilitySetting`, so its writes never bump `requestGeneration` — meaning a slower, separately-triggered `load()` elsewhere (e.g. `usePressFeedback`/`useHapticFeedback`, both already calling `useAccessibilitySettings()` today, and `AccessibilitySection` itself calls `usePressFeedback()`) can resolve *after* the Controls page's own newer write and silently overwrite the shared `stored` singleton with stale data — a real, pre-existing race for `visual_motion`/`haptic_motion` today that a third editable field makes more worth closing now. Add a small exported helper for exactly this "I have my own save flow but still need to publish into the shared store" case:

```ts
/** For call sites that run their own save flow (e.g. AccessibilitySection)
 * but still publish into the shared store — invalidates any in-flight
 * load() so a slower GET response can't overwrite this fresher write.
 * saveAccessibilitySetting() doesn't need this: it already tracks its own
 * generation end-to-end. */
export function publishAccessibilitySettingsFromExternalWrite(value: AccessibilitySettings) {
  requestGeneration += 1;
  publishAccessibilitySettings(value);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/hooks/useAccessibilitySettings.test.ts`
Expected: PASS — all tests in the file, including the two pre-existing overlapping-save tests now updated to carry `voice_uri` through their fixtures.

- [ ] **Step 5: Commit**

```bash
git add lib/hooks/useAccessibilitySettings.ts lib/hooks/useAccessibilitySettings.test.ts
git commit -m "feat(web): add voice_uri to the shared AccessibilitySettings type"
```

---

### Task 4: Frontend — `useSpeechVoices` hook + language grouping

**Files:**
- Create: `web/lib/hooks/useSpeechVoices.ts`
- Test: `web/lib/hooks/useSpeechVoices.test.ts`

**Interfaces:**
- Produces: `useSpeechVoices(): { supported: boolean; voices: SpeechSynthesisVoice[] }` and `groupVoicesByLanguage(voices: SpeechSynthesisVoice[]): { lang: string; label: string; voices: SpeechSynthesisVoice[] }[]`. Consumed by Task 7.

- [ ] **Step 1: Write the failing test**

Create `web/lib/hooks/useSpeechVoices.test.ts`:

```ts
// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeechVoices, groupVoicesByLanguage } from './useSpeechVoices';

function voice(overrides: Partial<SpeechSynthesisVoice>): SpeechSynthesisVoice {
  return {
    voiceURI: 'uri',
    name: 'name',
    lang: 'en-US',
    default: false,
    localService: true,
    ...overrides,
  } as SpeechSynthesisVoice;
}

function installSynthesis(initialVoices: SpeechSynthesisVoice[]) {
  const listeners: Array<() => void> = [];
  let current = initialVoices;
  const synthesis = {
    getVoices: vi.fn(() => current),
    addEventListener: vi.fn((_event: string, fn: () => void) => listeners.push(fn)),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal('speechSynthesis', synthesis);
  return {
    synthesis,
    setVoices: (next: SpeechSynthesisVoice[]) => {
      current = next;
      listeners.forEach((fn) => fn());
    },
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
});

describe('useSpeechVoices', () => {
  it('reports unsupported when speech synthesis is unavailable', () => {
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current).toEqual({ supported: false, voices: [] });
  });

  it('returns the voices already available at mount', () => {
    installSynthesis([voice({ voiceURI: 'a' }), voice({ voiceURI: 'b' })]);
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current.supported).toBe(true);
    expect(result.current.voices.map((v) => v.voiceURI)).toEqual(['a', 'b']);
  });

  it('updates when voiceschanged fires later', () => {
    const { setVoices } = installSynthesis([]);
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current.voices).toEqual([]);
    act(() => setVoices([voice({ voiceURI: 'late' })]));
    expect(result.current.voices.map((v) => v.voiceURI)).toEqual(['late']);
  });
});

describe('groupVoicesByLanguage', () => {
  it('groups voices by language tag and sorts groups and voices by label/name', () => {
    const groups = groupVoicesByLanguage([
      voice({ voiceURI: 'b', name: 'Zeta', lang: 'en-US' }),
      voice({ voiceURI: 'a', name: 'Alpha', lang: 'en-US' }),
      voice({ voiceURI: 'c', name: 'Solo', lang: 'es-ES' }),
    ]);
    expect(groups.map((g) => g.lang)).toEqual(['en-US', 'es-ES']);
    expect(groups[0].voices.map((v) => v.name)).toEqual(['Alpha', 'Zeta']);
    expect(groups[0].label.length).toBeGreaterThan(0);
  });

  it('returns an empty array for no voices', () => {
    expect(groupVoicesByLanguage([])).toEqual([]);
  });

  it('falls back to the raw tag when Intl.DisplayNames throws on a malformed lang', () => {
    // Verified: new Intl.DisplayNames(['en'], {type:'language'}).of('not-a-real-lang-tag')
    // throws RangeError rather than returning a fallback string.
    const groups = groupVoicesByLanguage([voice({ voiceURI: 'z', name: 'Zed', lang: 'not-a-real-lang-tag' })]);
    expect(groups).toEqual([{ lang: 'not-a-real-lang-tag', label: 'not-a-real-lang-tag', voices: [expect.objectContaining({ voiceURI: 'z' })] }]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/hooks/useSpeechVoices.test.ts`
Expected: FAIL — `Cannot find module './useSpeechVoices'`.

- [ ] **Step 3: Write minimal implementation**

Create `web/lib/hooks/useSpeechVoices.ts`:

```ts
'use client';

import { useEffect, useState } from 'react';

export function useSpeechVoices() {
  const [supported, setSupported] = useState(false);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);

  useEffect(() => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) return;
    setSupported(true);
    const update = () => setVoices(window.speechSynthesis.getVoices());
    update();
    window.speechSynthesis.addEventListener('voiceschanged', update);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', update);
  }, []);

  return { supported, voices };
}

export interface VoiceLanguageGroup {
  lang: string;
  label: string;
  voices: SpeechSynthesisVoice[];
}

// Intl.DisplayNames#of() throws RangeError on a malformed BCP-47 tag (verified:
// `new Intl.DisplayNames(['en'], {type:'language'}).of('not-a-real-lang-tag')`
// throws rather than returning a fallback) — a real browser's voice.lang
// should always be well-formed, but a label helper for OS-provided strings
// shouldn't be able to crash the whole picker over one malformed one.
function languageLabel(lang: string, displayNames: Intl.DisplayNames | null): string {
  try {
    return displayNames?.of(lang) ?? lang;
  } catch {
    return lang;
  }
}

export function groupVoicesByLanguage(voices: SpeechSynthesisVoice[]): VoiceLanguageGroup[] {
  const byLang = new Map<string, SpeechSynthesisVoice[]>();
  for (const v of voices) {
    const list = byLang.get(v.lang) ?? [];
    list.push(v);
    byLang.set(v.lang, list);
  }
  const displayNames =
    typeof Intl !== 'undefined' && 'DisplayNames' in Intl
      ? new Intl.DisplayNames(['en'], { type: 'language' })
      : null;
  return Array.from(byLang.entries())
    .map(([lang, list]) => ({
      lang,
      label: languageLabel(lang, displayNames),
      voices: [...list].sort((a, b) => a.name.localeCompare(b.name)),
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/hooks/useSpeechVoices.test.ts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add lib/hooks/useSpeechVoices.ts lib/hooks/useSpeechVoices.test.ts
git commit -m "feat(web): add useSpeechVoices hook and language grouping"
```

---

### Task 5: Frontend — `useSpeech` resolves the voice to speak with

**Files:**
- Modify: `web/lib/hooks/useSpeech.ts`
- Test: `web/lib/hooks/useSpeech.test.ts`

**Interfaces:**
- Consumes: `useAccessibilitySettings()` from `./useAccessibilitySettings` (Task 3), specifically its `voice_uri` field.
- Produces: `useSpeech(text: string, voiceURIOverride?: string | null)` — a new optional second parameter. When provided (including explicit `null`), it wins over the persisted setting; when omitted (`undefined`), the persisted `voice_uri` is used. Consumed by Task 6 (`ListenButton`).

- [ ] **Step 1: Write the failing test**

In `web/lib/hooks/useSpeech.test.ts`, first extend `MockUtterance` to carry a `voice` field and add a `getVoices` stub to both mock installers, then add the new test cases. Replace the top of the file (imports through `installPendingSpeech`) with:

```ts
// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeech } from './useSpeech';
import {
  publishAccessibilitySettings,
  resetAccessibilitySettingsForTests,
} from './useAccessibilitySettings';

class MockUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  voice: SpeechSynthesisVoice | null = null;
  constructor(public text: string) {}
}

function installSpeech() {
  let current: MockUtterance | null = null;
  const synthesis = {
    cancel: vi.fn(() => {
      current?.onend?.();
      current = null;
    }),
    speak: vi.fn((utterance: MockUtterance) => {
      current = utterance;
      utterance.onstart?.();
    }),
    getVoices: vi.fn(() => [] as SpeechSynthesisVoice[]),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

function installPendingSpeech() {
  let current: MockUtterance | null = null;
  const synthesis = {
    cancel: vi.fn(() => {
      current = null;
    }),
    // Does not call onstart synchronously - simulates real TTS engines where
    // speak() queues the utterance and onstart fires later (or never, if
    // canceled first).
    speak: vi.fn((utterance: MockUtterance) => {
      current = utterance;
    }),
    getVoices: vi.fn(() => [] as SpeechSynthesisVoice[]),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
  resetAccessibilitySettingsForTests();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null })),
  ));
});
```

(`vi.stubGlobal('fetch', ...)` in `beforeEach` runs before the next test's `vi.unstubAllGlobals()` at the top of the *following* `beforeEach`, so each test gets a fresh, deterministic fetch stub — matching the pattern already used for `speechSynthesis`.)

Then add these new cases at the end of the `describe('useSpeech', ...)` block, right before its closing `});`:

```ts
  it('sets the utterance voice from the persisted accessibility setting', async () => {
    const synthesis = installSpeech();
    const enVoice = { voiceURI: 'en-voice', name: 'En Voice', lang: 'en-US' } as SpeechSynthesisVoice;
    synthesis.getVoices.mockReturnValue([enVoice]);
    act(() => publishAccessibilitySettings({ visual_motion: true, haptic_motion: true, voice_uri: 'en-voice' }));
    const { result } = renderHook(() => useSpeech('Hello'));
    await waitFor(() => expect(result.current.supported).toBe(true));
    act(() => result.current.toggle());
    expect(synthesis.speak.mock.calls[0][0].voice).toBe(enVoice);
  });

  it('prefers an explicit voice override over the persisted setting', async () => {
    const synthesis = installSpeech();
    const overrideVoice = { voiceURI: 'override', name: 'Override', lang: 'en-GB' } as SpeechSynthesisVoice;
    synthesis.getVoices.mockReturnValue([overrideVoice]);
    act(() => publishAccessibilitySettings({ visual_motion: true, haptic_motion: true, voice_uri: 'persisted' }));
    const { result } = renderHook(() => useSpeech('Hello', 'override'));
    await waitFor(() => expect(result.current.supported).toBe(true));
    act(() => result.current.toggle());
    expect(synthesis.speak.mock.calls[0][0].voice).toBe(overrideVoice);
  });

  it('leaves the default voice unset when the persisted voice is not installed', async () => {
    const synthesis = installSpeech();
    synthesis.getVoices.mockReturnValue([]);
    act(() => publishAccessibilitySettings({ visual_motion: true, haptic_motion: true, voice_uri: 'missing' }));
    const { result } = renderHook(() => useSpeech('Hello'));
    await waitFor(() => expect(result.current.supported).toBe(true));
    act(() => result.current.toggle());
    expect(synthesis.speak.mock.calls[0][0].voice).toBeNull();
  });

  it('leaves the default voice unset for an explicit null override (System default)', async () => {
    const synthesis = installSpeech();
    act(() => publishAccessibilitySettings({ visual_motion: true, haptic_motion: true, voice_uri: 'persisted' }));
    const { result } = renderHook(() => useSpeech('Hello', null));
    await waitFor(() => expect(result.current.supported).toBe(true));
    act(() => result.current.toggle());
    expect(synthesis.speak.mock.calls[0][0].voice).toBeNull();
    expect(synthesis.getVoices).not.toHaveBeenCalled();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run lib/hooks/useSpeech.test.ts`
Expected: FAIL — the four new tests fail because `useSpeech` doesn't accept a second argument or read `voice_uri` yet (`synthesis.speak.mock.calls[0][0].voice` is `undefined`/`null` regardless of the mocked voice).

- [ ] **Step 3: Write minimal implementation**

Replace `web/lib/hooks/useSpeech.ts` in full:

```ts
'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAccessibilitySettings } from './useAccessibilitySettings';

// ponytail: module-scoped, shared by every useSpeech instance. Browsers
// don't reliably fire onend/onerror for a queued-but-not-started utterance
// dropped by a global cancel() (e.g. clicking a different listen button),
// so the button that queued it needs an explicit nudge to drop "speaking".
let activeClear: (() => void) | null = null;

export function useSpeech(text: string, voiceURIOverride?: string | null) {
  // ponytail: starts false so server and first client render match; flips
  // true post-mount, avoiding a hydration mismatch on supported browsers.
  const [supported, setSupported] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const speakingRef = useRef(false);
  // ponytail: tracks the in-flight utterance so a stale onend/onerror (fired
  // after cancel() on a queued-but-not-yet-started utterance) can't clobber
  // state for whichever utterance actually replaced it.
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const { voice_uri: persistedVoiceURI } = useAccessibilitySettings();
  const voiceURI = voiceURIOverride !== undefined ? voiceURIOverride : persistedVoiceURI;

  useEffect(() => {
    setSupported(typeof window !== 'undefined' && 'speechSynthesis' in window);
  }, []);

  useEffect(() => {
    return () => {
      // speakingRef only stays true here if nothing else has claimed
      // activeClear since (any other toggle() would have cleared us), so
      // it's safe to drop it unconditionally.
      if (speakingRef.current) {
        window.speechSynthesis.cancel();
        activeClear = null;
      }
    };
  }, []);

  const toggle = useCallback(() => {
    if (!supported) return;

    const wasSpeaking = speaking;
    window.speechSynthesis.cancel();
    activeClear?.();
    activeClear = null;
    utteranceRef.current = null;
    if (wasSpeaking) {
      speakingRef.current = false;
      setSpeaking(false);
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    if (voiceURI) {
      const match = window.speechSynthesis.getVoices().find((v) => v.voiceURI === voiceURI);
      if (match) utterance.voice = match;
    }
    const clear = () => {
      if (utteranceRef.current !== utterance) return;
      utteranceRef.current = null;
      speakingRef.current = false;
      setSpeaking(false);
      if (activeClear === clear) activeClear = null;
    };
    utterance.onend = clear;
    utterance.onerror = clear;

    // Mark speaking as soon as the utterance is queued, not on onstart:
    // speak() can queue without starting immediately, and a queued utterance
    // still needs to be cancelable (on unmount or a second click).
    utteranceRef.current = utterance;
    activeClear = clear;
    speakingRef.current = true;
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }, [speaking, supported, text, voiceURI]);

  return { supported, speaking, toggle };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run lib/hooks/useSpeech.test.ts`
Expected: PASS (all tests, old and new — the pre-existing tests never publish a `voice_uri`, so it stays `null` and `if (voiceURI)` stays falsy, leaving `utterance.voice` untouched exactly as before).

- [ ] **Step 5: Commit**

```bash
git add lib/hooks/useSpeech.ts lib/hooks/useSpeech.test.ts
git commit -m "feat(web): resolve SpeechSynthesisVoice from accessibility setting or override"
```

---

### Task 6: Frontend — `ListenButton` accepts an optional voice override

**Files:**
- Modify: `web/components/ui/listen-button.tsx`
- Test: `web/components/ui/listen-button.test.tsx`

**Interfaces:**
- Consumes: `useSpeech(text, voiceURIOverride?)` from Task 5.
- Produces: `<ListenButton text ariaLabel voiceURI? />` — `voiceURI` is optional and `undefined` by default, so both existing call sites (`web/app/(dashboard)/jobs/[id]/page.tsx`'s `FieldCard`, `web/app/(dashboard)/spaces/[id]/ContextTab.tsx`) need no changes. Consumed by Task 7's preview control.

- [ ] **Step 1: Write the failing test**

Add to `web/components/ui/listen-button.test.tsx`. First extend `MockUtterance` and `installSpeech()`'s `synthesis` object (mirroring Task 5's test setup) — replace the top of the file through `installSpeech`:

```tsx
// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ListenButton } from './listen-button';
import { resetAccessibilitySettingsForTests } from '@/lib/hooks/useAccessibilitySettings';

class MockUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  voice: SpeechSynthesisVoice | null = null;
  constructor(public text: string) {}
}

function installSpeech() {
  const synthesis = {
    cancel: vi.fn(),
    speak: vi.fn((utterance: MockUtterance) => utterance.onstart?.()),
    getVoices: vi.fn(() => [] as SpeechSynthesisVoice[]),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
  resetAccessibilitySettingsForTests();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null })),
  ));
});
```

Then add this test inside the existing `describe('ListenButton', ...)` block:

```tsx
  it('speaks with the voice named by the voiceURI prop', () => {
    const synthesis = installSpeech();
    const pickedVoice = { voiceURI: 'picked', name: 'Picked', lang: 'en-US' } as SpeechSynthesisVoice;
    synthesis.getVoices.mockReturnValue([pickedVoice]);
    render(<ListenButton text="Hello" ariaLabel="Preview voice" voiceURI="picked" />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview voice' }));
    expect(synthesis.speak.mock.calls[0][0].voice).toBe(pickedVoice);
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run components/ui/listen-button.test.tsx`
Expected: FAIL — TypeScript rejects the unknown `voiceURI` prop, and even ignoring that, `synthesis.speak.mock.calls[0][0].voice` is `null`.

- [ ] **Step 3: Write minimal implementation**

Replace `web/components/ui/listen-button.tsx` in full:

```tsx
'use client';

import { Square, Volume2 } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { useSpeech } from '@/lib/hooks/useSpeech';

export function ListenButton({
  text,
  ariaLabel,
  voiceURI,
}: {
  text: string;
  ariaLabel: string;
  voiceURI?: string | null;
}) {
  const { supported, speaking, toggle } = useSpeech(text, voiceURI);
  if (!supported || !text.trim()) return null;

  const label = speaking ? 'Stop' : ariaLabel;
  return (
    <Tooltip content={label}>
      <button
        onClick={toggle}
        aria-label={label}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {speaking ? <Square className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
      </button>
    </Tooltip>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run components/ui/listen-button.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add components/ui/listen-button.tsx components/ui/listen-button.test.tsx
git commit -m "feat(web): let ListenButton accept an explicit voice override"
```

---

### Task 7: Frontend — Voice row in the Accessibility section

**Files:**
- Modify: `web/app/(dashboard)/controls/page.tsx` (the `AccessibilitySection` function)
- Test: `web/app/(dashboard)/controls/page.test.tsx`

**Interfaces:**
- Consumes: `useSpeechVoices`/`groupVoicesByLanguage` (Task 4), `ListenButton` with `voiceURI` (Task 6), `AccessibilitySettings` with `voice_uri` and `publishAccessibilitySettingsFromExternalWrite` (Task 3), existing `apiPut`.
- Produces: nothing consumed by later tasks — this is the UI leaf.

- [ ] **Step 1: Write the failing test**

The new tests below are the first in this file to call `vi.stubGlobal('speechSynthesis', ...)`; without per-test cleanup that stub would leak into whichever test runs next (this file already re-establishes its `fetch` mock fresh in every `beforeEach`, so clearing all stubs after each test is safe). This is also the first test file in this plan to mount `useAccessibilitySettings`'s module singleton (via `ListenButton`'s internal `useSpeech` call) from inside a *different* file than the one that owns it — reset it too, matching the pattern in Tasks 5 and 6. Change the imports (the new generation-guard regression test below needs `act`, already re-exported by `@/test/render`'s `export * from '@testing-library/react'`):

```ts
import { render, screen, fireEvent, waitFor, within, act } from '@/test/render';
```

```ts
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
```

```ts
import { resetAccessibilitySettingsForTests } from '@/lib/hooks/useAccessibilitySettings';
```

And add, right after the existing `beforeEach(() => { ... });` block:

```ts
afterEach(() => {
  vi.unstubAllGlobals();
  resetAccessibilitySettingsForTests();
});
```

Update the `beforeEach` fetch stub in `web/app/(dashboard)/controls/page.test.tsx` (lines 59-67) to include `voice_uri`:

```ts
    if (String(input).includes('accessibility-settings')) {
      if (init?.method === 'PUT') {
        return new Response(init.body as string, { status: 200 });
      }
      return new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
      }), { status: 200 });
    }
```

Add these tests inside the `describe('ControlsPage', ...)` block:

```tsx
  it('hides the Voice row when speech synthesis is unsupported', () => {
    // Explicit regardless of prior test ordering/global stub leakage — vitest
    // doesn't auto-clear vi.stubGlobal between tests in this file (its
    // beforeEach only re-stubs fetch), so a speechSynthesis stub set by a
    // later-defined test must never be relied on to be absent here.
    delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
    render(<ControlsPage />);
    expect(section('Accessibility').queryByText('Voice')).toBeNull();
  });

  it('shows the Voice row grouped by language and lets the operator pick a voice', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
      { voiceURI: 'uk', name: 'Daniel', lang: 'en-GB' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    render(<ControlsPage />);

    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;
    expect(within(select).getByText('System default')).toBeTruthy();
    // Intl.DisplayNames(['en'], {type:'language'}).of('en-US') resolves to
    // "American English" under Node/browser ICU data, not a literal
    // "English (United States)" — assert the real resolved label.
    expect(within(select).getByRole('group', { name: 'American English' })).toBeTruthy();
    expect(within(select).getByText('Google US English')).toBeTruthy();
    expect(within(select).getByText('Daniel')).toBeTruthy();

    fireEvent.change(select, { target: { value: 'uk' } });
    await waitFor(() => expect(select.value).toBe('uk'));
  });

  it('shows an unavailable-voice placeholder and lets the operator clear it to System default', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    // Override this test's GET response with a voice_uri from a machine/browser
    // that doesn't have that voice installed.
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('accessibility-settings')) {
        if (init?.method === 'PUT') return new Response(init.body as string, { status: 200 });
        return new Response(JSON.stringify({
          visual_motion: true,
          haptic_motion: true,
          voice_uri: 'a-voice-from-another-machine',
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 });
    }));
    render(<ControlsPage />);

    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;
    // Showing "" here (silently) would be a dead end: the same-value click
    // wouldn't fire onChange, so the stale URI could never be cleared. It
    // must show the missing URI as its own (disabled) option instead.
    await waitFor(() => expect(select.value).toBe('a-voice-from-another-machine'));
    expect(within(select).getByText('Unavailable voice')).toBeTruthy();

    fireEvent.change(select, { target: { value: '' } });
    await waitFor(() => expect(select.value).toBe(''));
  });

  it('keeps the newer voice pick when its PUT resolves before an older overlapping one', async () => {
    // Regression test for the generationRef guard: pick 'us' (PUT deferred),
    // then pick 'uk' before the first PUT resolves (PUT also deferred).
    // Resolve the OLDER ('us') request last — without the guard, its
    // response would land last and roll the UI back to 'us'.
    //
    // Note: a mouse/keyboard user can't literally trigger this — the select
    // is disabled while saving={true}, so a real second pick can't happen
    // before the first PUT settles. fireEvent.change bypasses the disabled
    // attribute (it dispatches the DOM event directly), which is exactly
    // what's needed here: this test exercises the generationRef guard logic
    // itself, the same logic Task 3's "external write invalidates a slower
    // in-flight load" test exercises from the other direction — not a
    // literal two-click scenario.
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
      { voiceURI: 'uk', name: 'Daniel', lang: 'en-GB' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));

    let resolveFirstPut!: (response: Response) => void;
    let resolveSecondPut!: (response: Response) => void;
    const firstPut = new Promise<Response>((done) => { resolveFirstPut = done; });
    const secondPut = new Promise<Response>((done) => { resolveSecondPut = done; });
    let putCount = 0;
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('accessibility-settings')) {
        if (init?.method === 'PUT') {
          putCount += 1;
          return putCount === 1 ? firstPut : secondPut;
        }
        return Promise.resolve(new Response(JSON.stringify({
          visual_motion: true,
          haptic_motion: true,
          voice_uri: null,
        }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 }));
    }));

    render(<ControlsPage />);
    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;

    fireEvent.change(select, { target: { value: 'us' } });
    await waitFor(() => expect(select.value).toBe('us'));
    fireEvent.change(select, { target: { value: 'uk' } });
    await waitFor(() => expect(select.value).toBe('uk'));

    await act(async () => {
      // Older request resolves LAST.
      resolveSecondPut(new Response(JSON.stringify({
        visual_motion: true, haptic_motion: true, voice_uri: 'uk',
      }), { status: 200 }));
      await secondPut;
      resolveFirstPut(new Response(JSON.stringify({
        visual_motion: true, haptic_motion: true, voice_uri: 'us',
      }), { status: 200 }));
      await firstPut;
    });

    expect(select.value).toBe('uk');
  });

  it('previews the selected voice via the Listen affordance', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
    ] as SpeechSynthesisVoice[];
    const speak = vi.fn();
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak,
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    render(<ControlsPage />);

    // Wait for the exact element being clicked, not a sibling: the select's
    // visibility is gated on useSpeechVoices' own supported flag, but the
    // preview button's is gated on ListenButton's *own* internal useSpeech
    // effect — a separate hook instance with its own tick. Waiting on the
    // select alone doesn't guarantee the button is mounted yet.
    const previewButton = await section('Accessibility').findByRole('button', { name: 'Preview voice' });
    fireEvent.click(previewButton);
    expect(speak).toHaveBeenCalledOnce();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "app/(dashboard)/controls/page.test.tsx"`
Expected: FAIL — no "Voice" label/select exists yet.

- [ ] **Step 3: Write minimal implementation**

In `web/app/(dashboard)/controls/page.tsx`, add imports alongside the existing ones:

```tsx
import { useSpeechVoices, groupVoicesByLanguage } from "@/lib/hooks/useSpeechVoices";
import { ListenButton } from "@/components/ui/listen-button";
```

Also add `publishAccessibilitySettingsFromExternalWrite` to the file's existing `useAccessibilitySettings` import (currently `import { publishAccessibilitySettings, type AccessibilitySettings } from "@/lib/hooks/useAccessibilitySettings";`) — `AccessibilitySection` now uses the external-write variant exclusively, so drop the plain `publishAccessibilitySettings` import too:

```tsx
import { publishAccessibilitySettingsFromExternalWrite, type AccessibilitySettings } from "@/lib/hooks/useAccessibilitySettings";
```

Add this constant near the top of the file (alongside other module-level constants such as `DELETE_ACCOUNT_CONSEQUENCES`):

```tsx
const VOICE_PREVIEW_TEXT = "This is how enrichment will sound.";
const VOICE_SELECT_CLASS =
  "h-10 flex-1 rounded-md border border-line bg-canvas px-3 text-sm text-ink outline-none transition-ui focus:border-signal disabled:cursor-not-allowed disabled:text-muted disabled:opacity-70";
```

Replace the `AccessibilitySection` function's state, `toggle`, and returned JSX:

```tsx
function AccessibilitySection() {
  const [settings, setSettings] = useState<AccessibilitySettings>({
    visual_motion: true,
    haptic_motion: true,
    voice_uri: null,
  });
  // Only true once a real GET response has applied, so a failed initial
  // load can't leave the checkboxes editable against the hardcoded
  // { true, true, null } placeholder above.
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const pressFeedback = usePressFeedback();
  const { supported: speechSupported, voices } = useSpeechVoices();
  const voiceGroups = groupVoicesByLanguage(voices);
  // Guards against an older overlapping update() call (e.g. toggling a
  // checkbox right after picking a voice) resolving last and clobbering a
  // newer save's result — mirrors saveAccessibilitySetting's own
  // requestGeneration pattern in useAccessibilitySettings.ts, needed here too
  // now that a row's onChange can fire faster than a round trip resolves.
  const generationRef = useRef(0);
  // The persisted voice_uri may not be among voices on this browser/device
  // (set on another machine, or the voice was uninstalled). Silently showing
  // "System default" while the stored value is still the missing URI is a
  // dead end: the select's value already equals "" then, so choosing
  // "System default" from the list is a no-op click (onChange only fires on
  // an actual value change) and the stale URI is never cleared. Instead,
  // render it as its own disabled option so it's visibly the current
  // selection, and picking "System default" (a real value change) fires
  // onChange and persists null like any other pick.
  const isPersistedVoiceInstalled = voiceGroups.some((group) =>
    group.voices.some((voice) => voice.voiceURI === settings.voice_uri),
  );

  useEffect(() => {
    const controller = new AbortController();
    fetch("/api/controls/accessibility-settings", { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok)
          throw new Error("Failed to load accessibility settings");
        return response.json() as Promise<AccessibilitySettings>;
      })
      .then((value) => {
        if (!controller.signal.aborted) {
          setSettings(value);
          publishAccessibilitySettingsFromExternalWrite(value);
          setLoaded(true);
        }
      })
      .catch((caught) => {
        if (
          controller.signal.aborted ||
          (caught instanceof Error && caught.name === "AbortError")
        )
          return;
        setError(
          caught instanceof Error
            ? caught.message
            : "Failed to load accessibility settings",
        );
      });
    return () => controller.abort();
  }, []);

  const update = async <K extends keyof AccessibilitySettings>(
    key: K,
    value: AccessibilitySettings[K],
  ) => {
    const generation = ++generationRef.current;
    const previous = settings;
    const next = { ...settings, [key]: value };
    setSettings(next);
    publishAccessibilitySettingsFromExternalWrite(next);
    setSaving(true);
    setError(undefined);
    try {
      const saved = await apiPut<AccessibilitySettings>(
        "/api/controls/accessibility-settings",
        next,
        "Failed to save accessibility settings",
      );
      if (generation !== generationRef.current) return;
      setSettings(saved);
      publishAccessibilitySettingsFromExternalWrite(saved);
    } catch (caught) {
      if (generation !== generationRef.current) return;
      setSettings(previous);
      publishAccessibilitySettingsFromExternalWrite(previous);
      setError(
        caught instanceof Error
          ? caught.message
          : "Failed to save accessibility settings",
      );
    } finally {
      if (generation === generationRef.current) setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      {(
        [
          [
            "visual_motion",
            "Press animation",
            "Show tactile press animation on touch controls.",
          ],
          [
            "haptic_motion",
            "Haptic motion",
            "Vibrate for completed or failed actions when your device supports it.",
          ],
        ] as const
      ).map(([key, label, description]) => (
        <div key={key}>
          <label className="flex items-center gap-3 text-sm text-ink">
            <input
              {...pressFeedback}
              type="checkbox"
              checked={settings[key]}
              disabled={!loaded || saving}
              onChange={(event) => void update(key, event.target.checked)}
              className="h-4 w-4 accent-signal active:scale-[0.96] motion-reduce:active:scale-100"
            />
            <span className="font-medium">{label}</span>
          </label>
          <p className="ml-7 mt-1.5 text-xs text-muted">{description}</p>
        </div>
      ))}
      {speechSupported && (
        <div>
          <label
            htmlFor="accessibility-voice-select"
            className="text-sm font-medium text-ink"
          >
            Voice
          </label>
          <p className="mt-1.5 text-xs text-muted">
            Choose which installed voice narrates text aloud. System default
            uses your browser&apos;s normal voice.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <select
              id="accessibility-voice-select"
              value={settings.voice_uri ?? ""}
              disabled={!loaded || saving}
              onChange={(event) => void update("voice_uri", event.target.value || null)}
              className={VOICE_SELECT_CLASS}
            >
              <option value="">System default</option>
              {settings.voice_uri && !isPersistedVoiceInstalled && (
                <option value={settings.voice_uri} disabled>
                  Unavailable voice
                </option>
              )}
              {voiceGroups.map((group) => (
                <optgroup key={group.lang} label={group.label}>
                  {group.voices.map((voice) => (
                    <option key={voice.voiceURI} value={voice.voiceURI}>
                      {voice.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <ListenButton
              text={VOICE_PREVIEW_TEXT}
              ariaLabel="Preview voice"
              voiceURI={settings.voice_uri}
            />
          </div>
        </div>
      )}
      {error && (
        <p className="ml-7 text-sm text-status-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "app/(dashboard)/controls/page.test.tsx"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add "app/(dashboard)/controls/page.tsx" "app/(dashboard)/controls/page.test.tsx"
git commit -m "feat(web): add global voice picker to Controls > Accessibility"
```

---

## Self-Review

**Spec coverage:**
- Global (not per-field) persistence → Task 1 + 2 (backend), Task 3 (shared frontend type/store already global via `useAccessibilitySettings`'s module singleton).
- `useSpeech`/`ListenButton` pick up the setting everywhere Listen already ships (job detail, Space context) with zero changes to those two call sites → Task 5 (reads the persisted setting by default) + Task 6 (optional prop, `undefined` by default).
- Approved frontend design (grouped-by-language select, System default option, preview reusing the Listen icon-swap language) → Task 4 (grouping) + Task 7 (UI, reusing `ListenButton` unmodified for preview).
- No DB migration → confirmed in Task 1 (schemaless `user_settings` blob).

**Placeholder scan:** none — every step has runnable code, no "TBD"/"similar to Task N" shortcuts.

**Round 2 adversarial pass (Codex, gpt-5.5, same session):** full transcript in `PLAN-REVIEW-LOG.md`. Accepted: the Round-1 "fall back to System default when unavailable" fix was a dead end — the select's value already equaled `""`, so re-picking "System default" wouldn't fire `onChange` and the stale URI could never be cleared; replaced with a disabled "Unavailable voice" phantom option carrying the stale URI as its value, so picking "System default" is a real value change (Task 7, `isPersistedVoiceInstalled` + test). The Round-1 generation guard had no regression test proving it does what it's for; added one with two deferred PUTs resolving out of order (Task 7). `resetAccessibilitySettingsForTests()` didn't invalidate `requestGeneration`, leaving a narrow flakiness window for a test that ends without awaiting its own save; bumped it on reset (Task 3). The generic-`saveAccessibilitySetting` test only proved the response round-tripped, not that the request body actually carried `voice_uri`; strengthened to assert the PUT body, and updated the file's two pre-existing overlapping-save tests to carry `voice_uri` through their fixtures too, since that's exactly the logic a third field could subtly break (Task 3). `set_accessibility_settings()` could theoretically be called internally with an unbounded string, bypassing the API's `max_length`; documented it as trusting its one caller rather than duplicating the bound (Task 1) — cheaper and no less correct given there's only one call site. Rejected: restructuring `update()` around a `settingsRef`/functional-updater to guard against two `onChange` handlers firing within the same React tick — for three independent native form controls each requiring its own physical user interaction, React 18 only batches state updates scheduled within a single event handler's call stack, not across two separately-dispatched DOM events, so `settings` is guaranteed current by the next physical click; the exact same closure pattern already exists in the pre-existing two-checkbox `toggle()` today. Noted as a real but very low-probability theoretical concern, not fixed.

**Type consistency:** `AccessibilitySettings` (Task 3: `{visual_motion, haptic_motion, voice_uri}`) is the single type threaded through Task 1/2's API shape, Task 5's `useSpeech(text, voiceURIOverride?)`, Task 6's `ListenButton({text, ariaLabel, voiceURI?})`, and Task 7's `update<K>(key, value)` — no renamed fields or mismatched signatures across tasks. `saveAccessibilitySetting<K>(key, value: AccessibilitySettings[K])` (Task 3) matches the same generic shape. `publishAccessibilitySettingsFromExternalWrite(value: AccessibilitySettings)` (Task 3) takes the full object, matching every one of Task 7's four call sites.

**Round 3 adversarial pass (Codex, gpt-5.5, same session):** full transcript in `PLAN-REVIEW-LOG.md`. Accepted: verified `usePressFeedback` really does call `useAccessibilitySettings()` (Task 7's `AccessibilitySection` already calls `usePressFeedback()`), confirming a real, pre-existing race — `AccessibilitySection`'s own independent GET/PUT cycle never bumped `requestGeneration`, so a slower `load()` triggered elsewhere on the same page could resolve after a newer write and silently overwrite the shared singleton; added `publishAccessibilitySettingsFromExternalWrite()` (Task 3, bumps the counter, +regression test) and switched all four of `AccessibilitySection`'s publish calls to it (Task 7). The preview test waited on the select's own label rather than the specific button it was about to click — `ListenButton`'s visibility is gated by its own internal `useSpeech` effect, a different hook instance with its own tick than `useSpeechVoices`'; changed the wait target to `findByRole('button', {name:'Preview voice'})` (Task 7) — a strictly safer assertion regardless of whether the two ever race in practice. Confirmed by tracing the actual code that the "overlapping PUTs" regression test only works because `fireEvent.change` bypasses the `disabled` attribute — a real user cannot trigger a second pick before the first PUT resolves, since the select disables itself while `saving`. Left the test in place (it still correctly exercises the `generationRef` guard's logic) but added a comment stating plainly that this is a guard-logic test, not a literal two-click reproduction, so a future reader doesn't mistake it for one.

**Round 1 adversarial pass (Codex, gpt-5.5):** full transcript in `PLAN-REVIEW-LOG.md`. Accepted and folded in: the legacy-row-vs-whole-object-fallback wording was genuinely ambiguous (fixed in Global Constraints); `voice_uri` needed a `max_length` bound (Task 2, +422 test); `saveAccessibilitySetting`'s signature had a real type hole once `voice_uri` joined `keyof AccessibilitySettings` (Task 3, genericized, +regression test); `Intl.DisplayNames#of()` provably throws on a malformed tag — verified with `node -e`, not assumed (Task 4, try/catch + regression test); Task 7's local `update()` was missing the request-generation race guard the shared module already has for this exact scenario (added); a persisted `voice_uri` not installed on the current browser could leave the controlled `<select>` with no matching option (Task 7, derived `selectableVoiceURI` + test); Task 7's test file needed `resetAccessibilitySettingsForTests()` too, matching Tasks 5/6 (added); frontend command paths were inconsistent between Tasks 3-6 (repo-root-relative) and Task 7 (web/-relative) — standardized on web/-relative throughout, matching this repo's own documented convention. Rejected, with reasons logged: making `voice_uri` optional for rollout safety (no rolling-deployment risk in a single-operator app); full runtime JSON normalization on every frontend fetch (inconsistent with how every other hook in this codebase already trusts the backend's response shape); a claim that Task 5 was missing its fetch stub/singleton reset (false — already present); sharing a `voiceschanged` listener/cache between `useSpeech` and `useSpeechVoices` (real complexity for a narrow, softly-degrading edge case — documented as a deliberate cut in Global Constraints instead); feature-detecting `addEventListener` with an `onvoiceschanged` fallback (no shipping browser needs it); adding an MSW mock handler for this endpoint (verified none exists today for any of the three fields — pre-existing gap, out of scope).
