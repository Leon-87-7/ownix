# Codex prompt — implement issue #419 (mobile Feed intake sheet: BadgePlus launcher for the three ingests)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0040-mobile-feed-intake-sheet.md` — the accepted decision:
   replace the two mobile Feed action chips with one non-floating `BadgePlus`
   launcher opening a bottom sheet of the three ingests; the shared
   `INTAKE_ACTIONS` list; the "build the sheet on the existing Radix Dialog,
   not shadcn/vaul" call and why; the restricted-mode posture; the rejected
   alternatives. **Authoritative over any paraphrase below if the two
   disagree.**
2. `CONTEXT.md` glossary entry **Link pipeline** — records that "Add Link" is
   the Telegram (`/addlink`) command name only and the dashboard modal is
   **"Ingest Link"**. Use "Ingest Link" verbatim for all dashboard-facing
   copy in this batch.
3. `CLAUDE.md` (repo root) — the **Component layout** section (`ui/` = shared
   primitives, `feed/` = feature folder, kebab-case files, colocated
   `.test.tsx`, no barrel `index.ts`, import the file directly) and the web
   test/lint commands. `DESIGN.md` (repo root) — the Signal Rule (one
   rationed signal orange = "act here"; the active tab already owns the full
   fill, which is why the launcher takes the Commands-button *underline*
   treatment, not a full fill) and the flat-by-default / reduced-motion bar.
   Read `agent-knowledge/skills/impeccable/SKILL.md` before the UI work.
4. The specific files below — line numbers are as of this writing and may
   have drifted a line or two; find the symbol by name if so.
5. GitHub issue #419 (`gh issue view 419 --repo Leon-87-7/ownix`) — its
   acceptance criteria are the definition of done. This one issue bundles a
   prefactor and the feature; the work order below sequences them.

## Key decisions already made (do not relitigate)

- **One dedicated bottom sheet, built on the existing `@radix-ui/react-dialog`
  primitive** — not the shadcn Sheet (Base UI *or* Radix variant), not
  `vaul`. Do **not** add `class-variance-authority`, `tailwind-merge`, a
  `cn()` util, or `tailwindcss-animate`; the repo hand-rolls modals in
  `web/components/ui/dialog.tsx` with template-string classes and custom
  keyframes, and this stays on that one idiom. Only the **bottom** side is
  needed — no four-side variant machinery.
- **No drag-to-dismiss and no grabber.** Dismissal is overlay-tap + `Esc` +
  the `X` close, inherited from the Dialog primitive. (Skipping a drag
  gesture is exactly why `vaul` is not being added.)
- **The launcher is the mobile analog of the desktop Commands button**, so it
  borrows that button's treatment (`border-b-2 border-b-signal bg-surface
  text-body`), *not* the old Submit/Docs chips' `text-signal`. Icon is
  `BadgePlus`, **icon-only**, no text label, no `kbd` chip. It sits
  `row-span-2` in `col-start-1` — the exact footprint the two chips vacated.
- **Sheet title is "Add to your Index"** (visible; also satisfies Radix's
  required `DialogTitle`). The three item descriptions are fixed copy, hyphens
  not em dashes:
  - Submit URL — `Paste a URL -  auto-detects the pipeline.`
  - Ingest Docs — `Upload a PDF or document to parse.`
  - Ingest Link — `Save a link as-is to your Brain - no processing.`
- **Icons reuse the launcher's:** `Plus` (Submit URL), `FileCode2` (Ingest
  Docs), `Waypoints` (Ingest Link). `Waypoints` ≠ `Link2`; `Link2` stays the
  "Open Links" / Links-tab nav glyph.
- **Restricted mode: open-and-gate-per-item.** The launcher opens the sheet
  normally in restricted mode (it's a capability preview); each item's
  existing setter (`setOpen`/`setDocsOpen`/`setAddLinkOpen`) already raises
  the restricted toast on tap, so no new gating is written. This deliberately
  differs from the desktop command launcher, which gates at open — do not
  copy that gate onto the sheet.
- **Tap = launch, nothing inlined.** Each sheet item closes the sheet and
  opens that ingest's existing dialog (Submit URL / Ingest Docs / Ingest
  Link). The single-field Ingest Link form is **not** inlined into the sheet.

## Work order

Do the prefactor (step 1) first — it creates the shared list the sheet
consumes — then the primitive (2), then the sheet + provider wiring (3), then
the Feed trigger (4).

### 1. Prefactor — shared `INTAKE_ACTIONS` + unify the link-ingest label

- `web/components/feed/submit-job.tsx` — the command launcher's Intake group
  (`<CommandGroup label="Intake">`, `:636-664`) hardcodes three
  `<CommandAction>`s: `Submit URL` (`:639`), `Ingest Docs` (`:648`), **`Ingest
  Links`** (`:657`). Extract these three into a **module-level descriptor
  array** `INTAKE_ACTIONS` — one entry per action carrying `key`, `icon`
  (`Plus`/`FileCode2`/`Waypoints`), `label`, `description` (the fixed copy
  above), and `shortcut` (`N`/`D`/`U`). The per-action `onSelect` closes over
  component-scoped setters, so keep `onSelect` **out** of the module const;
  resolve it in-component by `key` (a small `key → setter` map, e.g. `submit
  → setOpen(true)`, `docs → setDocsOpen(true)`, `link → setAddLinkOpen(true)`,
  each preceded by closing the surface it was launched from). The launcher's
  Intake group then `.map`s `INTAKE_ACTIONS` to `<CommandAction>` (rendering
  `label` + `shortcut`, ignoring `description`).
- Rename the link action's label to **`Ingest Link`** (singular) in
  `INTAKE_ACTIONS` — this is the `:657` label. Rename the modal's own
  `DialogTitle` `Add Link` (`:573`) to **`Ingest Link`**, and the two other
  user-facing "Add Link" strings in that same modal: the submit button label
  `Add Link` / `Adding…` (`:610`) → `Ingest Link` / `Adding…`, and the helper
  line `Add Link saves the link as-is; it does not process it…` (`:592-594`)
  → `Ingest Link saves the link as-is…`. **Do not** rename the internal
  identifiers (`addLinkOpen`, `setAddLinkOpen`, `submitAddLink`,
  `addLinkUrl`) — they're not user-facing — and **do not** touch the Telegram
  `/addlink` command anywhere.
- Regression: the desktop command launcher still opens all three dialogs, now
  driven by `INTAKE_ACTIONS`; the `N`/`D`/`U` keyboard branches
  (`:300-409`) are unchanged.

### 2. New bottom-sheet primitive

- New file `web/components/ui/sheet.tsx`, modeled directly on
  `web/components/ui/dialog.tsx` (`:1-58`) — same `import * as RadixDialog`,
  same `RadixDialog.Portal` + `RadixDialog.Overlay` + `RadixDialog.Content`
  shape, same `RadixDialog.Close` `X`. Export `Sheet` (= `RadixDialog.Root`),
  `SheetContent`, `SheetTitle`, `SheetDescription`. The only substantive
  difference from `DialogContent` (`:10-33`): re-anchor `Content` to the
  bottom edge — replace the `fixed left-1/2 top-1/2 … -translate-x-1/2
  -translate-y-1/2 … max-w-md rounded-lg` positioning with
  `fixed inset-x-0 bottom-0 … w-full rounded-t-2xl` (full-width, rounded top
  only), and swap the `animate-tooltip-in/out` data-state classes for the new
  `slide-up-in/out` (step below). Keep the `motion-reduce:animate-none`
  guard verbatim (reduced-motion bar).
- `web/app/globals.css` — add `@keyframes slide-up-in` /
  `@keyframes slide-up-out` (translateY from `100%`→`0` and back, opacity as
  the tooltip pair does) directly after the existing
  `@keyframes tooltip-out` block (`:235-244`).
- `web/tailwind.config.ts` — register `'slide-up-in'` / `'slide-up-out'` in
  the `animation` map next to `'tooltip-in'`/`'tooltip-out'` (`:73-75`),
  mirroring their `<name> <duration> ease-out both` form.

### 3. Render the intake sheet + expose `openIntake()`

- `web/components/feed/submit-job.tsx` — add a fourth surface to
  `SubmitJobProvider`: `intakeOpen`/`setIntakeOpen` state, using the same
  `restricted`-aware `setOpen`-style wrapper the other dialogs use
  (`:218-268`) **but** without a hard block — restricted users may open the
  sheet (per the key decision); the toast fires per-item via the existing
  setters. Add `openIntake: () => setIntakeOpen(true)` to
  `SubmitJobContextValue` (`:58-68`), the context `value` memo (`:520-542`),
  and expose it through `useSubmitJob`.
- Render the sheet near the other dialogs at the end of the provider
  (`:547-716`) using the `web/components/ui/sheet.tsx` primitive:
  `<SheetTitle>Add to your Index</SheetTitle>` then `INTAKE_ACTIONS.map`ped to
  a tap-row per item — icon + `label` + `description` — each row's `onClick`
  doing `setIntakeOpen(false)` then the item's `key → setter` launch (same
  dispatch built in step 1). Rows are real `<button>`s, min 44px touch
  height, focus-ring per the existing `CommandAction` style (`:186-200`) is a
  good reference for classes.

### 4. Feed trigger — replace the two chips with the launcher

- `web/app/(dashboard)/feed/page.tsx` — the `actionSlot` (`:495-534`)
  currently renders two `sm:hidden` buttons: Submit (`:503-516`,
  `col-start-1 row-start-1`, `onClick={() => setSubmitOpen(true)}`) and Docs
  (`:517-532`, `col-start-1 row-start-2`, `onClick={openDocs}`). Replace both
  with a **single** `sm:hidden` button: `BadgePlus` icon-only,
  `col-start-1 row-start-1 row-span-2` (full height of the two rows it
  replaces), `onClick={openIntake}`, `aria-haspopup="dialog"`,
  `aria-label="Add to your Index"`, and the **Commands-button** treatment
  (`border border-line border-b-2 border-b-signal bg-surface text-body …
  hover:text-ink active:scale-[0.96] motion-reduce:active:scale-100`) — not
  the old chips' `text-signal`. Keep it in the `SegmentedTabs` `leadingItem`
  slot so the content-type tabs auto-flow into columns 2–4.
- Pull `openIntake` from `useSubmitJob()` in the destructure (`:154-159`,
  alongside `setOpen: setSubmitOpen`); `setSubmitOpen`/`openDocs` are no
  longer used by `actionSlot` — remove them from the destructure only if
  nothing else in the file references them (grep first). Fix the
  `lucide-react` import (`:35`): add `BadgePlus`; drop `Plus`/`FileCode2`
  **only if** they have no other use in this file (grep first — do not remove
  an icon still referenced elsewhere).
- Restricted mode drops the Links tab (5 content-type tabs instead of 6, see
  `contentTypeTabs`, `:317-333`), so the `row-span-2` launcher leaves one
  empty trailing cell in the 4-column grid. Absorb it (e.g. a trailing
  `aria-hidden` spacer cell, or a grid tweak) so there's no visible hole; do
  not special-case by counting tabs in a brittle way.

### Tests

Colocated `.test.tsx`, matching the existing `submit-job.test.tsx` /
`filter-bar.test.tsx` / feed `page.test.tsx` conventions (RTL + MSW where a
fetch is involved):

- `INTAKE_ACTIONS` drives the desktop launcher unchanged (all three items
  present, labeled "Submit URL" / "Ingest Docs" / **"Ingest Link"**).
- `openIntake()` opens the sheet; the sheet shows the "Add to your Index"
  title and all three items with their descriptions.
- Tapping a sheet item closes the sheet and opens that item's dialog (assert
  the target `DialogTitle` appears — e.g. "Ingest Link").
- The Feed's mobile `actionSlot` renders a single `BadgePlus` launcher and no
  longer the two separate Submit/Docs chips.
- Restricted mode: the launcher still opens the sheet; tapping an item raises
  the restricted toast and does not submit.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **No new dependencies.** Do not add `vaul`, shadcn's `sheet`,
  `class-variance-authority`, `tailwind-merge`, `tailwindcss-animate`, or a
  `cn()` util. Build on `@radix-ui/react-dialog`, already in
  `web/package.json`.
- Scope fence: touch only `submit-job.tsx`, the new `ui/sheet.tsx`,
  `globals.css`, `tailwind.config.ts`, `feed/page.tsx`, and the new/updated
  colocated tests. Do **not** refactor the command launcher's Navigate /
  Recovery / Search groups, the keyboard-shortcut handler, or any unrelated
  code in a file you opened for one change.
- "Add Link" survives **only** as the Telegram `/addlink` command name — every
  dashboard-facing occurrence becomes "Ingest Link". Do not rename internal
  identifiers or the Telegram command.
- Preserve the reduced-motion guards (`motion-reduce:*`) and WCAG AA contrast
  per `DESIGN.md`; the sheet must be keyboard-dismissable (`Esc`) and
  focus-trapped (free from the Radix Dialog primitive — don't defeat it).
- Run `npm run test:run`, `npm run lint`, and `npm run build` from `web/`.
  (No Python touched in this batch. Never run tests through the `rtk` hook —
  `.claude/rules/rtk-tests.md`.)

## Deliverable

Uncommitted working-tree changes implementing #419 in full — the shared
`INTAKE_ACTIONS` prefactor + "Ingest Link" relabel, the Radix-based bottom-
sheet primitive, the intake sheet + `openIntake()`, and the Feed's
`BadgePlus` launcher replacing the two mobile chips — with colocated
regression tests per the acceptance criteria, plus a short summary of what
changed per step and anything that blocked you (e.g. if removing
`Plus`/`FileCode2` from the Feed import turned up an unexpected remaining
reference).
