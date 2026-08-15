# Design System Token Inventory

## 1. Canonical Token Sources & Relationships

### Source Hierarchy

| Source | Purpose | Scope |
|--------|---------|-------|
| **DESIGN.md** (lines 1–214) | Authoritative YAML frontmatter | Colors, typography, rounded, spacing, components |
| **web/tailwind.config.ts** | Tailwind theme.extend | Colors, fontFamily, fontSize, transitionTimingFunction, boxShadow, animation |
| **web/app/globals.css** | CSS custom properties & keyframes | Scrollbar vars (--sb-*), animations, transitions |

### Relationship Map

```
DESIGN.md frontmatter (source of truth)
    ↓
web/tailwind.config.ts (mirrors: colors, fontSize, fontFamily)
    ↓
Tailwind utilities (text-signal, bg-surface, etc.)
    ↓
web/app/globals.css
    ├── :root { --sb-track-color, --sb-thumb-color, etc. } (theme() references)
    └── @keyframes (animations referenced in tailwind.config.ts)
```

---

## 2. Complete Token Table

### Color Tokens

| Name | Value | Defined In | Type |
|------|-------|-----------|------|
| **canvas** | `#0d0e10` | DESIGN.md:5, tailwind.config.ts:9 | Page floor (near-black) |
| **surface** | `#16181c` | DESIGN.md:6, tailwind.config.ts:11 | Working layer (cards, rows) |
| **raised** | `#202329` | DESIGN.md:7, tailwind.config.ts:12 | Hover plates, active nav |
| **selected** | `#2a2e36` | DESIGN.md:8, tailwind.config.ts:17 | Selection plate (stepper carve-out) |
| **line.DEFAULT** | `#30343d` | DESIGN.md:9, tailwind.config.ts:19 | Default 1px border |
| **line.strong** | `#343a44` | DESIGN.md:10, tailwind.config.ts:20 | Emphasized borders |
| **ink** | `#e6e6e6` | DESIGN.md:11, tailwind.config.ts:22 | Primary text |
| **body** | `#b8b8b8` | DESIGN.md:12, tailwind.config.ts:23 | Secondary text |
| **muted** | `#948e84` | DESIGN.md:13, tailwind.config.ts:24 | Meta text |
| **signal.DEFAULT** | `#d99a45` | DESIGN.md:14, tailwind.config.ts:26 | Index Amber action |
| **signal.bright** | `#efb566` | DESIGN.md:15, tailwind.config.ts:27 | Hover state |
| **signal.deep** | `#a57534` | DESIGN.md:16, tailwind.config.ts:28 | Pressed state |
| **onsignal** | `#1b1309` | DESIGN.md:17, tailwind.config.ts:35 | Text on amber |
| **contrasignal.DEFAULT** | `#94e6ee` | DESIGN.md:18, tailwind.config.ts:31 | Cool accent |
| **contrasignal.bright** | `#9ec9ff` | DESIGN.md:19, tailwind.config.ts:32 | Cool accent bright |
| **contrasignal.deep** | `#649ca1` | DESIGN.md:20, tailwind.config.ts:33 | Cool accent deep |
| **status.done** | `#4ade80` | DESIGN.md:21, tailwind.config.ts:37 | Done status text |
| **status.done-tint** | `#122b1c` | DESIGN.md:22, tailwind.config.ts:38 | Done status background |
| **status.pending** | `#eab308` | DESIGN.md:23, tailwind.config.ts:39 | Pending status text |
| **status.pending-tint** | `#2b240e` | DESIGN.md:24, tailwind.config.ts:40 | Pending status background |
| **status.processing** | `#60a5fa` | DESIGN.md:25, tailwind.config.ts:41 | Processing status text |
| **status.processing-tint** | `#14233b` | DESIGN.md:26, tailwind.config.ts:42 | Processing status background |
| **status.enriching** | `#a78bfa` | DESIGN.md:27, tailwind.config.ts:43 | Enriching status text |
| **status.enriching-tint** | `#221a3d` | DESIGN.md:28, tailwind.config.ts:44 | Enriching status background |
| **status.error** | `#f87171` | DESIGN.md:29, tailwind.config.ts:45 | Error status text |
| **status.error-tint** | `#371717` | DESIGN.md:30, tailwind.config.ts:46 | Error status background |
| **status.cancelled** | `#9aa1ad` | DESIGN.md:31, tailwind.config.ts:47 | Cancelled status text |
| **status.cancelled-tint** | `#23262c` | DESIGN.md:32, tailwind.config.ts:48 | Cancelled status background |
| **type.short** | `#c084fc` | DESIGN.md:33, tailwind.config.ts:51 | Short video type |
| **type.long** | `#38bdf8` | DESIGN.md:34, tailwind.config.ts:52 | Long video type |
| **type.article** | `#2dd4bf` | DESIGN.md:35, tailwind.config.ts:53 | Article type |
| **type.repo** | `#fb7185` | DESIGN.md:36, tailwind.config.ts:54 | Repository type |
| **telegram-blue** | `#26A5E4` | DESIGN.md:39, tailwind.config.ts:56 | Telegram brand color |
| **telegram-ring** | `#145b7d` | DESIGN.md:40, tailwind.config.ts:57 | Telegram ring (doc hold spinner) |
| **google** | `#4285F4` | DESIGN.md:41, tailwind.config.ts:60 | Google brand color |

### Typography Tokens

#### Font Family

| Name | Value | Defined In |
|------|-------|-----------|
| **sans** | `'var(--font-inter)', 'system-ui', 'sans-serif'` | tailwind.config.ts:63 |
| **mono** | `'var(--font-jetbrains)', 'ui-monospace', 'SFMono-Regular', 'monospace'` | tailwind.config.ts:64-68 |
| **title** | `'var(--font-montserrat)', 'system-ui', 'sans-serif'` | tailwind.config.ts:71 |
| **subtitle** | `'var(--font-merienda)', 'Georgia', 'serif'` | tailwind.config.ts:72 |

#### Font Size

| Name | Value | Defined In | DESIGN.md Role |
|------|-------|-----------|-----------------|
| **micro** | `0.625rem` (10px) | tailwind.config.ts:89 | Dense table/chip text |
| **mono-label** | `0.6875rem` (11px) | tailwind.config.ts:90 | Mono Label |
| **label** | `0.75rem` (12px) | tailwind.config.ts:91 | Label + Mono Meta |
| **button** | `0.8125rem` (13px) | tailwind.config.ts:92 | Button |
| **copy** | `0.875rem` (14px) | tailwind.config.ts:93 | Body |
| **prose** | `0.9375rem` (15px) | tailwind.config.ts:94 | Landing section body |
| **title** | `1rem` (16px) | tailwind.config.ts:95 | Title |
| **lead** | `1.0625rem` (17px) | tailwind.config.ts:96 | Landing closing line |
| **headline** | `1.25rem` (20px) | tailwind.config.ts:97 | Headline |
| **stat** | `1.75rem` (28px) | tailwind.config.ts:98 | Stat Value |
| **display** | `1.5rem` (24px) | tailwind.config.ts:99 | Display |

### Spacing Tokens (from DESIGN.md)

| Name | Value |
|------|-------|
| **xxs** | `4px` |
| **xs** | `8px` |
| **sm** | `12px` |
| **md** | `16px` |
| **lg** | `24px` |
| **xl** | `32px` |
| **xxl** | `48px` |

### Rounded Tokens (from DESIGN.md)

| Name | Value |
|------|-------|
| **none** | `0px` |
| **sm** | `4px` |
| **md** | `6px` |
| **lg** | `8px` |
| **xl** | `12px` |

### Transition Timing Function

| Name | Value | Defined In |
|------|-------|-----------|
| **out-quart** | `cubic-bezier(0.25, 1, 0.5, 1)` | tailwind.config.ts:102 |

### Box Shadow

| Name | Value | Defined In | Usage |
|------|-------|-----------|-------|
| **overlay** | `0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)` | tailwind.config.ts:106-107 | Dialogs, dropdowns, toasts |

### Animation Tokens

| Name | Value | Defined In |
|------|-------|-----------|
| **tooltip-in** | `tooltip-in 140ms ease-out both` | tailwind.config.ts:110 |
| **tooltip-out** | `tooltip-out 100ms ease-out both` | tailwind.config.ts:111 |
| **slide-up-in** | `slide-up-in 180ms ease-out both` | tailwind.config.ts:112 |
| **slide-up-out** | `slide-up-out 140ms ease-out both` | tailwind.config.ts:113 |

### CSS Custom Properties (globals.css)

| Name | Definition | Resolved Value | Used For |
|------|-----------|-----------------|----------|
| **--sb-track-color** | `theme("colors.surface")` | `#16181c` | Scrollbar track |
| **--sb-thumb-color** | `theme("colors.line.DEFAULT")` | `#30343d` | Scrollbar thumb |
| **--sb-thumb-hover-color** | `theme("colors.line.strong")` | `#343a44` | Scrollbar thumb hover |
| **--sb-size** | `8px` | `8px` | Scrollbar width/height |

### Keyframe Animations (globals.css)

| Name | Description | Duration |
|------|-------------|----------|
| **doc-hold** | Telegram ring sweep (0deg → 360deg) | 1.5s linear |
| **chev-step-2** | Chevron 2 opacity pulse | 3s ease-in-out infinite |
| **chev-step-3** | Chevron 3 opacity pulse | 3s ease-in-out infinite |
| **hero-rise** | Landing hero cascade entrance | 600ms cubic-bezier() backwards |
| **auth-card-enter** | Auth page card entrance | N/A (defined but not used in animation rule) |
| **tooltip-in** | Tooltip fade in | 140ms ease-out |
| **tooltip-out** | Tooltip fade out | 100ms ease-out |
| **slide-up-in** | Slide up entrance | 180ms ease-out |
| **slide-up-out** | Slide up exit | 140ms ease-out |
| **wordmark-marquee** | Sidebar wordmark scroll loop | N/A (keyframes only) |
| **ownix-logo-cycle** | Brand mark 7-hue gradient sweep | Referenced in shimmer (3s linear) |
| **ownix-shimmer** | Gradient text animation | 3s linear infinite |
| **sidebar-mark-in** | Sidebar mark scale fade | 260ms cubic-bezier() |
| **sidebar-word-in** | Sidebar wordmark slide + fade | 280ms cubic-bezier() 70ms backwards |

---

## 3. Drift & Hard-Coded Values

### Critical Drift: Color Values in Component Files

| File | Line | Found Value | Token It Should Use | Category |
|------|------|-------------|-------------------|----------|
| web/app/offline/page.tsx | 14 | `#0d0e10` | `canvas` | Expected: offline page fallback |
| web/app/offline/page.tsx | 15 | `#f4f1eb` | `ink` | Expected: offline page fallback |
| web/app/offline/page.tsx | 24 | `#30343d` | `line.DEFAULT` | Expected: offline page fallback |
| web/app/offline/page.tsx | 25 | `#16181c` | `surface` | Expected: offline page fallback |
| web/app/offline/page.tsx | 37 | `#948e84` | `muted` | Expected: offline page fallback |
| web/app/offline/page.tsx | 60 | `#c6c1b8` | `body` | Expected: offline page fallback |
| web/app/offline/page.tsx | 74 | `#30343d` | `line.DEFAULT` | Expected: offline page fallback |
| web/app/offline/page.tsx | 75 | `#0d0e10` | `canvas` | Expected: offline page fallback |
| web/app/offline/page.tsx | 79 | `#c6c1b8` | `body` | Expected: offline page fallback |
| web/app/opengraph-image.tsx | 38 | `#a57534` | `signal.deep` | Expected: OG image (Satori can't use theme()) |
| web/app/opengraph-image.tsx | 42 | `#d99a45` | `signal.DEFAULT` | Expected: OG image |
| web/app/opengraph-image.tsx | 46 | `#efb566` | `signal.bright` | Expected: OG image |
| web/app/opengraph-image.tsx | 50 | `#c6c1b8` | `body` | Expected: OG image |
| web/app/opengraph-image.tsx | 54 | `#9ec9ff` | `contrasignal.bright` | Expected: OG image |
| web/app/opengraph-image.tsx | 58 | `#94e6ee` | `contrasignal.DEFAULT` | Expected: OG image |
| web/app/opengraph-image.tsx | 62 | `#649ca1` | `contrasignal.deep` | Expected: OG image |
| web/app/opengraph-image.tsx | 84 | `#0d0e10` | `canvas` | Expected: OG image |
| web/app/opengraph-image.tsx | 103 | `#f4f1eb` | `ink` | Expected: OG image |
| web/app/opengraph-image.tsx | 106 | `#948e84` | `muted` | Expected: OG image |
| web/app/opengraph-image.tsx | 117 | `#f4f1eb` | `ink` | Expected: OG image |
| web/app/opengraph-image.tsx | 120 | `#f4f1eb` | `ink` | Expected: OG image |
| web/app/opengraph-image.tsx | 123 | `#948e84` | `muted` | Expected: OG image |
| web/app/opengraph-image.tsx | 131 | `#c6c1b8` | `body` | Expected: OG image |
| web/components/ui/confirm-dialog.tsx | 68 | `#1b1309` | `onsignal` | Drift: should use token |
| web/components/brain/brain-graph.tsx | 38 | `#d99a45` | `signal.DEFAULT` | Expected: match highlight constant |
| web/components/brain/brain-graph.tsx | 31 | `#4f9cff` | Not in token system | Drift: arbitrary topic color |
| web/components/brain/brain-graph.tsx | 31 | `#34d399` | Not in token system | Drift: arbitrary topic color |
| web/components/brain/brain-graph.tsx | 31 | `#a78bfa` | `status.enriching` | Partial collision |
| web/components/brain/brain-graph.tsx | 31 | `#f472b6` | Not in token system | Drift: arbitrary topic color |
| web/components/brain/brain-graph.tsx | 31 | `#7dd3fc` | Not in token system | Drift: arbitrary topic color |
| web/components/brain/brain-graph.tsx | 31 | `#facc15` | Not in token system | Drift: arbitrary topic color |
| web/components/brain/brain-graph.tsx | 31 | `#fb7185` | `type.repo` | Partial collision |
| web/components/ui/tag-picker.tsx | 40 | `#f87171` | `status.error` | Matches token |
| web/components/ui/tag-picker.tsx | 41 | `#fb923c` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 42 | `#facc15` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 43 | `#4ade80` | `status.done` | Matches token |
| web/components/ui/tag-picker.tsx | 44 | `#2dd4bf` | `type.article` | Matches token |
| web/components/ui/tag-picker.tsx | 45 | `#22d3ee` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 46 | `#60a5fa` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 47 | `#8b5cf6` | Not in token system | Drift: arbitrary preset color (DEFAULT_COLOR) |
| web/components/ui/tag-picker.tsx | 48 | `#c084fc` | `type.short` | Matches token |
| web/components/ui/tag-picker.tsx | 49 | `#f472b6` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 50 | `#a16207` | Not in token system | Drift: arbitrary preset color |
| web/components/ui/tag-picker.tsx | 51 | `#f4f1eb` | `ink` | Matches token |

### SVG / Brand Icon Colors

| File | Line | Color | Purpose | Status |
|------|------|-------|---------|--------|
| web/components/svg/google-icon.tsx | 17-243 | Various (#0fbc5c, #ff4e3a, etc.) | Google brand gradient | Expected: brand asset |
| web/components/svg/instagram-icon.tsx | 17-66 | Various (#fc0, #ff005f, etc.) | Instagram brand gradient | Expected: brand asset |
| web/components/svg/tiktok-icon.tsx | Multiple | `#25f4ee`, `#fe2c55`, `#fff` | TikTok brand colors | Expected: brand asset |
| web/components/svg/youtube-icon.tsx | 14 | `#FFF` | YouTube brand | Expected: brand asset |
| web/components/svg/youtube-shorts-icon.tsx | 6 | `#FF0000` | YouTube brand | Expected: brand asset |
| web/components/svg/chrome-icon.tsx | 12-28 | Various (#229342, #fbc116, etc.) | Chrome brand gradient | Expected: brand asset |
| web/components/svg/telegram-icon.tsx | 12, 16 | `#26a5e4`, `#fff` | Telegram brand | Expected: brand asset (matches `telegram-blue`) |
| web/components/svg/pdf-icon.tsx | 9, 14, 19, 23 | `#ff2116`, `#f5f5f5`, `#2c2c2c` | PDF brand | Expected: brand asset |
| web/components/svg/openai-icon.tsx | 14 | `#fff` | OpenAI brand | Expected: brand asset |

### Arbitrary Tailwind Values

| File | Line | Arbitrary Value | Token It Should Use | Category |
|------|------|-----------------|-------------------|----------|
| web/app/page.tsx | 134 | `bg-[linear-gradient(115deg,rgba(13,14,16,0.75)_0%,...)]` | N/A | Expected: custom gradient (landing hero) |
| web/app/page.tsx | 148 | `text-[clamp(1.618rem,6vw,2.618rem)]` | Not in system | Landing fluid type |
| web/app/page.tsx | 250 | `text-[clamp(1.375rem,3.4vw,1.75rem)]` | Not in system | Landing fluid type |
| web/components/landing/mobile-onboarding-stepper.tsx | 53 | `text-[clamp(1.375rem,3.4vw,1.75rem)]` | Not in system | Landing fluid type |
| web/components/landing/mobile-onboarding-stepper.tsx | 141 | `text-[clamp(1.25rem,6vw,1.5rem)]` | Not in system | Landing fluid type |
| web/components/landing/onboarding-stepper.tsx | 328 | `text-[clamp(1.25rem,2.6vw,1.5rem)]` | Not in system | Landing fluid type |
| web/app/page.tsx | 325 | `[-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)]` | N/A | Expected: custom mask (landing) |
| web/app/page.tsx | 458 | `[-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)]` | N/A | Expected: custom mask (landing) |

### rgba() Values in Tailwind Classes

| File | Line | Value | Token Equivalent | Status |
|------|------|-------|-----------------|--------|
| web/components/feed/links-table.tsx | 651 | `shadow-[0_1px_0_rgba(255,255,255,0.03)]` | No shadow token for subtle lines | Drift: bespoke shadow |
| web/components/feed/links-table.tsx | 654 | `shadow-[0_1px_0_rgba(255,255,255,0.06)]` | No shadow token for subtle lines | Drift: bespoke shadow |
| web/components/brain/brain-graph.tsx | 38 | `rgba(140,148,160,0.28)` | No token for dim overlay | Drift: hardcoded dimming |
| web/components/brain/brain-graph.tsx | 242 | `rgba(140,148,160,0.20)` | No token for dim overlay | Drift: hardcoded dimming |

### CSS Keyframe Hardcoded Colors (globals.css)

These are *expected* as they are part of the visual animation design:

| File | Line | Colors | Purpose | Status |
|------|------|--------|---------|--------|
| web/app/globals.css | 327 | `#a57534`, `#d99a45`, `#efb566`, `#c6c1b8`, `#9ec9ff`, `#94e6ee`, `#649ca1` | ownix-logo-cycle keyframe | Expected: documented animation palette |
| web/app/globals.css | 389-397 | Same as above | ownix-shimmer keyframe | Expected: documented animation palette |

### Height/Width Arbitrary Values

| File | Line | Value | Reason | Status |
|------|------|-------|--------|--------|
| web/components/intake/intake-composer.tsx | 112 | `h-[104px]` | Specific component height | Spacing not in token system |
| web/components/feed/links-table.tsx | 346 | `min-h-[320px]`, `max-h-[70vh]` | Responsive layout | Spacing not in token system |
| web/components/shell/invite-gate.tsx | 50 | `min-h-[calc(100vh-3rem)]` | Full-height minus header | Layout not in token system |
| web/components/doc-parser/telegram-toggle.tsx | 48 | `h-[18px] w-[18px]` | Icon sizing | Not in token system |
| web/components/landing/app-slot.tsx | 58 | `h-[22px] w-[22px]` | Icon sizing | Not in token system |

---

## 4. Summary

### Canonical Sources
- **DESIGN.md** (lines 1–214): Single source of truth for all visual tokens
- **web/tailwind.config.ts**: Mirrors colors, fontSize, fontFamily into Tailwind
- **web/app/globals.css**: CSS custom properties for scrollbar, animations, and keyframes

### Token Coverage

✓ **Well-tokenized:**
- Color palette (33 tokens)
- Font families (4 fallback stacks)
- Font sizes (11 size scales)
- Transition timing (1 curve)
- Box shadow (1 overlay shadow)
- Animations (4 Tailwind animations + 13 keyframes)

⚠ **Gaps (not in token system):**
- Spacing/sizing for specific components (arbitrary h-, w-, max-h-, min-h- values)
- Layout dimensions (viewport-relative calc() values)
- Topic colors for brain graph (7 colors in TOPIC_COLORS array)
- Tag preset colors (12 colors, 4 match tokens, 8 drift)
- Subtle rgba() overlays for tables and graphs
- Landing-only fluid type scales (clamp() values)

### Drift Assessment

**Total hard-coded color values found:** 120+ (excluding test files and brand assets)

**Genuine drift (should use tokens):**
- `text-[#1b1309]` in confirm-dialog.tsx:68 → should use `onsignal` token
- Topic colors array (7 bespoke hues for brain visualization)
- Tag color presets (8 colors outside the system)
- Table/graph rgba() overlays (no tokens for subtle lines)

**Expected/Legitimate hard-coding:**
- offline/page.tsx: System font styles for offline fallback (no JS available)
- opengraph-image.tsx: Satori cannot read theme() in OG render
- SVG brand assets: Google, Instagram, TikTok, YouTube, Chrome, PDF, OpenAI (brand IP)
- globals.css keyframes: Documented animation palette (comment-annotated)
- Landing-only arbitrary sizes: Fluid type (clamp values) not part of dashboard token set

