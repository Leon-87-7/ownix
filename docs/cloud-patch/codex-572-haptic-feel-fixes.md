# Codex prompt — implement issue #572 (haptic button-feel regression fixes)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0053-mobile-haptic-button-feel.md` — **authoritative**. Records
   why real vibration is Android/Chromium-only, why the visual press effect
   is a JS-driven mechanism rather than bare CSS `:active` (see its
   "Considered options" and "Decision" sections), and that iOS never getting
   real vibration is an accepted platform constraint, not a bug — the
   "Consequences" section says so explicitly. If anything below disagrees
   with the ADR, the ADR wins.
2. GitHub issue #572 (`gh issue view 572 --repo Leon-87-7/ownix`) — five
   findings from a `/council-review` of the #569-571 feature (working-tree
   diff, not yet committed at review time). Its "Findings to fix" and
   "Acceptance criteria" sections are restated more precisely below with
   verified line numbers — treat the issue as background, this document as
   the precise spec.
3. `CLAUDE.md` (repo root) — backend test/lint commands
   (`python -m pytest tests -q`, `ruff check src/`; **never** through the
   `rtk` hook, `.claude/rules/rtk-tests.md`).
4. `web/CLAUDE.md` — component layout (`web/components/<area>/<kebab-name>.tsx`,
   colocated `.test.tsx`) and the web test/lint commands (`npm test` /
   `npm run test:run`, `npm run lint`, `npm run build`, all run from `web/`).
5. The specific files cited per finding below — line numbers are as of this
   writing (verified directly against current code, not pulled from the
   issue body or memory); find the symbol by name if a line has drifted.

## Key decisions already made (do not relitigate)

- **This is a bug-fix pass on shipped work, not a redesign.** #569-571's
  press-feedback/haptic architecture (the `usePressFeedback`/
  `useHapticFeedback`/`useAccessibilitySettings` hooks) stays as-is except
  for the specific fixes below. Do not restructure the settings store (e.g.
  into `useSyncExternalStore` or React Context) as part of this pass — that
  was raised separately as a lower-priority structural nit and is explicitly
  **out of scope** here.
- **Finding 1's fix is deletion of redundant CSS, not deletion of the JS
  hook.** ADR-0053 deliberately chose a JS-driven press effect
  (`element.animate()` via `usePressFeedback`) over bare CSS `:active`
  specifically because `:active` doesn't reliably fire on iOS without a real
  touch listener attached — which the hook itself now provides. Do not
  "simplify" this finding by removing `usePressFeedback` and falling back to
  CSS alone; that would reintroduce the exact unreliability the ADR
  addressed. The fix is to remove the now-redundant CSS classes from the
  elements that already get the JS-driven effect.
- **Finding 4 needs a human call before any code changes.** ADR-0053's
  "Consequences" section already accepts "iOS gets no real vibration" as a
  platform constraint, not something the UI must call out. Do not add
  copy or feature-detection gating for this without an explicit go-ahead —
  see Finding 4 below for exactly what to do instead.
- **Finding 5 is a plain copy change** — implement directly, no design
  sign-off needed.

## Work order

Five findings, in the fix-priority order the council review recommended
(both Majors first, since they're real accessibility/UX regressions; the
rest in issue order).

### Finding 1 — Double press-animation on every migrated element (Major)

Every element wired with `usePressFeedback` still carries the pre-existing
`active:scale-[0.96] motion-reduce:active:scale-100` Tailwind class alongside
the hook's `element.animate()` call, both driving `transform: scale(0.96)`:

- `web/components/ui/ghost-button.tsx:25` (class) + `:58` (`{...pressFeedback}` spread)
- `web/components/ui/dialog.tsx:55` (class) + `:54` (`{...pressFeedback}`)
- `web/components/ui/sheet.tsx:26` (class) + `:25` (`{...pressFeedback}`)
- `web/components/feed/submit-job.tsx:306` (class, `SheetActionButton`) + `:305` (`{...pressFeedback}`)
- `web/app/(dashboard)/jobs/[id]/page.tsx:668` (`CARD_ACTION_BUTTON` shared class, consumed by `CardCopyButton`/`CardDownloadButton`/`CardOpenButton`) + `:686,713,731` (`{...pressFeedback}` in each of the three)

iOS Safari only activates `:active` styles once a real touch listener is
attached to the element — exactly what `usePressFeedback` adds via
`onPointerDown`/`onTouchStart`. This likely activates a previously-dormant
CSS `:active` transform at the same moment the WAAPI animation fires,
producing a compounded/janky double-press on iOS specifically — the one
platform ADR-0053 says the visual effect alone must carry (no vibration
there).

**Fix:** remove `active:scale-[0.96]` and `motion-reduce:active:scale-100`
(and, for dialog/sheet's close button, `motion-reduce:transition-none` stays
if it covers something else — check before removing more than the scale
classes) from each of the five locations above, since `usePressFeedback`
already reads the `visual_motion` setting and no-ops when motion is
disabled, replacing what `motion-reduce:active:scale-100` did. Do not touch
`active:scale-[0.96]` on any element that does **not** also spread
`{...pressFeedback}` — this fix is scoped to exactly the elements listed.

**Regression:** touch input on every listed element must still show exactly
one visual press effect (not zero, not two); desktop mouse interaction must
show no new effect (unchanged from before); `prefers-reduced-motion`/
`visual_motion: false` must still suppress the press effect entirely (now
solely via the hook, since the CSS fallback is gone).

**Test:** extend `web/lib/hooks/usePressFeedback.test.ts` or the relevant
component test to assert only one animation trigger path remains — check
existing `dialog.test.tsx`/`sheet.test.tsx`/`ghost-button.test.tsx` (if
present) don't assert on the removed classes; if they do, update the
assertion to check for `usePressFeedback`'s behavior instead of the literal
class string.

### Finding 2 — Reduced-motion default silently overridden after settings load (Major)

`web/lib/hooks/useAccessibilitySettings.ts:97` — the pre-load fallback
(`stored ?? { visual_motion: !reducedMotion, haptic_motion: true }`) correctly
respects the live `prefers-reduced-motion` query. But
`src/database.py:1695`'s `_DEFAULT_ACCESSIBILITY_SETTINGS = {"visual_motion":
True, "haptic_motion": True}` has no way to know the client's OS preference,
and this loads within milliseconds for any first-time visitor via
`useAccessibilitySettings.ts`'s `load()` (around line 29). Once it resolves,
it silently overrides the OS-derived fallback with `true` — permanently
enabling press animations for a vestibular-disorder user until they manually
find and uncheck the new Settings toggle. This contradicts ADR-0053's stated
design ("seeded from the live prefers-reduced-motion query on first load")
and `web/CLAUDE.md`'s WCAG AA + reduced-motion bar.

**Fix direction:** the backend cannot know the client's OS preference at
request time, so the fix belongs client-side. In
`web/lib/hooks/usePressFeedback.ts`, gate the effective visual-motion flag on
**both** the stored/settings value **and** a live `useReducedMotion()` read
(`web/lib/hooks/useReducedMotion.ts`) — i.e. press animation fires only when
`storedVisualMotion && !useReducedMotion()`. This preserves the setting as
the user's explicit override once they've actually changed it away from the
default, while never firing motion for someone whose OS says reduce motion
and who has never touched the checkbox. Do not change the backend default —
this is a client-side compositing fix, matching the layered-preference
decision already recorded in ADR-0053 ("Stored preference vs. live OS
query: layered").

**Regression:** a user who explicitly turns Visual motion ON in Settings
while their OS has `prefers-reduced-motion: reduce` set should get exactly
the behavior this fix produces — no animation, OS wins. If that's not the
intended behavior for an explicit user override, flag it in your summary
rather than guessing — this is a genuine two-way tradeoff the ADR doesn't
explicitly resolve for the "user says yes, OS says reduce" case.

**Test:** extend `web/lib/hooks/usePressFeedback.test.ts` with a case:
`visual_motion: true` from settings + `prefers-reduced-motion: reduce` from
`matchMedia` → press effect does not fire.

### Finding 3 — Lost-update race in `saveAccessibilitySetting` (Minor)

`web/lib/hooks/useAccessibilitySettings.ts:53-75` — `saveAccessibilitySetting`
captures `previous` synchronously and rolls back to that snapshot on
failure, with no request-ordering guard. Two overlapping calls (from any
future caller — today's only caller, `AccessibilitySection` in
`web/app/(dashboard)/controls/page.tsx`, is safe because it shares one
`saving` flag disabling both checkboxes while any save is in flight) could
let a stale response overwrite a newer change.

**Fix:** add a simple monotonically-increasing request-generation counter
(module-level, alongside `stored`/`loading`) that `saveAccessibilitySetting`
captures at call time and checks before publishing its result or rollback —
if a newer call has started since, skip publishing. Mirror the
`requestGeneration` guard already used in `web/lib/fetch-utils.ts`'s
`useFetchDetail` (read that function first) rather than inventing a new
pattern.

**Regression:** the existing `AccessibilitySection` toggle/rollback UX
(optimistic update, error message on failure) must keep working unchanged
for the normal single-toggle-at-a-time case.

**Test:** add a case to `web/lib/hooks/useAccessibilitySettings.test.ts` (if
none exists yet, create it colocated) that fires two overlapping
`saveAccessibilitySetting` calls with the second's response resolving after
the first started, and asserts the final published value matches the
second (later) call, not the first.

### Finding 4 — No UI indication haptic vibration is a no-op on iOS (Minor — HITL, decision only)

Nothing in `web/app/(dashboard)/controls/page.tsx` or
`web/lib/hooks/useHapticFeedback.ts` tells an iOS/Safari user that "Haptic
motion" will never do anything on their device. ADR-0053's "Consequences"
section already accepts this as a platform constraint, not a gap requiring
UI treatment.

**Do not implement a UI change for this finding.** Instead, leave it
unaddressed and say so explicitly in your summary, flagging that it needs a
human product decision (copy addition vs. feature-detect-and-hide vs.
leave as-is per the ADR's existing stance) before any code changes — this
is exactly the kind of design call ADR-0053 already made once and a second
agent shouldn't quietly relitigate.

### Finding 5 — "Visual motion" label reads broader than its actual scope (Minor)

`web/app/(dashboard)/controls/page.tsx:509` — "Visual motion" sits under the
"Accessibility" section and could be read as an app-wide reduced-motion
toggle, but it only controls the one press-feedback effect from #570.

**Fix:** rename the label from `'Visual motion'` to `'Press animation'` at
line 509. Leave the description text (`'Show tactile press animation on
touch controls.'`) as-is — it already describes the narrower scope
accurately; only the short label is ambiguous. Update any test that asserts
on the literal string `'Visual motion'` (grep
`web/app/(dashboard)/controls/page.test.tsx` and any hook tests for this
string) to match the new label.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Scope fence: touch only the files named per finding above. Do not touch
  `active:scale-[0.96]` on elements outside Finding 1's named list. Do not
  refactor `useAccessibilitySettings.ts` into `useSyncExternalStore`/Context
  or otherwise restructure the settings store — that's explicitly out of
  scope for this pass (see Key decisions above).
- Do not implement anything for Finding 4 beyond noting it as unaddressed in
  your summary.
- Run `python -m pytest tests -q` and `ruff check src/` for the backend
  slice (only relevant if Finding 2's investigation touches
  `src/database.py`, which it should not per the fix direction above);
  `npm run test:run`, `npm run lint`, and `npm run build` from `web/` for
  the frontend findings. Never run tests through the `rtk` hook —
  `.claude/rules/rtk-tests.md`.

## Deliverable

Uncommitted working-tree changes implementing Findings 1, 2, 3, and 5 in
full, with regression tests per each finding's test requirement above, plus
a short summary of what changed per finding and explicit confirmation that
Finding 4 was left unaddressed pending a human product decision (and
anything else that blocked you, e.g. if a cited line has drifted further
than a line or two, or if Finding 2's OS-vs-explicit-user-override tradeoff
needs a human call instead of the assumed resolution).
