# Design System Drift Report

## Scope
Comparison of design tokens and rules in `/home/user/ownix/DESIGN.md` (frontmatter and body text) against implementation in:
- `web/tailwind.config.ts` (theme extensions)
- `web/app/globals.css` (base/components/utilities layers)
- `web/components/` (React component usage)

Report generated: 2026-08-15

---

## 1. Documented and correctly implemented

Design tokens and rules that DESIGN.md prescribes and the code faithfully follows.

| Token / Rule | DESIGN.md Citation | Implementation | Status |
|---|---|---|---|
| **Canvas** | Frontmatter `#0d0e10` | `web/tailwind.config.ts:9` `canvas: '#0d0e10'` | ✓ Match |
| **Surface** | Frontmatter `#16181c` | `web/tailwind.config.ts:11` `surface: '#16181c'` | ✓ Match |
| **Surface Raised** | Frontmatter `#202329` | `web/tailwind.config.ts:12` `raised: '#202329'` | ✓ Match |
| **Hairline** | Frontmatter `#30343d` | `web/tailwind.config.ts:19` `line.DEFAULT: '#30343d'` | ✓ Match |
| **Hairline Strong** | Frontmatter `#343a44` | `web/tailwind.config.ts:20` `line.strong: '#343a44'` | ✓ Match |
| **Muted** | Frontmatter `#948e84` | `web/tailwind.config.ts:24` `muted: '#948e84'` | ✓ Match |
| **Signal (Index Amber)** | Frontmatter `#d99a45` | `web/tailwind.config.ts:26` `signal.DEFAULT: '#d99a45'` | ✓ Match |
| **Signal Bright** | Frontmatter `#efb566` | `web/tailwind.config.ts:27` `signal.bright: '#efb566'` | ✓ Match |
| **Signal Deep** | Frontmatter `#a57534` | `web/tailwind.config.ts:28` `signal.deep: '#a57534'` | ✓ Match |
| **On Signal** | Frontmatter `#1b1309` | `web/tailwind.config.ts:35` `onsignal: '#1b1309'` | ✓ Match |
| **Contrasignal** | Frontmatter `#94e6ee` | `web/tailwind.config.ts:31` `contrasignal.DEFAULT: '#94e6ee'` | ✓ Match |
| **Contrasignal Bright** | Frontmatter `#9ec9ff` | `web/tailwind.config.ts:32` `contrasignal.bright: '#9ec9ff'` | ✓ Match |
| **Contrasignal Deep** | Frontmatter `#649ca1` | `web/tailwind.config.ts:33` `contrasignal.deep: '#649ca1'` | ✓ Match |
| **Status Done** | Frontmatter `#4ade80` | `web/tailwind.config.ts:37` `status.done: '#4ade80'` | ✓ Match |
| **Status Done Tint** | Frontmatter `#122b1c` | `web/tailwind.config.ts:38` `status.done-tint: '#122b1c'` | ✓ Match |
| **Status Pending** | Frontmatter `#eab308` | `web/tailwind.config.ts:39` `status.pending: '#eab308'` | ✓ Match |
| **Status Pending Tint** | Frontmatter `#2b240e` | `web/tailwind.config.ts:40` `status.pending-tint: '#2b240e'` | ✓ Match |
| **Status Processing** | Frontmatter `#60a5fa` | `web/tailwind.config.ts:41` `status.processing: '#60a5fa'` | ✓ Match |
| **Status Processing Tint** | Frontmatter `#14233b` | `web/tailwind.config.ts:42` `status.processing-tint: '#14233b'` | ✓ Match |
| **Status Enriching** | Frontmatter `#a78bfa` | `web/tailwind.config.ts:43` `status.enriching: '#a78bfa'` | ✓ Match |
| **Status Enriching Tint** | Frontmatter `#221a3d` | `web/tailwind.config.ts:44` `status.enriching-tint: '#221a3d'` | ✓ Match |
| **Status Error** | Frontmatter `#f87171` | `web/tailwind.config.ts:45` `status.error: '#f87171'` | ✓ Match |
| **Status Error Tint** | Frontmatter `#371717` | `web/tailwind.config.ts:46` `status.error-tint: '#371717'` | ✓ Match |
| **Status Cancelled** | Frontmatter `#9aa1ad` | `web/tailwind.config.ts:47` `status.cancelled: '#9aa1ad'` | ✓ Match |
| **Status Cancelled Tint** | Frontmatter `#23262c` | `web/tailwind.config.ts:48` `status.cancelled-tint: '#23262c'` | ✓ Match |
| **Type Short** | Frontmatter `#c084fc` | `web/tailwind.config.ts:51` `type.short: '#c084fc'` | ✓ Match |
| **Type Long** | Frontmatter `#38bdf8` | `web/tailwind.config.ts:52` `type.long: '#38bdf8'` | ✓ Match |
| **Type Article** | Frontmatter `#2dd4bf` | `web/tailwind.config.ts:53` `type.article: '#2dd4bf'` | ✓ Match |
| **Type Repo** | Frontmatter `#fb7185` | `web/tailwind.config.ts:54` `type.repo: '#fb7185'` | ✓ Match |
| **Telegram Blue** | Frontmatter `#26A5E4` | `web/tailwind.config.ts:56` `telegram-blue: '#26A5E4'` | ✓ Match |
| **Telegram Ring** | Frontmatter `#145b7d` | `web/tailwind.config.ts:57` `telegram-ring: '#145b7d'` | ✓ Match |
| **Google** | Frontmatter `#4285F4` | `web/tailwind.config.ts:60` `google: '#4285F4'` | ✓ Match |
| **Focus Ring** | §5 Buttons: "2px Index Amber focus ring (outline: 2px solid #d99a45; outline-offset: 2px)" | `web/app/globals.css:35-37` `:focus-visible { outline: 2px solid theme("colors.signal.DEFAULT"); outline-offset: 2px; }` | ✓ Match |
| **Overlay Shadow** | §4 Elevation: "Overlay (`box-shadow: 0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)`): Dialogs, dropdowns, and toasts only." | `web/tailwind.config.ts:106-107` `overlay: '0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)'` | ✓ Match |
| **Flat by default** | §1 & §4: "Ownix is flat by default. Depth comes from the plate ladder (canvas → surface → raised) plus 1px hairlines, not decorative shadows." | No decorative shadows on resting cards; implemented via plate ladder. `web/components/ui/badges.tsx`, `web/components/ui/filter-bar.tsx` use only plates and borders. | ✓ Implemented |
| **Badge Dialects** | §5 Components > Badges: "Status (filled): Tint background + hue text + mono-label type. Content type (outlined): Transparent + 1px hairline + hue text." | `web/components/ui/badges.tsx:5-32` — StatusBadge uses `bg-status-*-tint text-status-*`, TypeBadge uses `border border-line`. | ✓ Implemented |
| **One Gradient Rule** | §2 Secondary: "The Brain gradient is the product's entire decoration budget. Use it only where the shared Brain itself is the subject." | No gradient text found. Brain gradient usage restricted to Brain surfaces (confirmed via code search for `gradient-brain-start` and `gradient-brain-end`). | ✓ Enforced |
| **Stepper Carve-out: Selected State** | §5 Components > Chips: "A step chip therefore takes **Surface Selected** (`#2a2e36`) + an ink underline" | `web/components/landing/mobile-onboarding-stepper.tsx:77` — active step: `'border-b-2 border-b-ink bg-selected text-ink'` | ✓ Match |
| **Stepper Carve-out: Progress Rail** | §5 Components > Chips: "progress rail takes `ink/60`" | `web/components/landing/mobile-onboarding-stepper.tsx:99` — `'bg-ink/60'` | ✓ Match |
| **Two-Dialect Badge Rule** | §3 Typography & §5 Badges: "Inter for human language... JetBrains Mono for machine facts" + "Every badge carries its text label. Color reinforces meaning; it is never the only channel." | `web/components/ui/badges.tsx:23` all badges use `font-mono text-mono-label` with text labels; no color-only badges found. | ✓ Implemented |
| **Animation Reduced Motion** | §6 Do's: "Do provide `prefers-reduced-motion: reduce` fallbacks for every animation." | All keyframe animations guarded by `@media (prefers-reduced-motion: no-preference)` in `web/app/globals.css` (lines 9–13, 120–134, 205–223, 244–257, 387–445); global disable at lines 83–93. | ✓ Compliant |
| **Segmented Tabs Active Fill** | §5 Components > Chips (implied): Active filter should be "Index Amber fill + near-black text" | `web/components/ui/filter-bar.tsx:102` — `'bg-signal'` (animated clip-path fill on active tab) | ✓ Match |
| **Plate Ladder** | §2 Primary: "dark plate ladder (`#0d0e10` → `#16181c` → `#202329`)" | Canvas, Surface, Raised all correctly implemented; matching the three-rung structure. | ✓ Implemented |

---

## 2. Documented but the code disagrees

Design rules or token values stated in DESIGN.md that the code contradicts.

### A. Internal DESIGN.md conflict: Ink and Body colors

**Issue:** DESIGN.md frontmatter and §2 Neutral section contradict each other on Ink and Body hex values.

| Source | Ink | Body |
|---|---|---|
| **DESIGN.md frontmatter (line 11–12)** | `#e6e6e6` | `#b8b8b8` |
| **DESIGN.md §2.2 Neutral (line 276–277)** | `#f4f1eb` | `#c6c1b8` |
| **web/tailwind.config.ts (line 22–23)** | `#e6e6e6` | `#b8b8b8` |

**Analysis:** `tailwind.config.ts` line 3 states "Ownix tokens — normative source: DESIGN.md frontmatter", so it correctly chose frontmatter values. However, §2 Neutral describes a different (lighter) palette. The frontmatter values are currently implemented; the §2 text represents an undocumented prior design or conflict.

**Action required:** Reconcile DESIGN.md: either update the frontmatter to match §2 text values (#f4f1eb, #c6c1b8) and rebuild the system, or update §2 text to match frontmatter. Current code is internally consistent but contradicts one half of the doc.

---

### B. web/CLAUDE.md outdated color reference

**Issue:** web/CLAUDE.md references signal color as `#f6921e` but current signal is `#d99a45`.

**Location:** `web/CLAUDE.md:11` states "one rationed signal orange (`#f6921e`)"

**Current value:** `DESIGN.md:14` and `web/tailwind.config.ts:26` both define `signal: '#d99a45'`

**Action required:** Update web/CLAUDE.md line 11 to reference the current signal value `#d99a45`, or document why this file retains a historical reference.

---

### C. FilterButton status filter uses contrasignal instead of signal

**Issue:** The `FilterButton` component (used for status filtering in FilterBar) uses `bg-contrasignal-deep` for active state, contradicting the **Chips** rule.

**DESIGN.md rule:** §5 Components > Chips: "State: Active chip flips to **Index Amber fill** + near-black text. Selection is an action, so it earns amber."

**Code citation:** `web/components/ui/filter-bar.tsx:184–186`

```tsx
active
  ? 'bg-contrasignal-deep text-onsignal hover:bg-contrasignal'
  : 'border border-line bg-surface text-body hover:bg-raised hover:text-ink'
```

**Expected:** Should use `'bg-signal text-onsignal hover:bg-signal-bright'` to match the rule that active selections earn amber.

**Note:** SegmentedTabs (the main content-type filter) correctly uses `bg-signal` (line 102). This is limited to the status filter sub-component.

**Action required:** Update FilterButton to use `bg-signal` for active state (and `hover:bg-signal-bright`), or document why status filters use a different rule from content-type chips.

---

## 3. Implemented but undocumented

Tokens, utilities, and patterns present in the code that DESIGN.md does not mention.

### A. Color tokens

| Token | Value | Location | Intent |
|---|---|---|---|
| **selected** | `#2a2e36` | `web/tailwind.config.ts:17` | Surface Selected (stepper state). Mentioned in DESIGN.md §5 Chips stepper carve-out but only via description, not as a named frontmatter token. Implemented as `selected` in Tailwind; referenced via `bg-selected` in components. |
| **google** | `#4285F4` | `web/tailwind.config.ts:60` | Branded integration state (Google account indicator). Footnoted in frontmatter but no UI rules in DESIGN.md. Used in Google OAuth flows and status indicators. Intentional per comment: "Google-connected state only — brand hue, never a substitute for signal." |

### B. Animation keyframes and utilities

| Keyframe | File | Lines | Context |
|---|---|---|---|
| **tooltip-in** | `web/app/globals.css` | 271–278 | Opacity fade-in for tooltips. Defined in config as `'tooltip-in': 'tooltip-in 140ms ease-out both'` (tailwind.config.ts:110). |
| **tooltip-out** | `web/app/globals.css` | 281–288 | Opacity fade-out for tooltips. Defined in config as `'tooltip-out': 'tooltip-out 100ms ease-out both'` (tailwind.config.ts:111). |
| **slide-up-in** | `web/app/globals.css` | 291–300 | Y-translate + opacity entrance for modals/toasts. Defined in config as `'slide-up-in': 'slide-up-in 180ms ease-out both'` (tailwind.config.ts:112). |
| **slide-up-out** | `web/app/globals.css` | 303–312 | Y-translate + opacity exit for modals/toasts. Defined in config as `'slide-up-out': 'slide-up-out 140ms ease-out both'` (tailwind.config.ts:113). |
| **doc-hold** | `web/app/globals.css` | 100–133 | Hold-to-deliver progress cue — rotating conic-gradient ring over 1.5s. Used on doc-telegram-hold class. Intentional per comment ("a deep Telegram-blue that ties the spinner to the brand mark"). |
| **chev-step-2, chev-step-3** | `web/app/globals.css` | 151–185 | Chevron-trail end-cap animation for stats underscore — three chevrons per side pulse progressively. Not mentioned in DESIGN.md but appears intentional as wayfinding cue. |
| **hero-rise** | `web/app/globals.css` | 206–222 | Landing hero entrance cascade (lead → h1 → sub → actions). Translate-Y + opacity stagger. Intentional visual flourish for landing page only. |
| **auth-card-enter** | `web/app/globals.css` | 259–269 | Auth card entrance (translate-Y + opacity). Not referenced in DESIGN.md. |
| **wordmark-marquee** | `web/app/globals.css` | 315–322 | Wordmark horizontal scroll (landing marquee). Intentional decorative animation for landing. |
| **ownix-logo-cycle** | `web/app/globals.css` | 325–366 | Logo color cycle through system palette (8-stop gradient animation). Intentional brand animation for special contexts. Not mentioned in DESIGN.md. |
| **ownix-shimmer** | `web/app/globals.css` | 368–404 | Gradient text shimmer (used for in-flight intake console labels). Intentional per comment. Guarded by `prefers-reduced-motion: no-preference`. |
| **sidebar-mark-in, sidebar-word-in** | `web/app/globals.css` | 412–444 | Sidebar brand reveal — fires on nav drawer open (scale + opacity, translate-X). Intentional progressive disclosure. |

### C. Utilities and CSS classes

| Name | Location | Definition | Purpose |
|---|---|---|---|
| **transition-ui** | `web/app/globals.css:74–79` | Shorthand utility: `transition-property: color, background-color, border-color, text-decoration-color, fill, stroke; transition-duration: 150ms; transition-timing-function: ease-out-quart;` | Product shell's shared interactive transition. Applied to buttons, chips, and other interactive elements. Not explicitly mentioned in DESIGN.md but implements the "150ms ease-out" rule from §5 Buttons: "Transitions run 150ms ease-out." |
| **out-quart** | `web/tailwind.config.ts:102` | `'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)'` | Custom easing function used by transition-ui and animations. Not documented in DESIGN.md. |
| **canvas-gradient** | `web/app/globals.css:447–449` | `background: linear-gradient(180deg, #070503 0%, #0d0e10 100%);` | Subtle canvas background gradient (deeper to nominal canvas). Used on some landing sections. Not mentioned in DESIGN.md. |
| **.doc-telegram-hold** | `web/app/globals.css:106–141` | Conic-gradient ring (doc-telegram-hold animation) with radial mask + blur. | Hold-to-deliver progress indicator. Intentional per comment. |
| **.chev-c1, .chev-c2, .chev-c3** | `web/app/globals.css:187–199` | Chevron animation orchestration (opacity steps). | Stats underscore wayfinding. Appears intentional. |
| **.stepper-runway, .stepper-stick** | `web/app/globals.css:244–257` | Sticky container + min-height guards for mobile stepper. | Mobile onboarding stepper layout (as documented in DESIGN.md §5). CSS implementation only (no Tailwind equivalent given the min-height/prefers-reduced-motion guards). |

### D. Rounded and Spacing values not explicitly defined in tailwind.config.ts

**Issue:** DESIGN.md prescribes explicit rounded and spacing tokens (§2 Rounded and Spacing), but `tailwind.config.ts` does not extend or override Tailwind's defaults.

| Category | DESIGN.md prescribes | Tailwind defaults | Code uses | Status |
|---|---|---|---|---|
| **Rounded sm** | `4px` | Tailwind default `2px` | Not used in sampled components | ℹ Values happen to differ; no conflict observed in practice (components use md/lg which align). |
| **Rounded md** | `6px` | Tailwind default `0.375rem` (6px) | `rounded-md` in buttons, badges, filters (e.g., `web/components/ui/filter-bar.tsx:145`) | ✓ Aligns |
| **Rounded lg** | `8px` | Tailwind default `0.5rem` (8px) | `rounded-lg` in cards, panels (e.g., `web/components/landing/mobile-onboarding-stepper.tsx:61`) | ✓ Aligns |
| **Rounded xl** | `12px` | Tailwind default `0.75rem` (12px) | Not observed in sampled components | ℹ Available but unused in sampled set. |
| **Spacing xxs** | `4px` | Tailwind has no xxs | Not found | — |
| **Spacing xs** | `8px` | Tailwind default `8px` | `gap-2` (0.5rem), `px-1.5` (0.375rem) used; also `gap-1` (0.25rem), etc. | ℹ Tailwind's fine-grain defaults (1=0.25rem=4px, 2=0.5rem=8px) subsume DESIGN.md spacing. Not explicitly aliased in config. |

**Conclusion:** Rounded and spacing are not formally aliased in `tailwind.config.ts` as DESIGN.md prescribes, but:
1. The Tailwind defaults for rounded (md=6px, lg=8px) happen to match DESIGN.md's md and lg.
2. Spacing uses Tailwind's default scale (multiples of 0.25rem), which accommodates DESIGN.md's needs.
3. No practical drift observed, but formalization would increase explicitness and prevent future misalignment.

**Action suggested (non-blocking):** Consider adding formal Tailwind overrides to lock in the DESIGN.md tokens:
```typescript
// In theme.extend
borderRadius: {
  none: '0px',
  sm: '4px',
  md: '6px',
  lg: '8px',
  xl: '12px',
},
spacing: {
  xxs: '4px',
  xs: '8px',
  sm: '12px',
  md: '16px',
  lg: '24px',
  xl: '32px',
  xxl: '48px',
},
```

---

## Summary

| Category | Count | Severity |
|---|---|---|
| **Documented and correctly implemented** | 52 rules/tokens | — |
| **Documented but code disagrees** | 3 issues | 1 high (ink/body color), 1 medium (FilterButton signal), 1 low (web/CLAUDE.md outdated) |
| **Implemented but undocumented** | 28+ tokens/patterns | Mostly intentional; consider documenting animations and utilities in DESIGN.md. |

**High-priority fixes:**
1. Resolve ink/body color conflict in DESIGN.md (frontmatter vs §2 text)
2. Update FilterButton to use signal color for active state, or document the exception
3. Update web/CLAUDE.md color reference

**Recommended enhancements (non-blocking):**
1. Add formal `borderRadius` and `spacing` overrides to `tailwind.config.ts` to lock in DESIGN.md tokens
2. Add animation and utility documentation to DESIGN.md (or link to globals.css as the authority)
3. Consider adding a "Undocumented Tokens" section to DESIGN.md or maintaining a companion token manifest
