# 001 — Fix mobile horizontal overflow on Controls / Prompts pages

Written against commit `92ad1c5`. If `git rev-parse --short HEAD` differs and any
file below has changed around the cited lines, STOP and re-read before editing.

## Problem

On small screens (≈375px wide) the **Controls** page content is clipped at the
right edge: the "Edit"/"Remove" buttons read as "Edi…"/"Remo…", inputs run off
screen, and every card's right border is missing. The page is wider than the
viewport and scrolls horizontally.

### Root cause (confirmed)

The dashboard shell is:

```tsx
web/app/(dashboard)/layout.tsx
  <div className="flex h-screen overflow-hidden">
    <Sidebar />                                    // fixed w-16 (64px) rail
    <main className="relative isolate flex-1 overflow-auto p-6">  // overflow-auto = scrolls X too
```

`<main>` is `overflow-auto`, so any child that refuses to shrink below the
viewport width makes the **whole page** scroll horizontally — which is why every
card (not just one) looks clipped.

The children that refuse to shrink are **fixed-pixel-width inputs**:

- `web/app/(dashboard)/controls/page.tsx:200` — domain input, `className="w-72 …"` (288px)
- `web/app/(dashboard)/prompts/page.tsx:35` — description input, `className="w-72 …"` (288px)
- `web/app/(dashboard)/prompts/page.tsx:32` — name input, `className="w-52 …"` (208px)

At 375px viewport: 375 − 64 (rail) − 48 (`main` `p-6` = 24px each side) ≈ **263px**
of usable width. A `w-72` (288px) input exceeds that and forces the page wider.
`w-*` is a hard width with no `min-width: 0`, so flexbox cannot shrink it.

The tag-form changes already landed in this repo (stacking Name/Meaning, 6-col
color grid) are correct and unaffected — they were just being clipped by this
page-level overflow.

## Fix

Make the fixed-width inputs full-width on mobile and keep their fixed width from
the `sm` breakpoint up (≥640px), matching the idiom already used elsewhere in
this codebase (e.g. `filter-bar.tsx` uses `w-full sm:w-auto`).

`w-72` → `w-full sm:w-72`
`w-52` → `w-full sm:w-52`

This is the whole fix. The overflow disappears because the inputs can now shrink
to the container; on desktop nothing changes.

## Steps

### Step 1 — Controls domain input

File: `web/app/(dashboard)/controls/page.tsx`, line ~200 (inside `DomainTab`).

Find:

```tsx
<input id={inputId} type="text" required value={input} onChange={(e) => setInput(e.target.value)} placeholder="example.com" className="w-72 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none" />
```

Change `className="w-72 …"` to `className="w-full sm:w-72 …"` (only the width
token changes; leave every other class untouched).

### Step 2 — Prompts name + description inputs

File: `web/app/(dashboard)/prompts/page.tsx`.

Line ~32 (name input): change `w-52` → `w-full sm:w-52`.
Line ~35 (description input): change `w-72` → `w-full sm:w-72`.

Leave all other classes untouched.

### Step 3 (optional polish — only if Step 1–2 alone still feels cramped)

In `web/app/(dashboard)/layout.tsx:13`, change `p-6` → `p-4 sm:p-6` on `<main>`
to give mobile a touch more usable width. Do **not** do anything else to the
layout. Skip this step if the overflow is already gone and the page reads fine —
the primary cause is the inputs, not the padding.

## Files

**In scope:** `web/app/(dashboard)/controls/page.tsx`,
`web/app/(dashboard)/prompts/page.tsx`, optionally
`web/app/(dashboard)/layout.tsx` (Step 3 only).

**Out of scope — do not touch:**

- `web/components/sidebar.tsx` — the 64px rail is intentional (DESIGN.md "Operator's Console").
- `web/components/TagPicker.tsx` and the tag-form / color-grid markup in `controls/page.tsx` — already responsive; the bug is not here.
- `web/components/feed/filter-bar.tsx` — already responsive.
- Do **not** add `overflow-x-hidden` to `<main>` as a "fix": that hides clipped content instead of letting it fit, and masks future regressions.

## Done criteria

1. `cd web && npm run lint` → passes (no new warnings/errors).
2. `cd web && npx tsc --noEmit` → no new type errors.
3. `cd web && npm run build` → succeeds.
4. Manual check at 375px width (Chrome DevTools device toolbar, "iPhone SE" or
   responsive 375×667), on both `/controls` and `/prompts`:
   - No horizontal scrollbar on the page.
   - On `/controls`: every card's right border is visible; "Edit"/"Remove"
     buttons render in full; the "Add domain" input spans the card width.
   - On `/prompts`: the Name and Description inputs span the card width and don't
     overflow.
   - At ≥640px width both pages look identical to before this change.

## Test plan

This is a CSS-only (Tailwind class) change with no logic, so no new unit test is
warranted (the existing Vitest suite asserts behavior, not pixel widths). The
verification is the manual viewport check in Done criteria #4. Run the existing
suite once to confirm nothing regressed:

```bash
cd web && npm run test:run
```

Expected: same pass/fail baseline as before the change (no new failures).

## Maintenance note

Any future fixed-pixel width (`w-NN`, `w-[NNpx]`, `min-w-[…]`) added to a child
of `<main>` can reintroduce this exact bug, because `<main>` is `overflow-auto`.
Reviewers: when you see a hard `w-*` on an input/control inside a dashboard page,
ask whether it needs `w-full sm:w-*`. The grep `w-72|w-52|w-\[|min-w-\[` over
`web/app/(dashboard)` surfaces the candidates.

## Escape hatches

- If after Step 1–2 the page **still** scrolls horizontally at 375px, the
  overflow has a second source. STOP and report: run
  `git stash && cd web && grep -rn "w-\[\|min-w-\[\|w-72\|w-64\|w-56\|whitespace-nowrap" app/(dashboard)`
  and list what you find rather than guessing at more class changes.
- If `npm run build` fails for a reason unrelated to these edits (pre-existing
  breakage), report the failure output instead of trying to fix it — it is out of
  scope.
