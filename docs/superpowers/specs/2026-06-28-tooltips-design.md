# Tooltip system — design spec

**Date:** 2026-06-28
**Status:** Approved (brainstorm)
**Area:** `web/` (Next.js dashboard)

## Goal

Introduce one on-brand, accessible Tooltip primitive and roll it out across the
dashboard: **replace** every existing native `title=` tooltip with the styled
component, and **extend** coverage to icon-only controls and metric labels that
currently lack any hover/focus explanation.

The native browser `title=` box (unstyled gray, ~1s delay, no dark theme) is
off-brand against the Operator's Console dark-plate system. After this work, no
native `title=` tooltip appears anywhere in the app.

## Scope decisions (from brainstorm)

- **Replace + extend** — build the primitive, migrate all existing `title=`, and
  add net-new tooltips.
- **Approach: Radix Tooltip** (`@radix-ui/react-tooltip`). Radix is already a
  dependency (`react-dropdown-menu`); this gives keyboard focus, Escape-to-dismiss,
  ARIA wiring, collision detection, and configurable delay out of the box (WCAG AA).
- **Net-new targets:** icon-only controls and metric labels. **Excluded:** status
  badges and type badges (intentionally left as-is).
- **Truncation/overflow-reveal:** convert **everything**, including the
  full-text-of-truncated-row tooltips, for full visual consistency. No native gray
  box remains in the app.

### Deliberate omissions (YAGNI)

- No rich/interactive tooltips (no links/buttons inside a tooltip).
- No controlled-open API.
- No per-tooltip theming beyond a single `mono` flag.
- No status/type badge tooltips.

## The primitive — `web/components/ui/tooltip.tsx`

A thin wrapper over `@radix-ui/react-tooltip` exposing one ergonomic component
plus a provider.

```tsx
<Tooltip content="GitHub repository">{children}</Tooltip>
```

- **`<TooltipProvider>`** — mounted once in the dashboard layout, holds shared
  delay config so all tooltips share timing behavior.
- **`<Tooltip>`** — composes Radix `Root → Trigger(asChild) → Portal → Content →
  Arrow`. `asChild` adds **zero wrapper DOM**: it borrows the child
  button/span/link, so it drops onto existing elements without changing layout.
- **Props:**
  - `content: ReactNode` — the tooltip body.
  - `side?`, `align?` — placement passthrough to Radix `Content`.
  - `mono?: boolean` — render body in JetBrains Mono for machine facts (URLs, full
    truncated text), per DESIGN.md.
  - **Nullish `content` renders the child bare** — preserves today's
    `title={display || undefined}` conditional pattern (no tooltip when there's
    nothing to show).

## Styling — inside the Operator's Console

Normative tokens from DESIGN.md / `tailwind.config.ts`:

- Plate: `bg-raised` (`#1c1f25`) + `border border-line` (`#262a31`) +
  **`shadow-overlay`** (the single shadow reserved for overlays — exact fit),
  `rounded-md`, `px-2 py-1`, `text-xs`.
- Text: `text-body` / `text-ink`. **Signal orange (`#f6921e`) deliberately unused**
  — tooltips are passive information, not an "act here" affordance, so they stay
  off the rationed accent.
- `mono` variant: `font-mono` + `break-words` + `max-w-xs` + `text-wrap: pretty`
  for URLs and long values.
- Filled arrow color-matched to the plate.
- Contrast: `text-ink` (`#f5f6f8`) on `bg-raised` (`#1c1f25`) clears WCAG AA.

## Motion — feel details, reduced-motion-safe

Animated via Radix's `data-state` (`delayed-open` / `instant-open` / `closed`) and
`data-side` attributes, with keyframes in `globals.css` — **no motion library
required**.

- **Enter:** opacity `0→1`, scale `0.96→1`, 2px translate from the trigger side → 0;
  `out-quart` easing (`cubic-bezier(0.25, 1, 0.5, 1)`), ~140ms.
- **Exit:** subtler and faster — opacity + 2px translate only.
- **Specific properties only** — no `transition: all`.
- `@media (prefers-reduced-motion: reduce)` → opacity-only, no transform/scale.

## Delay & keyboard behavior

- `TooltipProvider` config: `delayDuration={300}`, `skipDelayDuration={200}`.
  Quick console feel (Radix's 700ms default is sluggish); moving between adjacent
  triggers skips the re-delay.
- Focus opens the tooltip; **Escape** closes it; `role="tooltip"` and
  `aria-describedby` wiring are provided by Radix. Clears the WCAG AA bar.
- Hit-area (40×40) is a property of the trigger elements themselves, not the
  tooltip — out of scope here.

## Rollout map (concrete)

**Mount provider:** dashboard layout (`web/app/(dashboard)/layout.tsx` or root
`web/app/layout.tsx` — confirm during planning).

**Replace explanatory `title=`:**

| File | Line | Current |
| --- | --- | --- |
| `web/components/sidebar.tsx` | 326 | `title="GitHub repository"` |
| `web/components/sidebar.tsx` | 206 | collapsed nav `title={collapsed ? label : undefined}` |
| `web/components/platform-icon.tsx` | 97 | `title={`${label} source`}` |
| `web/app/(dashboard)/prompts/page.tsx` | 61 | validation hint `title="Lowercase letters, digits, hyphens, underscores only"` |
| `web/app/(dashboard)/jobs/[id]/page.tsx` | 123 | copy button `title={ariaLabel}` (keep `aria-label`) |

**Replace overflow-reveal `title=` (use `mono` variant):**

| File | Line | Current |
| --- | --- | --- |
| `web/components/job-card.tsx` | 32 | `title={display}` |
| `web/components/feed/preview-card.tsx` | 98 | `title={display}` |
| `web/components/feed/preview-card.tsx` | 111 | `title={job.created_at}` |
| `web/app/(dashboard)/spaces/[id]/UrlsTab.tsx` | 60 | `title={display}` |
| `web/app/(dashboard)/jobs/[id]/page.tsx` | 199, 201 | URL `title={job.url}` |

**Net-new tooltips:**

- **Icon-only controls** — audit and add an accessible name on hover/focus to every
  icon-only affordance across feed / controls / brain / spaces toolbars.
- **Metric labels** — add tooltips to the metric numbers in
  `web/components/feed/stats-overview.tsx` clarifying what each metric counts and
  over what window. *(Verify which `stats-overview` `title=` props are real metrics
  vs. section/chart labels during planning — `:199`/`:204` appear to be section
  labels, not metrics.)*

**Excluded from migration:** `PageHeader title=` / section-component `title=` props
(`controls`, `prompts`, `brain`, `doc-parser`, `spaces`, `TagPicker` section
headings) — these are component props, not tooltips.

## Testing

Vitest + Testing Library (`web/`):

- Content shows on hover **and** on focus.
- `role="tooltip"` present; `aria-describedby` associates trigger ↔ content.
- Nullish `content` renders the child bare (no tooltip element).
- `mono` variant applies the mono font class.
- Reduced-motion path: no transform animation when `prefers-reduced-motion`.

No MSW needed — the primitive is presentational.

## Accessibility summary

- `role="tooltip"`, `aria-describedby` (Radix).
- Opens on focus-visible; Escape dismisses.
- `prefers-reduced-motion` respected.
- AA contrast verified for tooltip text on the `raised` plate.
