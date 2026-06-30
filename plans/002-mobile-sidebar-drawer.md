# 002 — Mobile: sidebar sliver → full drawer with an edge pull-tab

Written against commit `92ad1c5`. If `git rev-parse --short HEAD` differs and
`web/components/sidebar.tsx` or `web/app/(dashboard)/layout.tsx` changed around
the cited lines, STOP and re-read before editing.

## Problem

On small screens the 64px icon rail ("the sliver") stays pinned to the left,
eating horizontal width and crowding the page. The component **already contains a
full slide-in drawer** (`<aside id="vig-nav-panel">` + backdrop, driven by
`open`/`setOpen`), but the rail is *also* always rendered.

On mobile we want only the drawer. To keep the drawer discoverable when it's
closed, show a **small pull-tab on the left edge** — an affordance that hints "a
drawer lives here." Tapping it opens the existing drawer.

The drawer's open/close/focus-trap/Escape/scroll-lock logic does **not** change —
it already works. This plan changes what's visible per breakpoint and adds **one
edge-tab trigger**. (No top bar — the tab is the only mobile affordance.)

## Current state

`web/app/(dashboard)/layout.tsx`:

```tsx
<div className="flex h-screen overflow-hidden">
  <Sidebar />
  <main className="relative isolate flex-1 overflow-auto p-6">
```

`web/components/sidebar.tsx` — the rail container (line ~274):

```tsx
{/* Collapsed rail — always visible. Favicon logo + per-page icons. */}
<div className="flex w-16 shrink-0 flex-col items-center border-r border-line bg-surface py-5">
```

The drawer (`<aside>`, line ~340) and backdrop (line ~331) are `fixed` and
already overlay everything — leave them as-is.

Breakpoint: `sm` (640px), matching the rest of the dashboard.

## Steps

### Step 1 — Hide the rail on mobile

File: `web/components/sidebar.tsx`, line ~274.

Change:

```tsx
<div className="flex w-16 shrink-0 flex-col items-center border-r border-line bg-surface py-5">
```

to:

```tsx
<div className="hidden w-16 shrink-0 flex-col items-center border-r border-line bg-surface py-5 sm:flex">
```

(`flex` → `hidden … sm:flex`. Nothing else changes. Because the rail was the only
other flex child of the `h-screen` row, `<main>` now spans full width on mobile
automatically — no layout-direction change needed.)

### Step 2 — Add the edge pull-tab (closed-state affordance)

File: `web/components/sidebar.tsx`.

`open`/`setOpen` already exist in scope. Add `Tally2` to the existing lucide
import (line ~6–15) — the two vertical bars read as a grip/handle, the right icon
for an edge pull-tab:

```tsx
import {
  Rss,
  Brain,
  LayoutGrid,
  MessageSquareText,
  SlidersHorizontal,
  ChevronRight,
  ChevronLeft,
  Tally2,
  type LucideIcon,
} from 'lucide-react';
```

Add this **as the first element inside the returned `<>` fragment** (right after
`return (` / the opening `<>`, before the `{/* Collapsed rail … */}` comment):

```tsx
{/* Mobile pull-tab — the rail is hidden < sm, so this slim edge handle is the
    affordance that a nav drawer exists. Hidden while the drawer is open. */}
<button
  type="button"
  onClick={() => setOpen(true)}
  aria-label="Open navigation"
  aria-expanded={open}
  aria-controls="vig-nav-panel"
  className={`fixed left-0 top-1/2 z-30 flex h-16 w-6 -translate-y-1/2 items-center justify-center rounded-r-lg border border-l-0 border-line bg-surface text-muted shadow-overlay transition-opacity hover:text-ink sm:hidden ${
    open ? 'pointer-events-none opacity-0' : 'opacity-100'
  }`}
>
  <Tally2 className="h-4 w-4" strokeWidth={2} aria-hidden="true" />
</button>
```

Notes for the executor:
- `z-30` keeps the tab **below** the backdrop (`z-40`) and drawer (`z-50`), so when
  open it's visually covered; the `opacity-0 pointer-events-none` toggle also
  removes it from interaction. Don't raise its z-index.
- `transition-opacity` is the only motion; reduced-motion is already neutralized
  globally in `globals.css`, so no extra guard is needed.
- The tab protrudes ~24px (`w-6`) from the left edge, vertically centered. If it
  overlaps page content awkwardly, that's expected — it's a fixed overlay handle,
  same as the backdrop.

### Step 3 — Mobile padding on main (small polish)

File: `web/app/(dashboard)/layout.tsx`, line 13.

Change `p-6` → `p-4 sm:p-6` on `<main>` for a bit more usable width on phones.
This is the only layout edit. Do **not** change the flex direction or add a top
bar.

## Files

**In scope:** `web/components/sidebar.tsx`, `web/app/(dashboard)/layout.tsx`.

**Out of scope — do not touch:**

- The drawer `<aside>` and its effects (open/close/focus/Escape/scroll-lock) — they work.
- `NavLink`, `NAV`, `LogoMark`, `GithubIcon`, `isActive` — no logic change.
- No new top bar, no header component, no `flex-col` shell restructure.
- The fixed-width-input overflow fix lives in plan **001** — do it there.

## Done criteria

1. `cd web && npm run lint` → passes.
2. `cd web && npx tsc --noEmit` → no new type errors.
3. `cd web && npm run build` → succeeds.
4. Manual check at 375px (DevTools, iPhone SE / responsive 375×667):
   - No 64px icon rail on the left.
   - A slim tab with a `Tally2` grip (two vertical bars) sits on the left edge, vertically centered.
   - Tapping it slides in the drawer; the tab fades out while open.
   - Backdrop tap, the drawer's X, Escape, and choosing a nav item all close the
     drawer; the tab fades back in.
5. At ≥640px: the icon rail is back exactly as before; the pull-tab is gone
   (`sm:hidden`); page is visually identical to pre-change.
6. Keyboard at 375px: Tab reaches the pull-tab; activating it opens the drawer and
   moves focus inside (existing behavior); closing returns focus to the tab.

## Test plan

CSS/markup change reusing existing `open` state — no new logic, no new unit test
warranted. Run the existing suite to confirm no regression:

```bash
cd web && npm run test:run
```

Expected: same pass/fail baseline. If a sidebar test asserts the rail is always
present, scope that assertion to desktop — but first confirm such a test exists
(`web/**/*sidebar*`); do not invent one.

## Maintenance note

The drawer now has two open triggers: the desktop rail buttons and the mobile
pull-tab. Both call the same `setOpen(true)` — keep one source of truth. If the
"mobile" breakpoint changes, it must change in two coordinated places: the rail
(`sm:flex`) and the pull-tab (`sm:hidden`).

## Escape hatches

- If the pull-tab stays visible *on top of* the open drawer, its z-index is wrong
  — it must be `z-30` (below backdrop `z-40` / drawer `z-50`). Don't bump it above
  them; fix the value.
- If a test fails asserting the rail's global presence, STOP and report it rather
  than deleting the test — the assertion may need a viewport scope jsdom can't
  fake.
