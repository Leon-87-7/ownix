# Council Fixes — Chunk 1/5: Critical fixes — auth fail-open, crashing script, Gemini timeout, WCAG, React majors

> **For agentic workers:** This is chunk 1 of 5 of `main-council-fixes.md`. Use superpowers:subagent-driven-development: dispatch **one subagent per task below, all in parallel in a single message** — every task in this chunk touches a disjoint set of files, so no coordination is needed while editing/testing. Chunks must be executed in order (chunk N+1 only after chunk N is fully committed), because tasks in different chunks intentionally share files.
>
> **Commit discipline for parallel agents:** edits and test runs happen in parallel, but `git add`/`git commit` must NOT run concurrently (index.lock contention). Either (a) each agent finishes edits+tests and reports back, then the orchestrator commits each task's files serially with that task's commit message, or (b) agents commit themselves but retry on index.lock errors. Option (a) is recommended.

**Parallel task map (task → files touched, all disjoint within this chunk):**

- **Task 1: `TELEGRAM_WEBHOOK_SECRET` / `TELEGRAM_BOT_TOKEN` must fail fast when empty** — `src/config.py`, `tests/test_config.py`
- **Task 2: Delete `scripts/backfill_brain.py` (Blocker — crashes on run)** — `scripts/backfill_brain.py`
- **Task 4: Gemini client — add an explicit request timeout** — `src/services/gemini.py`, `tests/test_gemini_client.py`
- **Task 6: Invalid Tailwind class sweep (WCAG contrast fix + dead classes)** — `web/app/(dashboard)/page.tsx`, `web/app/mini/page.tsx`, `web/components/brain-graph.tsx`
- **Task 7: `TelegramToggle` — in-flight guard + unmount cleanup** — `web/components/doc-parser/telegram-toggle.test.tsx`, `web/components/doc-parser/telegram-toggle.tsx`
- **Task 8: `doc-parser/[id]/page.tsx` — `load()` cancellation guard** — `web/app/(dashboard)/doc-parser/[id]/page.test.tsx`, `web/app/(dashboard)/doc-parser/[id]/page.tsx`
- **Task 11: Add a global error boundary (`web/app/error.tsx`)** — `web/app/error.tsx`

## Global Constraints

- This plan file is the only artifact this planning pass wrote. Every task below performs real source edits — do not treat the plan itself as read-only.
- Run Python tests directly, never through the `rtk` hook or `rtk proxy`: `python -m pytest tests/test_foo.py -q` or `python -m pytest tests -q`. If a full-suite run gets backgrounded with empty output, split into per-file/per-directory runs.
- Run web tests with the repo's configured runner: `npx vitest run <path>` (Vitest 4.x, Testing Library — see `web/vitest.config.*`). Do not invent a different runner.
- Each task must end in its own commit with a conventional-commit message (`fix:`, `refactor:`, `chore:`, `perf:`, `docs:`) — do not batch unrelated tasks into one commit.
- Preserve existing behavior unless the finding explicitly calls for a behavior change — most tasks are bug fixes or refactors, not new features.
- Design-system edits (colors, spacing, copy casing) must follow `DESIGN.md` at the repo root (dark plate ladder, single rationed signal orange `#f6921e` = "act here", JetBrains Mono for machine facts) — do not invent new tokens; reuse existing Tailwind config classes (`bg-signal`, `text-onsignal`, `bg-raised`, `text-muted`, `border-line`, etc. — see `web/tailwind.config.ts`).
- Two tasks (Task 21: APScheduler→sleep-loop, Task 27: HKDF key derivation) are marked **OPTIONAL** — the review flagged them as "user decision" items. Implement them only if the user confirms; otherwise skip and leave them unchecked.
- Do not merge to `main`/`master` unless the user explicitly names it as the target in that message (repo rule, `.claude/rules/no-merge-to-main.md`).

---

## Task 1: `TELEGRAM_WEBHOOK_SECRET` / `TELEGRAM_BOT_TOKEN` must fail fast when empty

**Files:**
- Modify: `src/config.py:19-20`
- Create: `tests/test_config.py`

**Major:** Both fields are typed plain `str` with no minimum length. An empty `TELEGRAM_WEBHOOK_SECRET` (e.g. unset env var in a misconfigured deploy) makes `compare_digest("", "")` at `src/telegram/webhook.py:1445` return `True`, silently disabling webhook authentication — any caller can post fake Telegram updates. `pydantic-settings` already validates on `Settings()` construction (`settings = Settings()` at `src/config.py:123`), so a length guard turns this into a startup crash instead of a silent bypass.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for src/config.py — startup validation guards."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings


def _base_env(**overrides: str) -> dict[str, str]:
    env = {"TELEGRAM_BOT_TOKEN": "123:ABC", "TELEGRAM_WEBHOOK_SECRET": "s3cr3t"}
    env.update(overrides)
    return env


def test_settings_rejects_empty_webhook_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_WEBHOOK_SECRET=""))


def test_settings_rejects_empty_bot_token() -> None:
    with pytest.raises(ValidationError):
        Settings(**_base_env(TELEGRAM_BOT_TOKEN=""))


def test_settings_accepts_nonempty_required_fields() -> None:
    s = Settings(**_base_env())
    assert s.TELEGRAM_WEBHOOK_SECRET == "s3cr3t"
    assert s.TELEGRAM_BOT_TOKEN == "123:ABC"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -q`
Expected: FAIL — `Settings(TELEGRAM_WEBHOOK_SECRET="")` currently succeeds, so `pytest.raises(ValidationError)` raises `Failed: DID NOT RAISE`.

- [ ] **Step 3: Add the length guard**

In `src/config.py`, change:

```python
    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_SECRET: str
```

to:

```python
    # --- Required at startup (slice #1) ---
    TELEGRAM_BOT_TOKEN: str = Field(min_length=1)
    TELEGRAM_WEBHOOK_SECRET: str = Field(min_length=1)
```

`Field` is already imported at the top of `src/config.py` (`from pydantic import Field`), so no import changes are needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Run the full config-adjacent suite for regressions**

Run: `python -m pytest tests/test_webhook.py -q`
Expected: all pass — `TELEGRAM_WEBHOOK_SECRET`/`TELEGRAM_BOT_TOKEN` are already set to non-empty values in the test env/fixtures, so this is a no-op check, not a real regression risk.

- [ ] **Step 6: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "fix(config): fail fast on empty TELEGRAM_WEBHOOK_SECRET/TELEGRAM_BOT_TOKEN"
```

---

---

## Task 2: Delete `scripts/backfill_brain.py` (Blocker — crashes on run)

**Files:**
- Delete: `scripts/backfill_brain.py`

**Blocker:** `scripts/backfill_brain.py:143` and `:195` reference `settings.GOOGLE_SHEETS_ID_SHORT` / `settings.GOOGLE_SHEETS_ID_LONG`. ADR-0013 (`docs/adr/0013-consolidate-sheets-into-tabs.md`) consolidated the three per-domain sheet IDs into one `settings.GOOGLE_SHEETS_ID` (see `src/config.py:51-54`). `tests/test_sheets.py:26-39` (`test_settings_drops_legacy_short_var`, `test_settings_drops_legacy_long_var`) asserts these attributes raise `AttributeError` on `settings` — so this script now crashes with `AttributeError` at the first sheet read. It performs a one-time historical-data migration into the Second Brain that has already run (per the module docstring, it's a `python -m scripts.backfill_brain` one-shot); there's no live workbook layout to migrate against anymore, and rewriting it against the single-workbook layout would require re-deriving which sheet rows are "short" vs "long" from tab name instead of spreadsheet ID, plus a full re-test — effort with no remaining use. Delete it.

- [ ] **Step 1: Confirm no other code imports this script**

Run: `python -c "import ast,glob; [ast.parse(open(f, encoding='utf-8').read()) for f in glob.glob('src/**/*.py', recursive=True)]"` is not the check needed — instead grep for importers:

```bash
grep -rn "backfill_brain" --include="*.py" src tests
```

Expected: no output (only `scripts/backfill_brain.py` itself references itself; the module isn't imported elsewhere). If this grep returns hits outside `scripts/backfill_brain.py`, stop and re-scope this task — do not delete a script something else depends on.

- [ ] **Step 2: Delete the file**

```bash
git rm scripts/backfill_brain.py
```

- [ ] **Step 3: Verify the deletion doesn't break collection**

Run: `python -m pytest tests/test_sheets.py -q`
Expected: all pass — this suite doesn't import the script, it only asserts on `settings` shape (ADR-0013), so nothing here depends on the deleted file.

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: delete scripts/backfill_brain.py — crashes on removed GOOGLE_SHEETS_ID_SHORT/LONG (ADR-0013), migration already ran"
```

---

---

## Task 4: Gemini client — add an explicit request timeout

**Files:**
- Modify: `src/services/gemini.py:147-159`
- Modify: `tests/test_gemini_client.py`

**Major:** `_call_sync` (`src/services/gemini.py:147-159`) builds `genai.Client(api_key=api_key)` with no `http_options`, so the SDK's default timeout is `None` (no timeout). It runs via `asyncio.to_thread` (`_call_with_fallback`, line 169) on Python's shared default `ThreadPoolExecutor` — the same pool used by every other `asyncio.to_thread` call in the app (Drive, Sheets, GCS, GitHub). A hung Gemini request never returns a thread to the pool, so enough concurrent hangs starve unrelated I/O across the whole app. Fix by passing an explicit timeout via `types.HttpOptions` — 90 seconds balances Gemini's occasionally-slow vision calls against not hanging the pool indefinitely.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gemini_client.py`:

```python
# ---------------------------------------------------------------------------
# Test 8: _call_sync builds the client with an explicit HttpOptions timeout
# ---------------------------------------------------------------------------

def test_call_sync_sets_explicit_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """genai.Client must be constructed with a bounded http_options.timeout so a
    hung request can't hold a asyncio.to_thread worker forever."""
    from google.genai import types
    from src.services.gemini import _call_sync

    captured: dict[str, object] = {}

    class _FakeModels:
        def generate_content(self, *, model, contents, config=None):
            return _make_response('{"ok": true}')

    class _FakeClient:
        def __init__(self, *, api_key, http_options=None):
            captured["http_options"] = http_options
            self.models = _FakeModels()

    monkeypatch.setattr("google.genai.Client", _FakeClient)

    _call_sync("hello", api_key="k", model="gemini-2.5-flash")

    http_options = captured["http_options"]
    assert isinstance(http_options, types.HttpOptions)
    assert http_options.timeout == 90_000  # milliseconds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gemini_client.py::test_call_sync_sets_explicit_timeout -q`
Expected: FAIL — `captured["http_options"]` is `None` today.

- [ ] **Step 3: Pass an explicit `HttpOptions` timeout**

In `src/services/gemini.py`, add a module-level constant near the top (after the existing imports, before `_VISION_PROMPT`/other constants):

```python
_GEMINI_TIMEOUT_MS = 90_000  # 90s — bounds a hung request's hold on the shared to_thread pool
```

Then change `_call_sync`:

```python
def _call_sync(parts: object, *, api_key: str, model: str, schema: type | dict | None = None):
    """Sync generate_content call — run inside asyncio.to_thread by _call_with_fallback."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=_GEMINI_TIMEOUT_MS))
    if schema is not None:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
        )
        return client.models.generate_content(model=model, contents=parts, config=config)
    return client.models.generate_content(model=model, contents=parts)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gemini_client.py -q`
Expected: all pass (8 tests).

- [ ] **Step 5: Commit**

```bash
git add src/services/gemini.py tests/test_gemini_client.py
git commit -m "fix(gemini): bound genai.Client requests to a 90s timeout so a hang can't starve the shared thread pool"
```

---

---

## Task 6: Invalid Tailwind class sweep (WCAG contrast fix + dead classes)

**Files:**
- Modify: `web/app/mini/page.tsx:94`
- Modify: `web/app/(dashboard)/page.tsx:167`
- Modify: `web/components/brain-graph.tsx:231,232,282`

**Major:** Three unrelated files use Tailwind class names that don't exist in `web/tailwind.config.ts`'s token set, so they silently no-op (Tailwind drops unknown classes) instead of applying the intended style:
1. `web/app/mini/page.tsx:94` — `text-on-signal` and `disabled:bg-surface-raised` (config defines `onsignal`/`raised`, no hyphen, no `surface-` prefix). The CTA button text falls through to ambient ink-on-signal-orange, which measures ≈2.2:1 contrast — fails WCAG AA (needs 4.5:1 for body text).
2. `web/app/(dashboard)/page.tsx:167` — `rounded-card`, `bg-panel`, `shadow-card` on the "Connect Google" banner — none of these exist in the token set.
3. `web/components/brain-graph.tsx:231,232,282` — `hover:bg-surface-raised` (3 occurrences) should be `hover:bg-raised`.

- [ ] **Step 1: Fix `web/app/mini/page.tsx:94`**

Change:
```tsx
          className="mt-8 h-11 rounded-md bg-signal px-4 text-sm font-medium text-on-signal transition-ui hover:bg-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-surface-raised disabled:text-muted"
```
to:
```tsx
          className="mt-8 h-11 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-raised disabled:text-muted"
```

- [ ] **Step 2: Fix `web/app/(dashboard)/page.tsx:167`**

Change:
```tsx
      <section className="rounded-card border border-line bg-panel p-4 shadow-card">
```
to:
```tsx
      <section className="rounded-lg border border-line bg-surface p-4">
```

(This matches the card treatment used elsewhere on the same page, e.g. `SpaceCard.tsx`'s `rounded-lg border border-line bg-surface`.)

- [ ] **Step 3: Fix `web/components/brain-graph.tsx:231,232,282`**

At line 231-232, change:
```tsx
                    className={`inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium shadow-sm ring-1 transition-[background-color,color,opacity,transform] duration-150 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 ${
                      hidden
                        ? 'bg-transparent text-body ring-line hover:bg-surface-raised hover:text-ink'
                        : 'bg-surface-raised text-ink ring-line-strong hover:bg-line'
                    }`}
```
to:
```tsx
                    className={`inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium shadow-sm ring-1 transition-[background-color,color,opacity,transform] duration-150 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 ${
                      hidden
                        ? 'bg-transparent text-body ring-line hover:bg-raised hover:text-ink'
                        : 'bg-raised text-ink ring-line-strong hover:bg-line'
                    }`}
```

At line 282, change:
```tsx
      className="min-h-10 min-w-10 rounded-md bg-transparent px-3 text-xs font-medium text-body shadow-sm ring-1 ring-transparent transition-[background-color,color,opacity,transform] duration-150 hover:bg-surface-raised hover:text-ink active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none motion-reduce:active:scale-100"
```
to:
```tsx
      className="min-h-10 min-w-10 rounded-md bg-transparent px-3 text-xs font-medium text-body shadow-sm ring-1 ring-transparent transition-[background-color,color,opacity,transform] duration-150 hover:bg-raised hover:text-ink active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none motion-reduce:active:scale-100"
```

- [ ] **Step 4: Grep for any remaining invalid occurrences of these exact typo classes**

Run: `grep -rn "text-on-signal\|bg-surface-raised\|rounded-card\|bg-panel\b\|shadow-card" web --include="*.tsx"`
Expected: no output.

- [ ] **Step 5: Run the web test suite for the touched components**

Run: `npx vitest run web/app/mini web/app/\(dashboard\)/page.test.tsx web/components/brain-graph.test.tsx`

If `brain-graph.test.tsx` or a mini-app test doesn't exist, run the closest existing suite instead:
```bash
npx vitest run web/app/\(dashboard\)/page.test.tsx
```
Expected: all pass — these are pure class-string swaps with no behavior change.

- [ ] **Step 6: Commit**

```bash
git add web/app/mini/page.tsx "web/app/(dashboard)/page.tsx" web/components/brain-graph.tsx
git commit -m "fix(web): replace invalid Tailwind class names (text-on-signal, bg-surface-raised, rounded-card, bg-panel, shadow-card) with real tokens"
```

---

---

## Task 7: `TelegramToggle` — in-flight guard + unmount cleanup

**Files:**
- Modify: `web/components/doc-parser/telegram-toggle.tsx`
- Test: `web/components/doc-parser/telegram-toggle.test.tsx` (create if it doesn't exist)

**Major + Minor (same file, same fix shape):**
1. `persist()` (lines 13-18) has no in-flight guard or stale-response check — a rapid double-tap fires two overlapping `PUT` requests and the *last one to resolve* wins, regardless of which the user intended (may land the toggle in the state before the user's actual last click). `SpaceCard.tsx:45` (`disabled={deleting}`) shows the project's existing pattern: track an in-flight boolean and disable the trigger while a request is outstanding.
2. `startHold`'s `setTimeout` (line 23, held in the `timer` ref) is never cleared on unmount — if the component unmounts mid-hold (e.g. navigating away while pressing), the timer still fires later and calls `persist()` against an unmounted component's closure.

- [ ] **Step 1: Write the failing test for the in-flight guard**

Check whether `web/components/doc-parser/telegram-toggle.test.tsx` exists; if not, create it:

```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { TelegramToggle } from './telegram-toggle';

describe('TelegramToggle', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('disables the button while a persist request is in flight', async () => {
    let resolveFetch: (value: Response) => void;
    const pending = new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    });
    vi.spyOn(global, 'fetch').mockReturnValue(pending as unknown as Promise<Response>);

    render(<TelegramToggle jobId="j1" value="off" />);
    const button = screen.getByRole('button', { name: /telegram delivery/i });

    fireEvent.click(button);
    expect(button).toBeDisabled();

    resolveFetch!(new Response(JSON.stringify({ telegram_delivery: 'on' }), { status: 200 }));
    await waitFor(() => expect(button).not.toBeDisabled());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run web/components/doc-parser/telegram-toggle.test.tsx`
Expected: FAIL — the button has no `disabled` attribute today, so `expect(button).toBeDisabled()` fails right after the click.

- [ ] **Step 3: Add the in-flight guard and unmount-safe timer cleanup**

Replace the full component body:

```tsx
'use client';

import { useEffect, useRef, useState } from 'react';

type State = 'off' | 'on' | 'retroactive';

export function TelegramToggle({ jobId, value = 'off' }: { jobId: string; value?: State }) {
  const [state, setState] = useState<State>(value);
  const [holding, setHolding] = useState(false);
  const [pending, setPending] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false); // hold completed → swallow the trailing click
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, []);

  async function persist(next: State) {
    if (pending) return; // in-flight guard — a rapid double-tap must not fire overlapping PUTs
    setPending(true);
    try {
      const res = await fetch(`/api/parsed/${jobId}/telegram-delivery`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ state: next }) });
      if (!res.ok) { console.error(`telegram-delivery PUT failed: ${res.status}`); return; } // failed PUT → keep state, surface so it's not silent
      const data = await res.json();
      if (mounted.current) setState(data.telegram_delivery);
    } finally {
      if (mounted.current) setPending(false);
    }
  }

  function startHold() {
    setHolding(true);
    fired.current = false;
    timer.current = setTimeout(() => { fired.current = true; persist('retroactive'); }, 1500);
  }
  function cancelHold() {
    setHolding(false);
    if (timer.current) clearTimeout(timer.current);
  }

  const isOff = state === 'off';

  return <button type="button" aria-label={`Telegram delivery ${state}`} aria-pressed={state !== 'off'} disabled={pending} onClick={(e) => { e.preventDefault(); if (fired.current) { fired.current = false; return; } persist(state === 'off' ? 'on' : 'off'); }} onPointerDown={startHold} onPointerUp={cancelHold} onPointerLeave={cancelHold} className={`relative flex h-[26px] w-[26px] items-center justify-center rounded-full border transition-ui disabled:cursor-not-allowed disabled:opacity-60 ${isOff ? 'border-line' : 'border-telegram-blue'} ${holding ? 'doc-telegram-hold' : ''}`}>
    {/* Official Telegram mark (simpleicons "telegram"): a disc + plane core. On = brand
        #26A5E4 / #ffffff; off = status-cancelled / cancelled-tint so it reads as inactive.
        The disc and plane carry the affordance, so the icon needs no currentColor. */}
    <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
      <circle cx="12" cy="12" r="12" className={`transition-ui ${isOff ? 'fill-status-cancelled' : 'fill-telegram-blue'}`} />
      <path className={`transition-ui ${isOff ? 'fill-status-cancelled-tint' : 'fill-white'}`} d="M16.906 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.139-5.061 3.345-.479.329-.913.489-1.302.481-.428-.009-1.252-.242-1.865-.44-.752-.244-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  </button>;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run web/components/doc-parser/telegram-toggle.test.tsx`
Expected: PASS.

- [ ] **Step 5: Run any consuming pages' tests for regressions**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/page.test.tsx" "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: all pass — `TelegramToggle` is used in both pages with the same props shape.

- [ ] **Step 6: Commit**

```bash
git add web/components/doc-parser/telegram-toggle.tsx web/components/doc-parser/telegram-toggle.test.tsx
git commit -m "fix(web): guard TelegramToggle against overlapping requests and unmount-after-hold timer leak"
```

---

---

## Task 8: `doc-parser/[id]/page.tsx` — `load()` cancellation guard

**Files:**
- Modify: `web/app/(dashboard)/doc-parser/[id]/page.tsx:126-136`
- Test: `web/app/(dashboard)/doc-parser/[id]/page.test.tsx`

**Minor:** `load()` (lines 126-133) and its `useEffect` (134-136) have no cancellation guard. If `id` changes quickly (e.g. fast client-side nav between two doc-parser detail pages) or the component unmounts mid-fetch, a stale response can land after a fresher one and clobber `job`/`outs` with outdated data.

- [ ] **Step 1: Write the failing test**

Add to `web/app/(dashboard)/doc-parser/[id]/page.test.tsx`:

```tsx
it('does not apply a stale response after id changes', async () => {
  let resolveFirst: (v: unknown) => void;
  const firstJob = new Promise((resolve) => { resolveFirst = resolve; });

  const fetchMock = vi.spyOn(global, 'fetch').mockImplementation((url: string) => {
    if (String(url).includes('/api/jobs/first')) {
      return firstJob.then(() => new Response(JSON.stringify({ id: 'first', title: 'First' }))) as unknown as Promise<Response>;
    }
    if (String(url).includes('/api/jobs/second')) {
      return Promise.resolve(new Response(JSON.stringify({ id: 'second', title: 'Second' })));
    }
    return Promise.resolve(new Response(JSON.stringify([])));
  });

  const { rerender } = render(<DocDetail params={{ id: 'first' }} />);
  rerender(<DocDetail params={{ id: 'second' }} />);
  await waitFor(() => expect(screen.getByText('Second')).toBeInTheDocument());

  resolveFirst!(undefined); // first request resolves AFTER the second one already rendered
  await new Promise((r) => setTimeout(r, 0));

  expect(screen.getByText('Second')).toBeInTheDocument(); // must not be clobbered back to "First"
  fetchMock.mockRestore();
});
```

(Adjust the mocked URLs/param shape to match how `useParams` is exercised in the file's existing tests — follow whatever mocking convention `web/app/(dashboard)/doc-parser/[id]/page.test.tsx` already uses for `next/navigation`'s `useParams`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: FAIL — the stale `first` response overwrites `job` back to "First" after the second one already landed.

- [ ] **Step 3: Add the cancelled-flag guard**

In `web/app/(dashboard)/doc-parser/[id]/page.tsx`, change:

```tsx
  async function load() {
    const [j, o] = await Promise.all([
      fetch(`/api/jobs/${id}`).then((r) => r.json()),
      fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
    ]);
    setJob(j);
    setOuts(o);
  }
  useEffect(() => {
    load();
  }, [id]);
```

to:

```tsx
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [j, o] = await Promise.all([
        fetch(`/api/jobs/${id}`).then((r) => r.json()),
        fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
      ]);
      if (cancelled) return;
      setJob(j);
      setOuts(o);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id]);
```

Also update `runAction`'s `await load();` call (line 148) to no longer call the now-inline `load` — since `load` moved inside the effect, `runAction` needs its own re-fetch trigger. Add a small reload helper alongside the effect instead:

```tsx
  const [reloadKey, setReloadKey] = useState(0);
  useEffect(() => {
    let cancelled = false;
    async function load() {
      const [j, o] = await Promise.all([
        fetch(`/api/jobs/${id}`).then((r) => r.json()),
        fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
      ]);
      if (cancelled) return;
      setJob(j);
      setOuts(o);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);
```

and in `runAction`, replace `await load();` with `setReloadKey((k) => k + 1);`.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add "web/app/(dashboard)/doc-parser/[id]/page.tsx" "web/app/(dashboard)/doc-parser/[id]/page.test.tsx"
git commit -m "fix(web): guard doc-parser detail load() against stale-response races"
```

---

---

## Task 11: Add a global error boundary (`web/app/error.tsx`)

**Files:**
- Create: `web/app/error.tsx`

**Major:** No `error.tsx`/`global-error.tsx` exists anywhere under `web/app/`. `web/app/(dashboard)/page.tsx:249-252` wraps the feed in `<Suspense fallback={null}>` with no error boundary above it — any render-time throw in the tree (a bad API shape, a hook throwing) crashes to Next.js's default unstyled error screen instead of the app's dark-plate design system.

- [ ] **Step 1: Create `web/app/error.tsx`**

Next.js App Router route-level error boundaries are Client Components exporting a default function with `{ error, reset }` props (per `next/error` conventions — confirm current API shape via context7/Next.js docs for the installed Next version in `web/package.json` before finalizing prop types, since the exact reset-signature has been stable across recent major versions but is worth a live check).

```tsx
'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <section className="w-full max-w-md rounded-lg border border-line bg-surface p-6 text-center">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-status-error">
          Error
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm leading-6 text-body">
          The page hit an unexpected error. You can try again, or head back to the feed.
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised"
          >
            Back to feed
          </a>
        </div>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Write a smoke test**

Create `web/app/error.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import GlobalError from './error';

describe('GlobalError', () => {
  it('renders the fallback and calls reset on click', () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error('boom')} reset={reset} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 3: Run the test**

Run: `npx vitest run web/app/error.test.tsx`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add web/app/error.tsx web/app/error.test.tsx
git commit -m "feat(web): add app-level error boundary styled to the design system"
```

---

---
