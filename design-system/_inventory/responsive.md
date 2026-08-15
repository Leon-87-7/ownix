# Responsive Layout Strategy Audit

## 1. Breakpoints

### Tailwind Defaults (In Use)
The codebase uses **unmodified Tailwind defaults** (no custom overrides in `web/tailwind.config.ts`, confirmed line 4-121):

- `sm` = 640px
- `md` = 768px  
- `lg` = 1024px
- `xl` = 1280px
- `2xl` = 1536px

**Usage**: Only `sm`, `md`, and `lg` appear in component code; `xl` and `2xl` are unused.

### Custom Hand-Written Media Queries (globals.css)
Five custom media queries guard responsive behaviour in `/home/user/ownix/web/app/globals.css`:

| Line | Query | Rule | Purpose |
|------|-------|------|---------|
| 9 | `(prefers-reduced-motion: no-preference)` | `html { scroll-behavior: smooth; }` | Smooth anchor scrolling for users who accept motion |
| 21 | `(min-width: 640px) and (prefers-reduced-motion: no-preference)` | `html { scroll-behavior: auto; }` | Override smooth scroll on desktop (GSAP ScrollTrigger desktop workaround) |
| 83 | `(prefers-reduced-motion: reduce)` | Global animation/transition kill-switch | Honour reduced-motion preference globally |
| 205 | `(prefers-reduced-motion: no-preference)` | Hero entrance animation `hero-rise` | Animate landing hero on load only if motion OK |
| 244 | `(min-height: 320px) and (prefers-reduced-motion: no-preference)` | `.stepper-runway` / `.stepper-stick` | Sticky mobile stepper: guarded on *both* height and motion preference (sticky elements taller than viewport park their bottom off-screen on landscape phones) |
| 387 | `(prefers-reduced-motion: no-preference)` | `.ownix-shimmer` gradient animation | Shimmer effect only under motion-safe |
| 411 | `(prefers-reduced-motion: no-preference)` | `.sidebar-mark-in` / `.sidebar-word-in` | Sidebar brand reveal animation on drawer open |

**Key insight**: The `min-height: 320px` guard at line 244 is load-bearing — it's the only place a viewport *height* media query appears, protecting the sticky stepper from breaking landscape phones.

## 2. Responsive Technique Breakdown

### Media Queries (Tailwind Prefixes)
**Dominant technique**. Widespread use of Tailwind's responsive prefixes across 126 occurrences (count: `/home/user/ownix/web/components/feed/stats-overview.tsx` + 35 other files).

**Prefix usage** (confirmed present):
- `sm:` (640px) — most common; used for mobile-first show/hide and layout rewrap
- `md:` (768px) — used for desktop feature reveals (graphs, sidebars)
- `lg:` (1024px) — used for large-screen layout expansion (3-column grids, sticky sidebars)

**Examples**:
- `sm:hidden` / `hidden sm:block` / `hidden sm:flex` — conditional visibility (9 occurrences)
- `sm:grid-cols-3` / `sm:flex-row` — layout rewrap
- `hidden md:block` — desktop-only brain graph visualization
- `hidden ... lg:block` / `lg:sticky` — large-screen sidebar stickiness

### JavaScript Viewport Detection (window.matchMedia)
**Secondary technique**. Used to sync JS state with CSS breakpoints; allows accessibility tree management (inert/aria-hidden) to match visual hiding.

**Files and queries**:

| File:Line | Query | Purpose |
|-----------|-------|---------|
| `/web/components/ui/filter-bar.tsx:253` | `(max-width: 639px)` | Track `< sm` breakpoint; collapse filter panel to disclosure + mark as `inert` on mobile |
| `/web/app/(dashboard)/jobs/[id]/page.tsx:745` | `(min-width: 768px)` | `useDesktopViewport()` hook — show/hide recipe choices layout based on md breakpoint |
| `/web/lib/hooks/useReducedMotion.ts:10` | `(prefers-reduced-motion: reduce)` | Global motion-preference detection; safe default = assume reduced until media query resolves |

**Pattern**: All use `addEventListener('change', ...)` to sync state on resize. No resize listeners; all rely on native matchMedia change events.

### Container Queries (@container)
**Not used**. Zero `@container` declarations found in codebase.

### GSAP.matchMedia (Scroll-Driven Animation)
**Specialized use**: Desktop landing page onboarding stepper only.

| File:Line | Query | Behaviour |
|-----------|-------|-----------|
| `/web/components/landing/onboarding-stepper.tsx:104-109` | `(min-width: 640px) and (prefers-reduced-motion: no-preference)` | GSAP `gsap.matchMedia()` — when query matches, register ScrollTrigger timeline that **pins the section** and overlaps the three stepper cards; when query stops matching (resize, motion-preference flip), reverts all changes to stacked layout. Desktop-only by design: scroll-jacking pins are unsafe on mobile (ADR-0038). |

**Link to globals.css**: Line 18-24 documents the exact same query, intentionally mirrored there to keep scroll-behavior and GSAP timeline in sync.

## 3. Markup / Behaviour Differences Between Viewports

The codebase **does render different component trees** for mobile vs desktop, not just different styles:

### Separate Mobile-Only & Desktop-Only Components

| Component | Mobile | Desktop | Difference |
|-----------|--------|---------|------------|
| `/web/components/landing/mobile-onboarding-stepper.tsx` (line 44: `sm:hidden`) | Tap-to-advance stepper with state machine (useState, onClick handlers) + sticky positioning | — | **Separate component file**. Mobile renders a button grid + arrow-advance controls + stateful step index. No JS scroll interaction. |
| `/web/components/landing/onboarding-stepper.tsx` (line 272: `hidden sm:motion-safe:grid`) | — | Scroll-driven GSAP timeline; steps overlapped, pinned to viewport | **Separate component file**. Desktop renders the same STEPS data but as a gsap.matchMedia animation. Only renders if `sm:` breakpoint + motion-safe. |

Both are called from the same parent (`web/app/page.tsx`), stacked in the DOM; CSS visibility hides the non-matching one.

### Conditional Rendering Within Components

| Component | Mobile (`< sm` / `< md` / `< lg`) | Desktop | Markup Difference |
|-----------|--------------------------------|---------|------------------|
| `/web/components/feed/stats-overview.tsx` | Lines 128–222: Collapsible disclosure (button + hidden grid expanding on click; inner state `open`). Shows compact `T/D/P/E` row + chevron animations. | Lines 224+: Grid of 5 stat cards (`hidden sm:grid sm:grid-cols-3 lg:grid-cols-5`). | **Entirely different markup tree**: mobile = 1 button + 1 nested grid; desktop = 5 separate StatCard components. Both rendered, CSS hides one. |
| `/web/components/brain/brain-graph.tsx` | — | Lines 181–201: Interactive D3 force-directed graph visualization + zoom controls (hidden on mobile with `hidden md:block`). | **Mobile gets nothing** (`md:block` means it's `hidden` below md). Desktop renders a 28rem-tall canvas. |
| `/web/components/shell/sidebar.tsx` | Lines 316–325: Fixed-position toggle button (6px wide, `sm:hidden`). Clicks setState to open a drawer. | Lines 328+: Persistent collapsed sidebar rail (16px, `hidden sm:flex`). Icons only, no drawer. | **Different structures**: mobile = button + drawer (modal/overlay interaction); desktop = always-visible rail. |
| `/web/components/shell/public-shell.tsx` | — | Lines 91–110: Sticky aside (`hidden ... lg:block`) containing legal nav sidebar. | Layout grid changes from 1-col to 2-col at lg. Mobile/tablet get no sidebar. |
| `/web/components/shell/app-header.tsx` | Lines 21–22: Centered branding + centered action grid (no submit button). | Lines 36, 90: Left-aligned branding + separator + command launcher button (`hidden ... sm:inline-flex`). | Visual layout rewrap + show/hide of secondary controls. |
| `/web/components/doc-parser/doc-upload-panel.tsx` | — | Lines 109+: Desktop-only upload button (`lg:hidden`). | Mobile lacks this button. |

**Key pattern**: When markup differs (not just styling), the `sm:hidden` / `hidden sm:block` / `hidden md:block` patterns combined with `.stepper-runway` + `.stepper-stick` CSS ensure both trees exist in the DOM and CSS controls visibility, **never conditional React rendering**.

### Pointer-Coarse Media Queries
Two components use `@media(pointer:coarse)` (touch-device adjustment):

| File:Line | Query | Adjustment |
|-----------|-------|------------|
| `/web/app/page.tsx:58, 61` | `[@media(pointer:coarse)]` | Landing buttons: increase height to `h-11` and padding to `px-5` for thumb-friendliness |
| `/web/components/landing/onboarding-stepper.tsx:370, 397` | `[@media(pointer:coarse)]` | Same desktop stepper buttons: larger on coarse pointers (touch) |

## 4. Design-System Gallery Build Verdict

### Answer: **Real CSS Media Queries — iframes Required**

**Reasoning**:

1. **Media queries dominate responsive behaviour**. `sm:` / `md:` / `lg:` prefixes and `@media()` rules control 100% of responsive adaptation. Container queries (`@container`) are absent.

2. **Viewport-width breakpoints are NOT negotiable**. The `sm` (640px), `md` (768px), and `lg` (1024px) breakpoints are hardcoded in Tailwind's default and referenced explicitly in:
   - `web/components/ui/filter-bar.tsx:253` — `window.matchMedia('(max-width: 639px)')`
   - `web/app/(dashboard)/jobs/[id]/page.tsx:745` — `window.matchMedia('(min-width: 768px)')`
   - `web/components/landing/onboarding-stepper.tsx:104-109` — `gsap.matchMedia('(min-width: 640px) and (prefers-reduced-motion: no-preference)')`

   These are **global viewport queries**, not container-specific. A `<div>` at 600px wide cannot pretend to be a 640px viewport.

3. **GSAP ScrollTrigger pinning depends on real viewport dimensions**. The desktop onboarding stepper (`onboarding-stepper.tsx` lines 104–200) uses GSAP's scroll-pinning, which measures against the browser's actual viewport, not a parent container.

4. **Markup trees differ, not just styling**. While both trees coexist in the DOM (CSS hides one), the component hierarchy, state management, and interaction patterns are fundamentally different:
   - Mobile stats overview: collapsible disclosure + nested grid
   - Desktop stats overview: flat grid of 5 cards
   - Mobile sidebar: drawer (modal-like, focus-trapping)
   - Desktop sidebar: always-visible rail
   
   **To test these properly, you need a real browser viewport** that can flip between 320px, 640px, 768px, and 1024px widths, triggering real media query changes and JS viewport detection (`window.matchMedia`).

5. **Reduced-motion cascades with viewport queries**. Line 244 of globals.css (`@media (min-height: 320px) and (prefers-reduced-motion: no-preference)`) shows the stepper guards are **not just about width**. A div-based container cannot be told "you are 320px tall" — only the actual viewport height is real.

### Conclusion
**You cannot use `<div>` containers with fake viewport constraints.** The gallery must render each component in a real `<iframe>` with its own resizable viewport (e.g., via `puppeteer`, `playwright`, or iframe `resize` events on the host), allowing components to:
- Respond to real CSS media queries (`(min-width: 640px)`, etc.)
- Trigger JavaScript `window.matchMedia` listeners
- Measure true viewport dimensions for GSAP ScrollTrigger
- Detect real `prefers-reduced-motion` and `prefers-color-scheme` from the host browser

**Alternative approach (not viable here)**: If container queries dominated and markup didn't differ, a single `<div>` at different widths could work. But this codebase relies on viewport queries, so that's off the table.
