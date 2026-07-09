---
name: Ownix
description: A quiet premium system for collecting the internet you care about — a private Index, an owned Feed, and an optional contribution layer to the public Brain.
colors:
  canvas: '#0d0e10'
  surface: '#16181c'
  surface-raised: '#202329'
  hairline: '#30343d'
  hairline-strong: '#343a44'
  ink: '#f4f1eb'
  body: '#c6c1b8'
  muted: '#948e84'
  signal: '#d99a45'
  signal-bright: '#efb566'
  signal-deep: '#a57534'
  on-signal: '#1b1309'
  contrasignal: '#94e6ee'
  contrasignal-bright: '#9ec9ff'
  contrasignal-deep: '#649ca1'
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
  google: '#4285F4' # Google-connected state only — brand hue, never a signal substitute
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

# Design System: Ownix

## 1. Overview

**Creative North Star: "The Personal Index"**

Ownix is a calm, durable place for the internet a person wants to keep. It is
not a command surface or a novelty archive; it is a premium product for saving
videos, links, articles, repos, documents, and ideas into a personal Index,
returning to them through an owned Feed, and choosing what contributes signal to
the public Brain.

The system should feel quiet, precise, and private. Dark premium surfaces carry
the product with very little decoration. Amber is restrained and meaningful: it
marks the moments where a person saves, selects, contributes, retries, or
continues. The Brain is the shared layer, so its violet-to-cyan gradient is the
only expressive visual moment in the system and belongs only where collective
knowledge is visible.

Ownix is invite-only while it is young, but the tone is conversational rather
than exclusive. The interface should feel like a product shaped with real users,
real workflows, and honest feedback.

**Key Characteristics:**

- Quiet near-black plate ladder (`#0d0e10` → `#16181c` → `#202329`) with 1px hairlines — depth is structural, not decorative.
- One warm action color: Index amber `#d99a45` appears only on actions, active selections, focus, and current navigation.
- Ownership state is explicit: private Index, owned Feed, optional contribution to the Brain.
- Status remains clear: filled tint badges in semantic hues, always paired with a text label.
- Two voices: Inter for human language and JetBrains Mono for machine facts such as IDs, timestamps, URLs, statuses, and counts.
- Flat by default; shadows exist only for overlays such as dialogs, menus, and toasts.
- One expressive moment: the violet-to-cyan Brain gradient, used at meaningful scale only on Brain surfaces.
- Density is welcome, but every element must help someone collect, understand, return to, or share what matters.

## 2. Colors: The Ownix Palette

A restrained dark product palette with one warm amber for action and a semantic
vocabulary for state. Warmth means a person can do something; hue means state or
content type.

### Primary

- **Index Amber** (`#d99a45`): The single action color. It fills the primary button, active filter chip, focus ring, and active nav text. If it glows amber, the user can act: add to Index, save, retry, select, navigate, invite, or contribute to the Brain. It never appears in status badges, decorative fills, inactive states, or disabled controls.
- **Index Amber Bright** (`#efb566`): Hover state of amber surfaces.
- **Index Amber Deep** (`#a57534`): Pressed state.
- **On Amber** (`#1b1309`): Near-black text on amber fills. Dark-on-amber is sharper than white-on-amber and keeps contrast high.

### Secondary

- **Brain Gradient** (`#7c3aed` → `#22d3ee`): The shared-knowledge layer. Use it at meaningful scale on Brain surfaces only. Never miniaturize it to an icon, use it on buttons, or apply it as text fill.
- **Contrasignal** (`#94e6ee`, `#9ec9ff`, `#649ca1`): A cool supporting accent for secondary informational emphasis. It must not compete with Index Amber for action.

### Neutral

- **Canvas** (`#0d0e10`): The page floor — near-black with a restrained premium cast.
- **Surface** (`#16181c`): The working layer — cards, rows, sidebars, panels, and tiles.
- **Surface Raised** (`#202329`): Hover plates, active nav plates, and one-step-raised surfaces.
- **Hairline** (`#30343d`): Default 1px border on plates and inputs.
- **Hairline Strong** (`#343a44`): Emphasized borders such as input hover and table header rules.
- **Ink** (`#f4f1eb`): Headings and primary content text.
- **Body** (`#c6c1b8`): Secondary text — descriptions, nav labels at rest, and supporting copy.
- **Muted** (`#948e84`): Meta text — timestamps, counts, captions, and placeholders. It must remain WCAG AA on dark surfaces.

### Semantic — Status (filled badges: tint background + hue text)

- **Done** (`#4ade80` on `#122b1c`): Item processed, indexed, or complete.
- **Pending** (`#eab308` on `#2b240e`): Waiting, queued, or not yet reviewed.
- **Processing** (`#60a5fa` on `#14233b`): Active work in progress.
- **Enriching** (`#a78bfa` on `#221a3d`): Analysis, summary, transcript, or enrichment phase.
- **Error** (`#f87171` on `#371717`): Failed; pair with an amber retry action when retry is available.
- **Cancelled** (`#9aa1ad` on `#23262c`): Stopped or inert.

### Semantic — Content Type (outlined badges: transparent background + hue text + hairline)

- **Short** (`#c084fc`): Reels / Shorts / TikTok.
- **Long** (`#38bdf8`): Full-length videos.
- **Article** (`#2dd4bf`): Article or document pipeline.
- **Repo** (`#fb7185`): Repository pipeline.

### Named Rules

**The Amber Rule.** Index Amber means action, selection, or contribution. It is
forbidden in status badges, decorative fills, inactive states, and disabled
controls. Pending yellow is a status color and must never stand in for action.

**The Ownership Rule.** Surfaces should make ownership legible. Users should be
able to tell whether an item is in their private Index, visible in their Feed,
or contributing signal to the Brain. Do not rely on color alone; use text labels
and clear affordances.

**The Two-Dialect Badge Rule.** Statuses are filled: tint background + hue text.
Content types are outlined: transparent background + hairline + hue text. Every
badge carries a text label.

**The One Gradient Rule.** The Brain gradient is the product's entire decoration
budget. Use it only where the shared Brain itself is the subject.

## 3. Typography

**Display Font:** Inter (with system-ui fallback)
**Body Font:** Inter
**Label/Mono Font:** JetBrains Mono (with ui-monospace fallback)

**Character:** A two-voice system. Inter speaks for people: headings, body,
buttons, navigation, and product copy. JetBrains Mono speaks for generated or
system facts: IDs, timestamps, URLs, statuses, counts, and compact metadata.

### Hierarchy

- **Display** (600, 24px, 1.2, -0.5px): Page titles. One per screen.
- **Headline** (600, 20px, 1.25, -0.25px): Section heads inside a page.
- **Title** (600, 16px, 1.4): Card and panel titles, item titles in detail view.
- **Body** (400, 14px, 1.5): Default UI text. Long prose caps at 65–75ch; data surfaces may run denser.
- **Body Strong** (500, 14px): Nav items, emphasized inline text, table-row emphasis.
- **Label** (500, 12px): Form labels and filter group labels — sentence case, never tracked-uppercase.
- **Stat Value** (600, 28px, tabular-nums): Summary tiles. Always `tnum` so counts align.
- **Mono Meta** (400, 12px, JetBrains Mono): Timestamps, IDs, URLs, counts, and compact generated facts.
- **Mono Label** (500, 11px, +0.4px, JetBrains Mono, uppercase permitted): Badge text and table headers only.

### Named Rules

**The Mono Fact Rule.** If a system generated it — an ID, timestamp, URL,
status, count, or filename — render it in JetBrains Mono. If a person reads it
as language, render it in Inter.

**The 600 Ceiling.** No weight above 600. Premium restraint comes from spacing,
contrast, and disciplined color, not heavy type.

## 4. Elevation

Ownix is flat by default. Depth comes from the plate ladder (canvas → surface →
raised) plus 1px hairlines, not decorative shadows. Shadows are reserved for
surfaces that genuinely sit above the product: dialogs, dropdown menus, and
toasts.

### Shadow Vocabulary

- **Overlay** (`box-shadow: 0px 2px 4px rgba(0,0,0,0.4), 0px 12px 24px -8px rgba(0,0,0,0.5)`): Dialogs, dropdowns, and toasts only.

### Named Rules

**The Plate Rule.** Depth is stacked plates and hairlines. Resting cards do not
float. Overlays do.

## 5. Components

### Buttons

- **Shape:** Compact product radius (6px), 32px tall, 13px/500 Inter labels.
- **Primary:** Index Amber fill (`#d99a45`) with near-black text (`#1b1309`). Use for the main action on a surface: add to Index, save, submit, retry, invite, or contribute.
- **Secondary / Ghost:** Transparent with 1px hairline border and ink text; hover raises the plate (`#202329`).
- **Hover / Focus:** All interactive elements share a 2px Index Amber focus ring (`outline: 2px solid #d99a45; outline-offset: 2px`). Transitions run 150ms ease-out.
- **Disabled:** Surface fill, muted text, no amber glow, and no dimmed amber.

### Chips (filters)

- **Style:** 28px tall, 6px radius, surface fill with body text at rest.
- **State:** Active chip flips to Index Amber fill + near-black text. Selection is an action, so it earns amber. Hover on inactive chips raises the plate.

### Badges

- **Status (filled):** Tint background + hue text + mono-label type.
- **Content type (outlined):** Transparent + 1px hairline + hue text.
- **Ownership / Brain contribution:** Use labeled badges such as `Private`, `Indexed`, or `Shared to Brain`. Prefer neutral or cool treatments unless the badge itself is an action.
- **Rule:** Every badge carries its text label. Color reinforces meaning; it is never the only channel.

### Cards / Containers

- **Corner Style:** 8px radius.
- **Background:** Surface (`#16181c`) on the canvas floor.
- **Shadow Strategy:** None at rest; hover raises background to `#202329`.
- **Border:** 1px hairline (`#30343d`) on every plate.
- **Internal Padding:** 16px default; compact item rows may use 12px × 16px.

### Inputs / Fields

- **Style:** Inset to canvas (`#0d0e10`) so fields read as durable slots in the product. 1px hairline, 6px radius, 36px tall.
- **Focus:** Border or outline shifts to Index Amber; no decorative glow or shadow.
- **Placeholder:** Muted (`#948e84`) and WCAG AA.
- **Error:** Border and message in status-error (`#f87171`).

### Navigation

- **Style:** Sidebar or rail on the surface plate with a 1px hairline edge; Ownix wordmark in the expanded state.
- **Items:** 14px/500 Inter, body color at rest, 6px radius, 8px × 12px padding.
- **Hover:** Plate raise (`#202329`), ink text.
- **Active:** Raised plate + Index Amber text. This marks current location as the active place to continue.
- **Mobile:** Collapse to a top bar or disclosure drawer. Keep styling identical across viewports.

### Summary Tiles

Summary tiles answer “what changed in my Index?” without becoming hero metrics.
Use a surface plate, 8px radius, 12px × 16px padding, an 11px mono-label caption
over a 28px/600 tabular-nums value. Status-filtered tiles may tint values with
semantic status hues. No trend-arrow template, no sparkline decoration, and no
gradient accents.

### Brain Surface

The Brain is the product's shared layer: a collective map shaped by what people
choose to contribute. Its violet-to-cyan gradient may appear at meaningful scale
on Brain surfaces only. Controls on top of it must still use the standard Ownix
vocabulary. If the gradient animates, it must freeze to a static wash under
`prefers-reduced-motion: reduce`.

## 6. Do's and Don'ts

### Do:

- **Do** reserve Index Amber (`#d99a45`) for actionable elements: primary buttons, active selections, focus rings, active nav, retry, invite, and contribution actions.
- **Do** make privacy and contribution state legible: private Index, Feed, Indexed, Shared to Brain.
- **Do** render generated facts — IDs, timestamps, URLs, statuses, counts, filenames — in JetBrains Mono.
- **Do** keep badge dialects distinct: statuses filled, content types outlined, ownership/contribution labeled.
- **Do** build depth from the plate ladder (`#0d0e10` → `#16181c` → `#202329`) + 1px hairlines.
- **Do** use `tabular-nums` on counts and stats.
- **Do** keep meta text at `#948e84` or lighter-on-dark so it remains WCAG AA.
- **Do** provide full states for interactive components: default, hover, focus, active, disabled, loading, and error.
- **Do** provide `prefers-reduced-motion: reduce` fallbacks for every animation.

### Don't:

- **Don't** make Ownix feel like a cluttered admin panel. Density needs hierarchy: quiet surfaces, clear ownership state, restrained amber.
- **Don't** make it toy-like: no mascots, oversized emoji, bouncy motion, jokey copy, or rounded-everything.
- **Don't** use Index Amber decoratively, on inactive states, in status badges, or on disabled controls.
- **Don't** put pending yellow on clickable controls.
- **Don't** use gradient text. The Brain gradient is a backdrop for Brain surfaces, never text fill or button treatment.
- **Don't** ship hero-metric stat cards. Summary tiles are label + number.
- **Don't** use side-stripe borders as colored accents. Use full borders, labeled badges, or background tints instead.
- **Don't** lay out identical icon + heading + text card grids unless the content truly needs repeated cards.
- **Don't** put tracked-uppercase eyebrows above sections. Uppercase mono is permitted only inside badges and table headers.
- **Don't** exceed font weight 600, use display type in UI labels, or float resting cards on shadows.
- **Don't** reach for a modal first. Prefer inline and progressive disclosure when it keeps the user in flow.
