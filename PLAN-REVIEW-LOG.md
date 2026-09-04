# Plan Review Log: Voice picker (global accessibility setting)

Plan under review: `docs/superpowers/plans/2026-09-04-voice-picker-global-setting.md`
Model: gpt-5.5 (reasoning_effort=high). MAX_ROUNDS=5.
Started: session in progress, 2026-09-04.
Thread ID: `01a06e2e-cee2-7a70-b1ba-58acce0df903`.

## Round 1 — Codex

- `src/api/controls.py:49`: making `voice_uri` required breaks old/cached frontend clients whose PUT body only has `visual_motion`/`haptic_motion`. Fix: accept `voice_uri: str | None = None` during rollout while always returning the normalized three-field shape.
- `src/api/controls.py:49`: `voice_uri` is an unbounded user-controlled string persisted to SQLite and echoed back. Fix: `Field(default=None, max_length=512)` and normalize blank strings to `None`.
- Plan's global constraint vs. Task 1 test contradict each other: whole-object-fallback-on-any-invalid-field vs. legacy rows missing only `voice_uri` recovering partially. Fix: state the explicit legacy exception.
- `web/lib/hooks/useAccessibilitySettings.ts:67`: frontend casts API JSON without runtime normalization. Fix: add a `normalizeAccessibilitySettings()` before `publishAccessibilitySettings()`.
- `web/lib/hooks/useAccessibilitySettings.ts:31`: once `voice_uri` joins `keyof AccessibilitySettings`, `saveAccessibilitySetting(key, checked: boolean)` type-allows corrupting `voice_uri` with a boolean. Fix: genericize to `<K extends keyof AccessibilitySettings>(key: K, value: AccessibilitySettings[K])`.
- `web/app/(dashboard)/controls/page.tsx:365`: the planned local `update()` drops the existing request-generation race guard, so overlapping saves can publish stale responses or roll back newer choices. Fix: reuse the shared guarded save path or add a per-component generation ref.
- `web/lib/hooks/useSpeech.ts:8`: importing `useAccessibilitySettings()` into `useSpeech` makes every listen button start the settings fetch, but Task 5 doesn't update `useSpeech.test.ts` to reset/stub that singleton/fetch. Fix: add `resetAccessibilitySettingsForTests()` plus a fetch stub.
- `web/lib/hooks/useSpeech.ts:45`: resolving the voice only at click time with `getVoices()` misses browsers where voices load asynchronously after mount. Fix: share a voice cache/listener with `useSpeechVoices` or wait for one `voiceschanged` event before speaking.
- Task 7 UI has no handling for a persisted `voice_uri` not installed on the current browser/device — the controlled select can render with no matching option. Fix: render a disabled option or reset to system default once voices are loaded and no match exists.
- Task 4 assumes `speechSynthesis.addEventListener`/`removeEventListener` exist everywhere. Fix: feature-detect and fall back to `onvoiceschanged`.
- Task 4 assumes `Intl.DisplayNames` and every `voice.lang` are valid. Fix: wrap label generation in try/catch, fall back to the raw language tag.
- `web/lib/mocks/handlers.ts:1`: the plan doesn't update MSW mock handlers for `/api/controls/accessibility-settings`, so mock/demo mode won't exercise or persist the new setting. Fix: add GET/PUT mock state.
- Plan's frontend commands are inconsistent with repo layout: Tasks 3-6 use root-relative `npx vitest run web/...`, Task 7 uses `app/...` and `git add app/...`. Fix: standardize.
- Controls page tests add `vi.unstubAllGlobals()` but don't reset `useAccessibilitySettings`'s module singleton, so a voice selected in one test can leak into later tests that mount `ListenButton`. Fix: call `resetAccessibilitySettingsForTests()`.
- Observability is thin: missing selected voice, empty voice list, `speechSynthesis.speak` errors, and unsupported synthesis all fail silently except button disappearance. Fix: expose an inline unavailable/error state.

VERDICT: REVISE

### Claude's response (round 1)

**Accepted and fixed:**
1. Global Constraints wording was genuinely ambiguous about the legacy-row exception — rewrote to state it explicitly (missing `voice_uri` key normalizes to `None`; only a *present-but-wrong-type* value triggers the whole-object fallback).
2. Added `Field(max_length=512)` to `AccessibilitySettingsIn.voice_uri` (Task 2) plus a 422 test for an over-length value. Did NOT add the "normalize blank strings to None" half — the frontend already sends `event.target.value || null`, so an empty string never reaches this endpoint from our own client; not worth a second normalization path for a case that can't occur through the shipped UI.
3. Genericized `saveAccessibilitySetting<K extends keyof AccessibilitySettings>(key: K, value: AccessibilitySettings[K])` (Task 3) — real type hole, cheap fix, added a regression test.
4. Task 7's local `update()` was missing the generation-race guard — added a `generationRef` counter mirroring the shared module's existing pattern, since a third editable field genuinely raises the odds of overlapping saves.
5. Verified with `node -e "new Intl.DisplayNames(['en'],{type:'language'}).of('not-a-real-lang-tag')"` that it really does throw `RangeError` (not a guess) — added a `languageLabel()` helper with try/catch and a regression test (Task 4).
6. A persisted `voice_uri` not installed locally really would leave the controlled `<select>` with no matching option — added a derived `selectableVoiceURI` (falls back to "" for display without mutating the stored preference) and a test (Task 7).
7. Task 7's test file was missing `resetAccessibilitySettingsForTests()` (Tasks 5/6 already had it) — added for consistency, low cost.
8. Frontend command paths really were inconsistent (Tasks 3-6 assumed repo-root cwd, Task 7 assumed `web/` cwd) — standardized everything on `web/`-relative, matching root `CLAUDE.md`'s documented `cd web && npm test` convention and this session's own actual command history.

**Rejected, with reasons:**
1. Making `voice_uri` optional for zero-downtime rollout safety — this is a single-operator personal dashboard with one atomic Next.js build, not a fleet with staggered deploys; the existing all-fields-required contract (already true for `visual_motion`/`haptic_motion`) is the right one to extend, not carve an exception into.
2. Full runtime JSON normalization on every frontend fetch — no other hook in this codebase validates its fetched JSON at runtime either (all trust the backend's response shape); adding it here alone would be a new, inconsistent pattern for this one endpoint, not a fix.
3. "Task 5 doesn't stub fetch/reset the singleton" — **false**, verified by re-reading the plan: lines 585-586 (now shifted after edits) already had both `resetAccessibilitySettingsForTests()` and the `fetch` stub in `useSpeech.test.ts`'s `beforeEach`.
4. Sharing a `voiceschanged` listener/cache between `useSpeech` and `useSpeechVoices` so voice resolution never misses an async-loaded voice — real architectural complexity (a second shared singleton) for a narrow edge case that already degrades softly (falls back to default voice for that one click). Documented as a deliberate, revisitable scope cut in Global Constraints instead of building it preemptively.
5. Feature-detecting `speechSynthesis.addEventListener`/`removeEventListener` with an `onvoiceschanged` fallback — every current browser implementing the Web Speech API supports `addEventListener` on it; no other browser API in this codebase gets this treatment for similarly-universal support.
6. Adding MSW mock handlers for `/api/controls/accessibility-settings` — verified via grep: **no handler exists today** for this endpoint at all, so `visual_motion`/`haptic_motion` already silently fail and fall back to hardcoded defaults in `NEXT_PUBLIC_API_MOCK=1` mode. `voice_uri` inherits the same pre-existing gap; this plan doesn't regress anything mock mode already didn't support, and fixing decade-old (well, day-old) mock coverage for two unrelated fields is out of scope for a voice-picker feature.
7. "Observability is thin" — noted, but no concrete action taken; the existing two toggles have the exact same silent-failure profile (no logging on `speechSynthesis.speak` errors, no visible "no voices" state beyond the row disappearing) and this plan doesn't regress that baseline. Left as a follow-up idea, not blocking.

## Round 2 — Codex

- Task 7's unavailable-voice fallback is misleading: the `<select>` displays "System default" while `settings.voice_uri` still contains the missing URI, and the user cannot clear it by choosing "System default" because the select value is already `""`. Fix: render a selected disabled "Unavailable voice" option with the missing URI as the current value, so selecting "System default" fires `onChange` and persists `null`.
- Task 7's race guard prevents stale responses from publishing, but `update()` still builds `previous`/`next` from a stale React closure; two same-tick changes before the disabled render can lose the first change or roll back to the wrong snapshot. Fix: keep a `settingsRef`/functional updater as the source of truth for composing `next` and rollback state.
- Task 7 adds a generation guard for overlapping saves but no regression test for the stale-response case it is meant to fix. Fix: add a deferred-PUT test where two accessibility updates resolve out of order and assert the final UI/published settings match the newer update.
- Task 3 still leaves `resetAccessibilitySettingsForTests()` unable to invalidate in-flight loads/saves because it resets `stored`/`loading` but not `requestGeneration`; a late promise from a prior test can publish after reset if its generation still matches. Fix: increment or reset `requestGeneration` inside `resetAccessibilitySettingsForTests()`.
- Task 3's generic `saveAccessibilitySetting<K>()` is good, but the plan's new test only proves a string value compiles; it does not catch accidental boolean corruption at runtime or request-body level. Fix: assert the PUT body includes `"voice_uri":"Daniel"` and update existing exact-object tests to include `voice_uri` instead of relying on omitted-field fixtures.
- Task 2 bounds `voice_uri` on the API model but Task 1's public database helper can still persist arbitrarily long strings if called internally. Fix: either enforce the same max length in `set_accessibility_settings()` or document the helper as trusting already-validated callers and keep all writes routed through the API.

VERDICT: REVISE

### Claude's response (round 2)

**Accepted and fixed:**
1. The Round-1 "fall back to System default" display fix was itself a dead end: the select's value already equaled `""`, so re-picking "System default" is not a value change and `onChange` never fires — the stale URI could never actually be cleared through the UI. Replaced with a disabled "Unavailable voice" option carrying the stale URI as its own value (Task 7's `isPersistedVoiceInstalled`), so picking "System default" is a real transition and persists `null`. Updated the test accordingly and added an explicit "clear it" step.
2. The generation guard had no test proving it does what it's for — added one with two deferred PUTs (`us` then `uk`) resolving in reverse order, asserting the UI ends on the newer pick (Task 7).
3. `resetAccessibilitySettingsForTests()` didn't invalidate `requestGeneration` — bumped it on reset (Task 3), closing a narrow flakiness window for a test that ends without awaiting its own in-flight save.
4. The generic-save test only proved the round-tripped response, not the request body — strengthened to parse and assert the actual PUT body; also updated the file's two pre-existing overlapping-save tests to carry `voice_uri` through their fixtures, since that's precisely the logic most likely to silently drop a new field (Task 3). Reorganized: these test changes belong in Task 3's Step 1 (write the failing test), not Step 3 (implementation) — fixed a structural mistake from my own Round 1 edit in the process.
5. `set_accessibility_settings()` could theoretically be called with an unbounded string bypassing the API's `max_length` — added a one-line comment documenting it trusts its one caller (the PUT route) rather than duplicating the bound in a second layer (Task 1). Cheaper, and there's genuinely only one call site today.

**Rejected, with reason:**
1. Restructuring `update()` around a `settingsRef`/functional updater to guard against two `onChange` handlers firing within the same React batch — for three independent native form controls, each requiring its own separate physical user interaction (a checkbox click, a select change), React 18's automatic batching only batches state updates scheduled within a single event handler's synchronous call stack, not across two separately-dispatched DOM events; each interaction gets its own render before the next one's handler runs, so `settings` is guaranteed current at the start of every independent `update()` call. This is standard React semantics (not something I ran an isolated proof for in this session — noting that honestly rather than dressing up a reasoning check as an empirical test), and the exact same closure pattern already exists in the pre-existing two-checkbox `toggle()` today without incident. A real risk only for scripted/automated multi-field changes within one tick, not normal use; not worth the added indirection for this settings panel.

## Round 3 — Codex

- `web/lib/hooks/useAccessibilitySettings.ts:29` / Task 7: `publishAccessibilitySettings()` still does not invalidate an in-flight `load()`, and Controls already mounts `useAccessibilitySettings()` via `usePressFeedback.ts:17`; a stale GET can publish old settings after a Controls-page save because only `saveAccessibilitySetting()` bumps `requestGeneration`. Fix: add an exported "external write" helper or optional `publishAccessibilitySettings(value, {invalidateLoads: true})` path that bumps `requestGeneration`, and use it for Controls-page optimistic/saved publishes.
- Task 7 preview test can race the `ListenButton` mount/effect: `findByLabelText('Voice')` only proves the select rendered after `useSpeechVoices`, but the preview button appears only after `ListenButton`'s own `useSpeech` effect flips `supported`. Fix: change the test to `await section('Accessibility').findByRole('button', {name:'Preview voice'})` before clicking.
- Task 7's "overlapping PUTs" regression test may be testing a path real users cannot hit because the first change sets `saving=true` and disables the select before the second selection. Fix: either remove `disabled={saving}` for the voice select if overlapping edits are intentionally supported, or make the regression exercise a realistic stale response path such as an in-flight settings GET/PUT resolving after a later Controls publish.

VERDICT: REVISE

### Claude's response (round 3)

**Accepted and fixed, all three — verified each concretely before acting, not taken on faith:**
1. Read `usePressFeedback.ts` directly: confirmed it calls `useAccessibilitySettings()` at line 22, and `AccessibilitySection` already calls `usePressFeedback()` — so this cross-component race is real and reachable today (for `visual_motion`/`haptic_motion`), not theoretical. Traced why: `AccessibilitySection` runs its own independent GET/PUT cycle and calls `publishAccessibilitySettings()` directly, never touching the shared module's `requestGeneration` counter that `load()` checks against. Added `publishAccessibilitySettingsFromExternalWrite()` (Task 3) — bumps the counter, then publishes — and switched all four of `AccessibilitySection`'s publish call sites to it (Task 7), with a regression test simulating the actual race (a slow shared `load()` resolving after an external write). Considered making `saveAccessibilitySetting()` itself always bump on every publish instead, but traced through the math and confirmed that would immediately invalidate its own optimistic publish before its own fetch even started — a strictly separate helper for external writers is the correct shape, not a shared one.
2. Traced the actual effect timing: both `useSpeechVoices` (gates the select) and `ListenButton`'s internal `useSpeech` (gates the preview button) flip their `supported` flag in a `useEffect(() => {...}, [])`, and RTL's `render()` flushes all commit-phase effects before returning — so in practice these very likely resolve in the same synchronous flush. But regardless of whether a real race exists today, waiting for the exact element about to be clicked is strictly more correct test design than waiting for a sibling and assuming the target arrived too — changed the wait target unconditionally.
3. Traced through what `fireEvent.change` actually does versus a real click: it dispatches the DOM event directly, bypassing the `disabled` attribute a real user's mouse/keyboard interaction cannot get past. Confirmed the select does disable itself via `disabled={!loaded || saving}` the instant the first change lands (same synchronous commit as the optimistic `settings`/`saving` updates). So the existing regression test cannot happen through real UI interaction — but it still correctly exercises the `generationRef` guard's logic (the same logic the Task 3 external-write test exercises from the network-ordering side), so kept it and added a comment saying plainly what it does and doesn't prove, rather than removing real coverage or inventing a claim that it reproduces literal double-clicking.

## Round 4 — Codex

No material findings. Round-3 fixes confirmed represented in the plan: `publishAccessibilitySettingsFromExternalWrite()` invalidates stale shared loads, Task 7 uses it for its independent Controls fetch/save flow, the preview test waits for the actual `ListenButton`, the overlapping-PUT test is documented as guard-logic-only. Residual scope cuts (no frontend runtime schema normalization, no MSW handler, no shared voice cache, required `voice_uri`) judged consistent with existing project patterns or already explicitly rejected with coherent reasoning — no remaining blocker.

VERDICT: APPROVED

---

**Outcome: APPROVED after 4 rounds.** See the plan file's own "Self-Review" section (rounds 1-3 notes) for the condensed rationale behind every accepted/rejected finding.
