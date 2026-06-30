---
name: vig — Video Intelligence Gateway
description: A dark operator's console — cool near-black chassis, mono technical voice, one rationed orange signal, status as the loudest layer.
colors:
  canvas: '#0b0c0f'
  surface: '#14161a'
  surface-raised: '#1c1f25'
  hairline: '#262a31'
  hairline-strong: '#343a44'
  ink: '#f5f6f8'
  body: '#b3b9c4'
  muted: '#8a919e'
  signal: '#f6921e'
  signal-bright: '#ffa83d'
  signal-deep: '#b96a06'
  on-signal: '#16100a'
  status-done: '#4ade80'
  status-done-tint: '#122b1c'
  status-pending: '#eab308'
  status-pending-tint: '#2b240e'
  status-processing: '#60a5fa'
  status-processing-tint: '#14233b'
  status-enriching: '#a78bfa'
  status-enriching-tint: '#221a3d'
  status-error: '#f87171'
  status-error-tint: '#371717'
  status-cancelled: '#9aa1ad'
  status-cancelled-tint: '#23262c'
  type-short: '#c084fc'
  type-long: '#38bdf8'
  type-article: '#2dd4bf'
  type-repo: '#fb7185'
  gradient-brain-start: '#7c3aed'
  gradient-brain-end: '#22d3ee'
  telegram-blue: '#26A5E4'
  telegram-ring: '#145b7d'
typography:
  display:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '24px'
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: '-0.5px'
  headline:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '20px'
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: '-0.25px'
  title:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '16px'
    fontWeight: 600
    lineHeight: 1.4
  body:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '14px'
    fontWeight: 400
    lineHeight: 1.5
  body-strong:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '14px'
    fontWeight: 500
    lineHeight: 1.5
  label:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '12px'
    fontWeight: 500
    lineHeight: 1.4
  stat-value:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '28px'
    fontWeight: 600
    lineHeight: 1.1
    fontFeature: 'tnum'
  mono-meta:
    fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: '12px'
    fontWeight: 400
    lineHeight: 1.4
  mono-label:
    fontFamily: "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: '11px'
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: '0.4px'
  button:
    fontFamily: 'Inter, system-ui, -apple-system, sans-serif'
    fontSize: '13px'
    fontWeight: 500
    lineHeight: 1.0
rounded:
  none: '0px'
  sm: '4px'
  md: '6px'
  lg: '8px'
  xl: '12px'
spacing:
  xxs: '4px'
  xs: '8px'
  sm: '12px'
  md: '16px'
  lg: '24px'
  xl: '32px'
  xxl: '48px'
components:
  button-signal:
    backgroundColor: '{colors.signal}'
    textColor: '{colors.on-signal}'
    typography: '{typography.button}'
    rounded: '{rounded.md}'
    padding: '0px 14px'
    height: '32px'
  button-signal-hover:
    backgroundColor: '{colors.signal-bright}'
    textColor: '{colors.on-signal}'
    rounded: '{rounded.md}'
  button-ghost:
    backgroundColor: 'transparent'
    textColor: '{colors.ink}'
    typography: '{typography.button}'
    rounded: '{rounded.md}'
    padding: '0px 14px'
    height: '32px'
  button-ghost-hover:
    backgroundColor: '{colors.surface-raised}'
    textColor: '{colors.ink}'
    rounded: '{rounded.md}'
  filter-chip:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.body}'
    typography: '{typography.button}'
    rounded: '{rounded.md}'
    padding: '0px 12px'
    height: '28px'
  filter-chip-active:
    backgroundColor: '{colors.signal}'
    textColor: '{colors.on-signal}'
    typography: '{typography.button}'
    rounded: '{rounded.md}'
    padding: '0px 12px'
    height: '28px'
  badge-status:
    backgroundColor: '{colors.status-done-tint}'
    textColor: '{colors.status-done}'
    typography: '{typography.mono-label}'
    rounded: '{rounded.sm}'
    padding: '2px 6px'
  badge-type:
    backgroundColor: 'transparent'
    textColor: '{colors.type-short}'
    typography: '{typography.mono-label}'
    rounded: '{rounded.sm}'
    padding: '2px 6px'
  card:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    typography: '{typography.body}'
    rounded: '{rounded.lg}'
    padding: '{spacing.md}'
  job-row:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    typography: '{typography.body}'
    rounded: '{rounded.lg}'
    padding: '12px 16px'
  job-row-hover:
    backgroundColor: '{colors.surface-raised}'
    textColor: '{colors.ink}'
    rounded: '{rounded.lg}'
  stat-card:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.ink}'
    typography: '{typography.stat-value}'
    rounded: '{rounded.lg}'
    padding: '12px 16px'
  text-input:
    backgroundColor: '{colors.canvas}'
    textColor: '{colors.ink}'
    typography: '{typography.body}'
    rounded: '{rounded.md}'
    padding: '0px 12px'
    height: '36px'
  sidebar:
    backgroundColor: '{colors.surface}'
    textColor: '{colors.body}'
    typography: '{typography.body-strong}'
    width: '208px'
    padding: '{spacing.lg} {spacing.md}'
  nav-item:
    backgroundColor: 'transparent'
    textColor: '{colors.body}'
    typography: '{typography.body-strong}'
    rounded: '{rounded.md}'
    padding: '8px 12px'
  nav-item-active:
    backgroundColor: '{colors.surface-raised}'
    textColor: '{colors.signal}'
    typography: '{typography.body-strong}'
    rounded: '{rounded.md}'
    padding: '8px 12px'
---

# Design System: vig — Video Intelligence Gateway

## 1. Overview

**Creative North Star: "The Operator's Console"**

The vig dashboard is the faceplate of a machine you command. Every panel is a
control surface; every glow is a state. The system synthesizes three lineages
into one dark console: **Vercel's stark ink discipline** supplies the chassis —
cool near-black surfaces, hairline borders, negative-tracked display type, and a
monospace voice for everything the machine says; **Nintendo 2001's signal
doctrine** supplies the energy — warm color is rationed strictly to mean _act
here_, and never decorates; **Expo's restraint** supplies the ceiling — weights
stop at 600, depth stays at hairlines and plates, and decoration is spent on
exactly one signature moment (the Brain gradient).

The result is bold through commitment, not noise. The chassis is so disciplined
— cool, dark, quiet — that the rationed orange signal and the semantic status
hues become the loudest things on screen, which is exactly the point:
PRODUCT.md's first principle is _state at a glance_. This system explicitly
rejects its two failure modes: the **cluttered enterprise admin** (gray-on-gray
density with no hierarchy — the fate of the current monochrome shell if left
alone) and the **toy / consumer-cute** (rounded-everything, bouncy, jokey).
The console is a sharp instrument an operator trusts daily and a future
customer would pay for.

**Key Characteristics:**

- Cool near-black plate ladder (`#0b0c0f` → `#14161a` → `#1c1f25`) with 1px hairlines — depth is structural, not floating.
- One warm signal: orange `#f6921e` appears _only_ on things the operator can act on (primary actions, active selections, focus, active nav).
- Status is the loudest layer: filled tint badges in semantic hues, always paired with a text label.
- Two voices: Inter (human language) and JetBrains Mono (machine facts — job IDs, timestamps, URLs, statuses, counts).
- Flat by default; shadows exist only for overlays (modals, dropdowns, toasts).
- One decorative moment in the whole product: the violet→cyan Brain gradient, hero-scale, `/brain` only.
- Density is welcome — the console is an information tool — but every element must earn its place.

## 2. Colors: The Console Palette

A cool dark chassis with one rationed warm signal and a semantic status vocabulary — warmth always means _action_, hue always means _state_.

### Primary

- **Signal Orange** (`#f6921e`): The single action color. Fills the primary button, the active filter chip, the focus ring, and tints the active nav item's text. If it glows signal orange, the operator can act on it — submit, retry, select, navigate. It never appears in a status badge, never as decoration, and never on a disabled control.
- **Signal Bright** (`#ffa83d`): Hover state of signal surfaces.
- **Signal Deep** (`#b96a06`): Pressed state.
- **On Signal** (`#16100a`): Near-black text on signal fills — the Nintendo amber-chip move; dark-on-orange reads sharper than white-on-orange and holds ≥7:1.

### Secondary

- **Brain Gradient** (`#7c3aed` → `#22d3ee`): The one decorative system. A violet-to-cyan atmospheric wash representing the semantic link graph, used at hero scale on the `/brain` surface only. Never miniaturized to an icon, never on buttons, never as text fill.

### Neutral

- **Canvas** (`#0b0c0f`): The page floor — near-black with a cool cast. Inputs are inset to this level.
- **Surface** (`#14161a`): The working plate — cards, job rows, sidebar, stat tiles.
- **Surface Raised** (`#1c1f25`): Hover plates and the active nav plate — one step toward the light.
- **Hairline** (`#262a31`): Default 1px border on every plate and input.
- **Hairline Strong** (`#343a44`): Emphasized borders (hover on inputs, table header rules).
- **Ink** (`#f5f6f8`): Headings and primary content text.
- **Body** (`#b3b9c4`): Secondary text — descriptions, nav labels at rest (≈9:1 on surface).
- **Muted** (`#8a919e`): Meta text — timestamps, counts, placeholders. Held at ≥4.5:1 on both canvas and surface; this token exists precisely to retire the failing `gray-500`.

### Semantic — Status (filled badges: tint background + hue text)

- **Done** (`#4ade80` on `#122b1c`): Job complete.
- **Pending** (`#eab308` on `#2b240e`): Queued, waiting.
- **Processing** (`#60a5fa` on `#14233b`): Actively running.
- **Enriching** (`#a78bfa` on `#221a3d`): Gemini enrichment phase (also covers `transcript_done`).
- **Error** (`#f87171` on `#371717`): Failed — pairs with a signal-orange retry action.
- **Cancelled** (`#9aa1ad` on `#23262c`): Terminated, inert.

### Semantic — Content type (outlined badges: transparent background + hue text + hairline)

- **Short** (`#c084fc`): Reels / Shorts / TikTok.
- **Long** (`#38bdf8`): Full YouTube videos.
- **Article** (`#2dd4bf`): Article pipeline.
- **Repo** (`#fb7185`): GitHub repo pipeline.

### Named Rules

**The Signal Rule.** Signal orange means _the operator can act here_ — nothing else. It is forbidden in status badges, decorative fills, illustrations, and inactive states. Pending-yellow, its nearest hue, is forbidden on interactive controls. The two never trade places.

**The Two-Dialect Badge Rule.** Statuses are _filled_ (tint background + hue text); content types are _outlined_ (transparent + hairline + hue text). Hues may repeat across the two dialects because the fill style disambiguates at a glance — and every badge always carries its text label (color is never the only signal).

**The One Gradient Rule.** The Brain gradient is the product's entire decoration budget. One surface, hero scale, full stops. Everywhere else the console is chassis and signal.

## 3. Typography

**Display Font:** Inter (with system-ui fallback)
**Body Font:** Inter (same family — single-sans product discipline)
**Label/Mono Font:** JetBrains Mono (with ui-monospace fallback)

**Character:** A two-voice system. Inter speaks for humans — headings, body, buttons, navigation — at modest weights with gently negative tracking on display sizes. JetBrains Mono speaks for the machine — job IDs, timestamps, URLs, statuses, counts — so generated facts are typographically distinct from human language at a glance.

### Hierarchy

- **Display** (600, 24px, 1.2, -0.5px): Page titles. One per screen.
- **Headline** (600, 20px, 1.25, -0.25px): Section heads inside a page.
- **Title** (600, 16px, 1.4): Card and panel titles, job titles in detail view.
- **Body** (400, 14px, 1.5): Default UI text. Prose blocks (enrichment output) cap at 65–75ch; data surfaces may run denser.
- **Body Strong** (500, 14px): Nav items, emphasized inline text, table-row emphasis.
- **Label** (500, 12px): Form labels, filter group labels — sentence case, never tracked-uppercase.
- **Stat Value** (600, 28px, tabular-nums): Overview stat tiles. Always `tnum` so counts align.
- **Mono Meta** (400, 12px, JetBrains Mono): Timestamps, job IDs, URLs.
- **Mono Label** (500, 11px, +0.4px, JetBrains Mono, uppercase permitted): Badge text and table headers only — the machine's silkscreen voice, used narrowly.

### Named Rules

**The Mono Voice Rule.** If the machine produced it — an ID, a timestamp, a URL, a status word, a count — it renders in JetBrains Mono. If a human wrote it or reads it as language, it renders in Inter. No exceptions; this single rule does more "technical instrument" work than any decoration could.

**The 600 Ceiling.** No weight above 600 anywhere. Boldness comes from the dark chassis and rationed color, not from heavier type.

## 4. Elevation

The console is **flat by default** — depth is the plate ladder, not shadow. A surface communicates its level through background step (canvas → surface → raised) plus a 1px hairline; nothing at rest floats. Shadows are reserved exclusively for surfaces that genuinely sit _above_ the console: modals, dropdown menus, and toasts, which use a stacked pair of small offsets rather than a single heavy drop.

### Shadow Vocabulary

- **Overlay** (`box-shadow: 0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)`): Modals, dropdowns, toasts — the only shadow in the system.

### Named Rules

**The Plate Rule.** Depth is stacked plates and hairlines. If a card at rest has a shadow, it's wrong. If a modal doesn't, it's wrong. There is no third case.

## 5. Components

### Buttons

- **Shape:** Compact console radius (6px), 32px tall, 13px/500 Inter labels.
- **Signal (primary):** Signal orange fill (`#f6921e`) with near-black text (`#16100a`) — the highest-voltage element on any screen, so at most one or two per view. Hover brightens to `#ffa83d`; pressed deepens to `#b96a06`.
- **Ghost (secondary):** Transparent with 1px hairline border, ink text; hover raises the plate (`#1c1f25`). The workhorse for everything that isn't the primary action.
- **Hover / Focus:** All interactive elements share one focus treatment — a 2px signal-orange ring (`outline: 2px solid #f6921e; outline-offset: 2px`). Transitions 150ms ease-out.
- **Disabled:** Surface fill, muted text, no hairline glow — never a dimmed signal orange.

### Chips (filters)

- **Style:** 28px tall, 6px radius, surface fill with body text at rest.
- **State:** Active chip flips to signal orange fill + near-black text — selection is an act, so it earns the signal. Hover on inactive chips raises the plate.

### Badges

- **Status (filled):** Tint background + hue text + mono-label type (11px JetBrains Mono). E.g. done = `#4ade80` on `#122b1c`.
- **Content type (outlined):** Transparent + 1px hairline + hue text, same type. The two dialects never mix.
- **Rule:** Every badge carries its text label. Color is reinforcement, never the sole channel.

### Cards / Containers

- **Corner Style:** 8px radius.
- **Background:** Surface (`#14161a`) on canvas floor.
- **Shadow Strategy:** None at rest (The Plate Rule); hover raises background to `#1c1f25`.
- **Border:** 1px hairline (`#262a31`) on every plate.
- **Internal Padding:** 16px default; job rows 12px × 16px.

### Inputs / Fields

- **Style:** Inset to canvas (`#0b0c0f`) — one step _below_ the surface plates, so fields read as slots in the console. 1px hairline, 6px radius, 36px tall.
- **Focus:** Border shifts to signal orange; no glow, no shadow.
- **Placeholder:** Muted (`#8a919e`) — passes 4.5:1, never lighter.
- **Error:** Border and message in status-error (`#f87171`).

### Navigation

- **Style:** 208px sidebar on the surface plate with a 1px hairline edge; wordmark top, sign-out pinned bottom.
- **Items:** 14px/500 Inter, body color at rest, 6px radius, 8px × 12px padding.
- **Hover:** Plate raise (`#1c1f25`), ink text.
- **Active:** Raised plate + **signal orange text** — the one place signal appears as text color, marking "you are here" as an actionable state.
- **Mobile:** Sidebar collapses to a top bar with a disclosure menu; nav items keep identical styling.

### Stat Tiles (signature component)

The Overview row that answers "state at a glance." Surface plate, 8px radius, 12px × 16px padding: an 11px mono-label caption (muted) over a 28px/600 tabular-nums value (ink). Status-filtered tiles may tint their value with the matching status hue. Never the hero-metric template — no trend arrows, no sparkline decoration, no gradient accents; the number and its label are the entire design.

### Brain Surface (signature moment)

The `/brain` page carries the product's single decorative gesture: the violet→cyan gradient (`#7c3aed` → `#22d3ee`) as an atmospheric backdrop behind the semantic-search hero area, full stops, never cropped to a swatch. All controls on top of it follow the standard console vocabulary. Honors `prefers-reduced-motion`: if the gradient animates, it freezes to a static wash.

## 6. Do's and Don'ts

### Do:

- **Do** reserve signal orange (`#f6921e`) for actionable elements: primary buttons, active selections, focus rings, active nav. One or two signal elements per screen, maximum.
- **Do** render every machine fact — job IDs, timestamps, URLs, statuses, counts — in JetBrains Mono (The Mono Voice Rule).
- **Do** keep the two badge dialects distinct: statuses filled with tints, content types outlined with hairlines, every badge labeled with text.
- **Do** build depth from the plate ladder (`#0b0c0f` → `#14161a` → `#1c1f25`) + 1px hairlines; reserve the one overlay shadow for modals, dropdowns, toasts.
- **Do** use `tabular-nums` on every count and stat so numbers align as they tick.
- **Do** hold meta text at `#8a919e` or lighter-on-dark — ≥4.5:1 always (WCAG AA per PRODUCT.md).
- **Do** give every interactive component its full state set: default, hover, focus (2px signal ring), active, disabled, loading — skeleton plates for loading, not spinners in content.
- **Do** provide a `prefers-reduced-motion: reduce` fallback for every animation; transitions run 150–250ms ease-out.

### Don't:

- **Don't** drift into the **cluttered enterprise admin** PRODUCT.md names: gray-on-gray noise, toolbars stuffed with controls, everything visible at once. Density must have hierarchy — chassis quiet, signal loud.
- **Don't** go **toy / consumer-cute**: no mascots, no rounded-everything (radius caps at 12px), no bouncy or elastic motion, no jokey copy.
- **Don't** use signal orange decoratively, on inactive states, or in status badges — and don't put pending-yellow on anything clickable (The Signal Rule).
- **Don't** use gradient text (`background-clip: text`) anywhere; the Brain gradient is a backdrop, never a text fill or icon (The One Gradient Rule).
- **Don't** ship the hero-metric template: no big-number-with-trend-arrow-and-gradient-accent stat cards. Stat tiles are label + number, nothing else.
- **Don't** use side-stripe borders (`border-left` > 1px as a colored accent) on cards, rows, or alerts — status is carried by badges, not stripes.
- **Don't** lay out identical icon+heading+text card grids; vary structure by content or don't use cards.
- **Don't** put a tracked-uppercase eyebrow above sections. Uppercase mono is permitted only inside badges and table headers — the machine's voice, not section scaffolding.
- **Don't** exceed weight 600, use display type in UI labels, or float resting cards on shadows.
- **Don't** reach for a modal as the first thought — exhaust inline and progressive disclosure first (the operator stays in flow).
- **Don't** reintroduce the dead `gray-750` hovers or `gray-500` meta text from the legacy shell; both are retired by this spec's tokens.
