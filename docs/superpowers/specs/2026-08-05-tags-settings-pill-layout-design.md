# Tags settings — icon-aware pill layout with detached edit panel

**Date:** 2026-08-05
**Scope:** `web/app/(dashboard)/controls/page.tsx` (`TagsTab`, `TagRow`, `ColorSwatch`)

## Problem

The Tags settings tab has two issues:

1. `TagRow` renders each tag's color with the plain `ColorSwatch` component
   (a flat color dot), not the icon-aware `TagMark` component that already
   exists in `web/components/ui/tag-picker.tsx`. Tags with an icon set never
   show it here.
2. Tags render as a vertical `<ul className="space-y-2">` list of full-width
   rows. The desired layout is a wrapped "heap" of pill-shaped tags, and
   clicking a pill should open its edit form in a fixed slot below the
   create-tag form, rather than expanding the row in place.

## Design

### Layout

`TagsTab` renders, top to bottom:

1. Create form (unchanged — the existing collapsible `<details>` on mobile,
   plain card on desktop).
2. Edit panel — new fixed slot, conditionally rendered only while a tag is
   selected for editing. Not nested inside the create form's `<details>`, so
   it's visible regardless of the create form's collapsed state.
3. Tag pills — `<ul className="flex flex-wrap gap-2">` (replacing the
   current stacked-row list).

### Pills

- Use `TagMark` (icon if set, else color dot) instead of `ColorSwatch`.
- Styling matches the existing `TagChips` chip look: `border-line` /
  `bg-raised` pill chrome, `text-ink` name (not tag-colored text — the
  `PRESET_COLORS` palette is only vetted for ≥3:1 non-text contrast per its
  own comment in `tag-picker.tsx`, not the 4.5:1 WCAG AA text threshold, so
  full colored text risks failing DESIGN.md's AA bar).
- No delete affordance on the pill. The whole pill is a `<button>` that
  opens the edit panel for that tag.
- The pill currently being edited gets `ring-1 ring-signal-deep` so it's
  visually linked to the open edit panel.
- Names are not truncated — pills size naturally in the wrapped flex
  layout (this is a small, curated settings list, not a space-constrained
  card).

### Edit panel

- Reuses the existing `TagForm` (Name / Meaning / Color / Icon fields),
  pre-filled from the clicked tag — same as today's inline edit.
- Button row, left to right: **Save** (CTA) · **Cancel** (ghost) · trash
  icon (delete, reusing the `TagX` icon already imported, still gated by
  the existing `confirm(\`Delete tag "${tag.name}"?\`)` dialog).
- Opening the panel calls `scrollIntoView({ behavior: 'smooth', block:
  'nearest' })` on the panel and focuses its Name input — needed because
  the panel is a fixed slot rather than inline, so it can be off-screen
  when a long tag list puts the clicked pill far down the page.
- Closing the panel (same-pill click again, Cancel, or a successful
  Save/Delete) unmounts it and clears the `ring-1 ring-signal-deep`
  highlight.
- Clicking a *different* pill while one is already open switches the panel
  to the new tag immediately — no unsaved-changes confirmation (form
  fields aren't destructive/hard to redo).

### Unaffected

- `useTagList` hook (fetch/create/update/delete API surface) — unchanged.
- Loading / fetch-error / empty-list states — unchanged, still rendered as
  text above the pill list.
- The create-tag flow and its `TagForm` instance — unchanged.
- `TagChips`, `TagMenu`, `TagMark`, `IconPicker` in
  `web/components/ui/tag-picker.tsx` — unchanged, reused as-is.

## Out of scope

- Any change to `TagMenu` / `TagChips` used elsewhere (feed cards, job
  detail) — this design only touches the Tags settings tab.
- Keyboard reordering or drag-and-drop of pills.
