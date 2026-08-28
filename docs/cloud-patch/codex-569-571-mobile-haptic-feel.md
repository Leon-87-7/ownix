# Codex prompt — implement issues #569–#571 (mobile haptic button feel)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0053-mobile-haptic-button-feel.md` — **authoritative**. Records
   why real vibration is Android/Chromium-only (WebKit has never implemented
   the Vibration API, on any Apple platform, in any version — confirmed
   against current browser-support docs, not memory), why the rollout is
   opportunistic rather than a big-bang button-consolidation, and why
   real vibration is reserved for outcome-bearing actions instead of every
   press. If anything below disagrees with the ADR, the ADR wins.
2. GitHub issue #568 (`gh issue view 568 --repo Leon-87-7/ownix`) — the
   parent PRD. Its User Stories are the product intent; its Implementation/
   Testing Decisions sections are restated more precisely below with
   verified line numbers.
3. `CLAUDE.md` (repo root) — backend test/lint commands
   (`python -m pytest tests -q`, `ruff check src/`; **never** through the
   `rtk` hook, `.claude/rules/rtk-tests.md`) and the migration mechanism
   (`PRAGMA user_version` in `src/database.py`) — **not needed for this
   batch**, see the migration-free decision below.
4. `web/CLAUDE.md` — component layout (`web/components/<area>/<kebab-name>.tsx`,
   colocated `.test.tsx`, no barrel files) and the web test/lint commands
   (`npm test` / `npm run test:run`, `npm run lint`, `npm run build`, all
   run from `web/`).
5. The specific files cited per slice below — line numbers are as of this
   writing (verified directly, not pulled from memory); find the symbol by
   name if a line has drifted.
6. GitHub issues #569, #570, #571
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each issue's acceptance
   criteria are the definition of done for that slice. Two of #571's
   acceptance-criteria bullets need a correction against current code —
   flagged explicitly in that slice's section below, don't skip it.

## Key decisions already made (do not relitigate)

- **Layered haptics, not a single mechanism.** A visual "press" effect
  (`pointerdown`/`touchstart`, touch/coarse-pointer only) is the actual
  cross-platform feel; real `navigator.vibrate()` is a separate, explicitly-
  called layer reserved for outcome-bearing moments, gated by
  `'vibrate' in navigator` feature detection — never platform/browser-sniffed.
- **No new DB migration.** Accessibility settings reuse the existing generic
  per-user `user_settings` key/value table already in `src/database.py` —
  see the `brain_links_view` pattern below, which this mirrors exactly.
- **v1 rollout is opportunistic, not exhaustive.** Only the files already
  listed in issue #570's acceptance criteria get the press hook in this
  batch. Consolidating every button/anchor in the dashboard into one shared
  component is explicitly deferred (ADR-0053) — do not attempt it here, and
  do not touch any interactive-element file outside the ones named below.
- **Real vibration is press-hook-independent.** The vibration utility is
  called explicitly at outcome sites; it is never wired as a side effect of
  the press hook. A routine nav/filter/tab tap must never vibrate, and a
  background job-status change with no button pressed must never vibrate.
- **Accessibility setting is the single source of truth, once loaded.**
  Both the press hook (Visual motion) and the vibration utility (Haptic
  motion) read one hook that seeds from the live `prefers-reduced-motion`
  query (Visual motion only — Haptic motion has no OS equivalent, defaults
  to enabled) and then treats the stored per-user value as authoritative
  once it has loaded.

## Work order

Three slices in dependency order — #569 is the foundation both others read
from; #570 must land before #571 (they touch overlapping files: the press
hook's markup changes and the vibration calls both land inside the same
handler bodies in `submit-job.tsx` and `jobs/[id]/page.tsx`).

### 1. #569 — Accessibility settings: storage, API, Settings UI toggle

**Backend — mirror the `brain_links_view` pattern exactly**
(`src/database.py:1657–1691`), not the plain-boolean `recovery_telegram_notifications`
pattern (`:1694–1703`) — this setting is JSON-shaped and explicitly meant to
grow more keys later, same as `brain_links_view`'s `{order, size}` shape:

- Add a new key constant (e.g. `_ACCESSIBILITY_SETTINGS_KEY = "dashboard_accessibility_settings"`)
  and `get_accessibility_settings(chat_id) -> dict` /
  `set_accessibility_settings(chat_id, *, visual_motion: bool, haptic_motion: bool) -> dict`,
  built on the existing generic `get_user_setting`/`set_user_setting`
  (`src/database.py:1636–1654` — do not add new SQL, these two functions are
  the whole persistence layer). Default value when unset:
  `{"visual_motion": True, "haptic_motion": True}`. Normalize malformed/
  partial stored JSON back to defaults on read, same defensive shape as
  `_normalize_brain_links_view` (`:1663–1672`) — a bad or missing key must
  not raise.
- **API** — add `GET`/`PUT /api/controls/accessibility-settings` to
  `src/api/controls.py`, mirroring the existing `RecoverySettingsIn` /
  `get_recovery_settings` / `update_recovery_settings` trio
  (`:47–49`, `:185–198`) — same `chat_id = request.state.user["id"]` scoping,
  same shape (a Pydantic `AccessibilitySettingsIn` with both booleans, a
  GET returning the dict, a PUT accepting and returning it).

**Frontend**

- New "Accessibility" `<Section>` on the Settings page
  (`web/app/(dashboard)/controls/page.tsx`) — add it alongside the existing
  `<Section>` blocks in the `ControlsPage` export (`:563–636`), using the
  same `Section` wrapper (`:526–561`). Two checkboxes, "Visual motion" and
  "Haptic motion", following `RecoveryTab`'s exact fetch/optimistic-update/
  rollback shape (`:363–452`): `useEffect` GET on mount, `apiPut` on toggle
  (`web/lib/fetch-utils.ts:163`) with the previous value restored and an
  error message shown on failure — same UX as `RecoveryTab`'s `toggle()`
  (`:403–427`).
- New hook exposing the resolved settings — the single source of truth
  slices #570/#571 will read from. It composes: the stored value (once the
  GET above resolves) as authoritative, falling back to the live
  `prefers-reduced-motion` query for `visual_motion` before that (mirror
  `useReducedMotion`'s media-query pattern, `web/lib/hooks/useReducedMotion.ts`
  — full file, 18 lines, safe-by-default `useState(true)` seed) and to
  `true` for `haptic_motion` (no OS equivalent). Name/place it under
  `web/lib/hooks/` next to `useReducedMotion.ts`.
- The two new checkboxes get the press-feedback hook too, same as every
  other control in scope — see slice #570 (this is why #570 depends on
  #569: the checkboxes need to exist first).

### 2. #570 — Visual press-feedback hook + v1 rollout

- New reusable hook (`web/lib/hooks/`, e.g. `usePressFeedback`) — fires on
  `pointerdown`/`touchstart` (not `click`), gated to coarse-pointer/touch
  input only, reads #569's accessibility hook and no-ops when
  `visual_motion` is false. Model its test on
  `web/lib/hooks/useVisualViewport.ts` + `useVisualViewport.test.ts` — that
  pair is this codebase's existing template for a hook that reads/reacts to
  a browser API and is tested by faking the global (`window.matchMedia`,
  `PointerEvent`) rather than mounting a consumer component. Note:
  `useReducedMotion.ts` currently has **no** colocated test — don't treat
  its absence as "no test needed," write one for the new hook regardless.
- Wire the hook onto the v1 rollout set — the **15 files** that currently
  carry the ad hoc `active:scale-[0.96] motion-reduce:active:scale-100`
  press affordance (verified via a direct grep just now, not the earlier
  estimate in the issue body — trust this list):
  `web/components/feed/submit-job.tsx`, `web/components/ui/dialog.tsx`,
  `web/components/ui/ghost-button.tsx`, `web/components/ui/sheet.tsx`,
  `web/components/shell/sidebar.tsx`,
  `web/components/shell/telegram-login-widget.tsx`,
  `web/components/landing/mobile-onboarding-stepper.tsx`,
  `web/components/feed/links-table.tsx`,
  `web/components/feed/submit-url-form.tsx`,
  `web/components/doc-parser/doc-upload-panel.tsx`,
  `web/components/doc-parser/document-source-chip.tsx`,
  `web/components/brain/brain-graph.tsx`, `web/app/logout/page.tsx`,
  `web/app/(dashboard)/jobs/[id]/page.tsx`,
  `web/app/(dashboard)/doc-parser/[id]/page.tsx` — plus the `GhostButton`
  primitive's 6 real call sites (`web/components/ui/ghost-button.tsx`
  itself already covered above; its consumers: `web/app/page.tsx`,
  `web/components/feed/submit-job.tsx` (already in the 15), `web/components/landing/mobile-onboarding-stepper.tsx` (already in the 15),
  `web/components/landing/onboarding-stepper.tsx`,
  `web/components/shell/app-header.tsx`,
  `web/app/(dashboard)/feed/page.tsx`) — and the two new Accessibility
  checkboxes from #569.

  Do not touch any interactive element outside this named set, including
  the separate `/intake` conversational console
  (`web/app/intake/*`, not `web/app/intake/share/page.tsx` which redirects
  and has no interactive controls of its own) — it's a real page but not
  part of this v1 surface.
- The "+" intake trigger the PRD calls out by name is confirmed at
  `web/app/(dashboard)/feed/page.tsx:548–554` — a `GhostButton` with
  `onClick={openIntake}`, `sm:hidden` (mobile-only), already inside the v1
  set above. Its panel is `submit-job.tsx`'s `intakeOpen` `Sheet`
  (`:822–857`, `SheetActionButton` at `:287–316` carries the existing
  `active:scale-[0.96]` at line 302) plus the Submit URL / Ingest Link
  dialogs it launches (`submit-url-form.tsx`, and the `GhostButton` at
  `submit-job.tsx:796–803`) — all already in the file list above.
- Regression: `prefers-reduced-motion` handling already present in these
  files (the `motion-reduce:active:scale-100` fallback) must keep working —
  the new hook layers on top, it does not replace existing CSS
  reduced-motion fallbacks.

### 3. #571 — Real vibration on outcome-bearing actions

New, separate vibration utility (feature-detected `'vibrate' in navigator`,
reads #569's `haptic_motion`, never called from the press hook), wired into
outcome sites **within the same v1 file set from #570 only** — do not expand
scope to reach an outcome site living outside those 15+6 files.

Verified in-scope outcome sites:

- **Intake submit** — `web/components/feed/submit-job.tsx`: `submitJob`
  (`:477–528`, success sets `lastAccepted` + closes the dialog at `:504–518`,
  failure sets `error` at `:519–522`) and `submitOneLink`
  (`:533–577`, per-token success/error already tracked in `batchResults`,
  `:541–563` vs `:564–573`) — vibrate on each function's success/failure
  branch.
- **Destructive confirm** — `web/app/(dashboard)/jobs/[id]/page.tsx`:
  `handleDelete` (`:1164`, state at `:1065–1066` — `deleting`/`deleteFailed`),
  behind the `ConfirmDialog` at `:1318–1350` — vibrate on the delete
  outcome (success navigates away/updates state; failure sets
  `deleteFailed`, surfaced at `:1351–1354`).
- **In-flight job action** — the "Run Gemini" enrichment trigger on the
  same page (button around `:1000`, status flips to `'enriching'` at
  `:1227`/`:1235`) — vibrate on its resolution (poll-to-completion success
  vs. failure), not on the click that starts it.

**Correction against #571's written acceptance criteria — read before
starting, don't silently skip or silently over-scope:**

- *"The Android share-target intake path vibrates on accept/reject."*
  Verified: `web/app/intake/share/page.tsx` only redirects to
  `/intake?url=...` (or `/login`, preserving the URL) — it has no submit
  button and never itself accepts/rejects a URL. The actual accept/reject
  happens on the `/intake` console page, which is **outside the v1 file
  set** (not one of the 15+6 files above). **Do not implement vibration on
  `/intake` in this batch** — leave this specific bullet unaddressed and
  say so in your summary; wiring it would mean expanding the v1 surface,
  which ADR-0053 explicitly scoped out of this pass.
- *"Cancelling or retrying an in-flight job vibrates."* Verified: the
  cancel/retry actions the PRD means live in
  `web/components/feed/recovery-panel.tsx`, which is **not** one of the 15
  `active:scale-[0.96]` files and has no press-feedback hook from #570 to
  hang a vibration call off of. **Do not implement vibration on
  `recovery-panel.tsx` in this batch** for the same reason — note it as
  unaddressed, same as above. The "Run Gemini" enrichment trigger above is
  the one genuinely in-scope in-flight action; implement that one.

### Tests

Backend — `python -m pytest tests -q` (never via the `rtk` hook):

- `tests/test_database.py` — a roundtrip + normalization test for the new
  accessibility-settings functions, same shape as
  `test_brain_links_view_roundtrip_and_normalizes_invalid_values`
  (`:1006–1037`): write valid, read back unchanged; write malformed JSON
  directly via `set_user_setting`, confirm the read falls back to defaults
  without raising.
- `tests/test_controls_validation.py` — route-level tests using the
  existing `controls_client` fixture (`:15–33`, wraps `controls_router` in
  a bare `TestClient`, no full app/auth needed): GET returns defaults when
  unset, PUT persists and a subsequent GET reflects it, an invalid payload
  is rejected.

Frontend — `npm run test:run` from `web/` (Vitest + RTL, colocated
`.test.ts`/`.test.tsx`):

- The new press-feedback hook: render-hook style per `useVisualViewport.test.ts`'s
  pattern — fake `PointerEvent`/touch dispatch and `window.matchMedia`
  (coarse-pointer query), assert it fires on touch, not on mouse-only
  interaction, and suppresses itself when `visual_motion` is false.
- The new accessibility-settings hook: seeds from the live
  `prefers-reduced-motion` query before the stored value loads; the stored
  value wins once loaded; both consumers observe the same resolved value.
- The vibration utility: mock `navigator.vibrate`, assert the right call
  per named outcome, assert a no-op when unsupported (delete the mock /
  `'vibrate' in navigator` false) and when `haptic_motion` is false.
- New Accessibility section on Controls: checkboxes reflect the loaded
  setting; toggling one calls the PUT; a failed save reverts the checkbox
  and shows an error — same assertions style as this codebase's existing
  Controls-page tests for `RecoveryTab`.
- Existing suites stay green — especially anything currently covering the
  15 rollout files' existing `active:scale-[0.96]` behavior and
  `submit-job.test.tsx` / `web/app/(dashboard)/jobs/[id]/page.test.tsx`'s
  delete-flow coverage.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Scope fence: touch only the files named in slices #569–#571 above (backend:
  `src/database.py`, `src/api/controls.py`, their two test files; frontend:
  the new hooks under `web/lib/hooks/`, the 15+6 named rollout files, the new
  vibration utility, `web/app/(dashboard)/controls/page.tsx`, and colocated
  tests). Do not touch `/intake` or `recovery-panel.tsx` — see the
  correction note in #571. Do not refactor unrelated code in a file opened
  for one change.
- Do not attempt any iOS/WebKit vibration workaround (hidden-checkbox
  tricks, etc.) — ADR-0053 explicitly rejects this; iOS relies on the
  visual press effect only.
- Do not build the button/anchor consolidation into a shared component —
  explicitly deferred, separate follow-up work per ADR-0053.
- No new npm/pip dependencies — everything here (Vibration API,
  `matchMedia`, `PointerEvent`) is a native browser API already used
  elsewhere in this codebase (`useReducedMotion.ts`, `useVisualViewport.ts`).
- Run `python -m pytest tests -q` and `ruff check src/` for the backend
  slice; `npm run test:run`, `npm run lint`, and `npm run build` from
  `web/` for the frontend slices. Never run tests through the `rtk` hook —
  `.claude/rules/rtk-tests.md`.

## Deliverable

Uncommitted working-tree changes implementing #569–#571 in full: the
migration-free accessibility-settings backend + API + Settings UI toggle,
the shared press-feedback hook wired onto the verified 15+6-file v1 set, and
the outcome-tied vibration utility wired into the three verified in-scope
outcome sites — with colocated regression tests per each issue's acceptance
criteria, plus a short summary of what changed per slice and what was
explicitly left unaddressed (the `/intake` share-target and
`recovery-panel.tsx` bullets flagged in #571 above, and anything else that
blocked you, e.g. if a cited line has drifted further than a line or two).
