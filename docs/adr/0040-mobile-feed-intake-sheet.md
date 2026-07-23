---
adr: "0040"
title: Mobile Feed intake sheet — one launcher for the three ingests
status: accepted
date: 2026-07-23
---

## Context

The mobile Feed (`<sm`) exposed intake through two chips in the FilterBar tab grid — "Submit"
(`N`, opens the Submit URL dialog) and "Docs" (`D`, opens Ingest Docs) — styled and placed
differently from the content-type filter tabs. The third ingest, the `link` pipeline's dashboard
entry point (`U`, ADR-0039), had **no mobile trigger at all**: on desktop it's reachable from the
`Ctrl+Shift+K` command launcher, but that launcher's header button is `sm:hidden` and there is no
keyboard on mobile, so mobile users had no way to add a link. Adding a third chip would not scale
the pattern, and the two existing chips already crowd the tab grid.

## Decision

Replace the two mobile action chips with a **single non-floating launcher** — a `row-span-2`
`BadgePlus` icon button in `col-start-1` of the tab grid, occupying exactly the footprint the two
chips vacated — that opens a **bottom sheet** listing the three ingests, each an icon + label +
one-line description that closes the sheet and opens that ingest's existing dialog:

- Submit URL (`Plus`) — "Paste a URL - auto-detects the pipeline."
- Ingest Docs (`FileCode2`) — "Upload a PDF or document to parse."
- Ingest Link (`Waypoints`) — "Save a link as-is to your Brain - no processing."

The launcher is the mobile analog of the desktop command launcher, so it borrows that button's
treatment (`border-b-2 border-b-signal bg-surface text-body`) rather than the old chips'
`text-signal`. Sheet, its `intakeOpen` state, and an `openIntake()` on the `useSubmitJob()` context
all live in `SubmitJobProvider` alongside the other intake surfaces; the Feed page stays a pure
consumer. The three actions are extracted into a shared `INTAKE_ACTIONS` list consumed by **both**
the sheet (renders the description) and the launcher's Intake group (renders the shortcut), so a
fourth ingest is added in one place.

The bottom sheet is **built on the existing `@radix-ui/react-dialog`** primitive — the same
`Portal`/`Overlay`, `Content` re-anchored to `bottom-0 inset-x-0` with a `slide-up` keyframe added
beside the existing `tooltip-in/out` — authored in the hand-rolled style of `dialog.tsx`. It is
**not** the upstream shadcn Sheet.

Dashboard naming is unified on **"Ingest Link"** (the Ingest-Link `DialogTitle` and the launcher's
former "Ingest Links" label both become it); `/addlink` remains the Telegram-only command name.
See [[Link pipeline]] in `CONTEXT.md`.

## Considered options

- **Reuse the desktop command launcher on mobile** (open it from the new button, hide its
  non-intake groups, add descriptions). Rejected: the launcher is a keyboard command palette whose
  actions render `icon + label + kbd shortcut`; serving mobile intake would fork it on viewport at
  three points (add descriptions, hide Navigate/Recovery/Search, hide the meaningless shortcut
  chips). The genuinely reusable asset is the *action list*, not the palette's rendering — captured
  instead as the shared `INTAKE_ACTIONS`, letting each surface render its own way without one
  component branching between a palette and a touch menu.
- **Adopt shadcn's Sheet** (Base UI or Radix variant). Rejected: the Base UI variant pulls in
  `@base-ui-components/react`, a second primitive library alongside Radix; even the Radix variant's
  generated `sheet.tsx` drags in `class-variance-authority` (four-side variants we don't need —
  only `bottom`), `tailwind-merge`/`cn`, and `tailwindcss-animate`, none of which the repo uses.
  That would stand up a **second modal idiom** next to the hand-rolled `dialog.tsx`. Porting the
  Sheet's look onto the Radix Dialog already in `package.json` gives the identical bottom-sheet UX
  with zero new dependencies and one modal convention.
- **A floating FAB.** Rejected implicitly by the "non-floating" requirement — the launcher stays in
  document flow inside the tab grid, not fixed-positioned over content.

## Consequences

- In restricted mode the launcher opens the sheet normally and the three captioned actions render
  as a capability preview; each action's setter already raises the restricted toast on tap, so
  gating is per-item (unlike the desktop launcher, which is gated at open). Restricted mode's job is
  to showcase, and a described menu is a better teaser than a dead-end toast.
- Restricted mode also drops the Links tab (5 tabs instead of 6), so the `row-span-2` launcher
  leaves one empty trailing cell in the tab grid — absorbed with a trailing spacer.
- The desktop command launcher and the mobile sheet now share one source of truth for the intake
  action list; the launcher's "Ingest Links" label changes as a side effect of the rename.
- No bottom-sheet gesture affordance (no `vaul`, no drag-to-dismiss, no grabber) — dismissal is
  overlay-tap + `Esc` + the `X` close inherited from `DialogContent`. A visible "Add to your Index"
  title satisfies Radix's required `DialogTitle`.
