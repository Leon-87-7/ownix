---
adr: "0043"
title: Expanding rail, Bespoke Stencil wordmark morph, and the footer brand sweep
status: accepted
date: 2026-07-29
---

## Context

The sidebar was described as "the logo goes from the mark to `Ownix` in a smooth
transition." The code does not support that reading. `components/shell/sidebar.tsx`
holds **two logos in two disconnected subtrees**: a desktop rail
(`hidden w-16 … sm:flex`) with its own `LogoMark`, and a `position: fixed`
drawer (`w-56`, `-translate-x-full → translate-x-0`) with a *second* `LogoMark`
plus `<span>Ownix</span>`, sliding over the rail behind a `bg-black/50` backdrop.
The rail mark never becomes the wordmark — it gets covered by a different one.

Three further constraints shaped the decision:

- **`Ownix` is HTML text in Inter**, not SVG. `MorphSVGPlugin` morphs
  `path` → `path`/`polyline`/`polygon` only (`convertToPath()` upgrades
  `circle`/`rect`/`ellipse`/`line`). HTML text is not a valid morph target, so a
  literal glyph morph requires outlined letterforms.
- **`app/ownix-logo.svg` is one `<path>` with 4 subpaths**, `fill-rule="evenodd"`.
  Its first subpath is an **open ring** — a C-shaped sweep enclosing no counter.
- **Below `sm` there is no rail at all.** Mobile reaches the same drawer through
  a pull-tab (`sm:hidden`), so "expanding rail" can only be a desktop structure.

Licensing, which historically blocked this: **no longer a factor.** Since GSAP
3.13 (post-Webflow acquisition) every plugin — MorphSVG, ScrollTrigger,
SplitText — ships free in the npm package, commercial use included, with no
license key or auth token.

## Decision

**1. Desktop becomes an expanding rail; mobile keeps the modal drawer.** One
component, two behaviors, because `open` means different things per breakpoint:

| | Desktop (≥sm) — expanding rail | Mobile (<sm) — modal drawer |
|---|---|---|
| Layout | in-flow, pushes content, 64→224px | `fixed`, overlays content |
| Backdrop / focus trap / scroll lock | none | retained (current APG behavior) |
| Escape closes | no | yes |
| Close on navigate | **no** | yes |

The existing `useEffect(() => setOpen(false), [pathname])` must stop firing on
desktop — correct for a modal, hostile for persistent nav.

**2. Rail state persists per browser session** (`sessionStorage`). Not
`localStorage`: a preference set weeks ago shouldn't silently govern today's
layout. `sessionStorage` is unreadable during SSR, so the initial render is
always collapsed and an effect restores it — see decision 5.

**3. The wordmark is Bespoke Stencil Medium Italic**, loaded via
`next/font/local` (Fontshare/ITF, *not* Google Fonts — `next/font/google` does
not apply), **subsetted to the five glyphs `O w n i x`** since the face is only
ever used for one word. Fontshare fonts are free for commercial use and
self-hostable; outlining the `O` is derivative artwork, not font redistribution.

**4. The morph is mark → `O` only.** A stencil `O` is an **open ring** — the
counter connects to the outside through the stencil breaks, so there is no
separate inner contour. Open ring → open ring is **1 subpath → 1 subpath**, the
case MorphSVG handles with perfect fidelity and no `shapeIndex` tuning. `wnix`
stays **real text**, so it remains selectable and keeps its accessible name
(the link already carries `aria-label="Ownix home"`).

**5. The morph plays only on user toggle.** Session restore and
`prefers-reduced-motion: reduce` both call `.progress(1)` — end state, zero
frames — via `gsap.matchMedia()`. This replaces `sidebar-mark-in` and
`sidebar-word-in` in `globals.css`; keeping both would double-animate the same
element.

**6. The footer mark gets a gradient sweep, not a color cycle.** Replacing
`ownix-logo-cycle` (7s `linear`, 8 stops) on the landing footer, `/login`, and
`/logout`. Implemented as a **CSS `mask-image`** — a masked animated
`linear-gradient`, precedent already in `app/page.tsx:262` — **not** an SVG
`<linearGradient>`: the logo is `fill="currentColor"` across five render sites,
and SVG gradient IDs are document-global (the landing page renders the mark
three times). Colors are the **hero shader's exact array**, exported as a shared
token both files import, so `hero-gradient.tsx` and the footer can't drift.

## Consequences

- **Two `DESIGN.md` exceptions are granted here**, and they are deliberate, not
  drift. (a) A third typeface alongside Inter and JetBrains Mono. Bespoke
  Stencil is industrial and precise — it reads as "The Operator's Console"
  rather than decoration, and Medium Italic is weight **500**, under the 600
  Ceiling. (b) The **One Gradient Rule** — the footer sweep is a second
  gradient. It is scoped to three pages, uses signal→contrasignal rather than
  the Brain's violet→cyan, and therefore does not dilute the Brain's equity.
  Without this record, a future reader will "fix" both back.
- **The two footers must be consolidated first.** `components/ui/footer.tsx`
  serves `/login` and `/logout` via `AuthShell`, but the landing page carries an
  **inline duplicate** (`app/page.tsx`) that has already drifted — different
  widths, an extra `#top` anchor, extra hover treatments, and a copy-pasted
  comment that no longer makes sense in its new home. Implementing the sweep
  before consolidating means writing it twice.
- **GSAP enters the bundle.** Its only load-bearing use here is the one-path
  `O`-ring morph; the rail expansion and the footer sweep are both plain CSS.
  See ADR-0044 for the use that actually justifies the dependency.

## Considered Options

### Kalam (handwriting) as the wordmark

Rejected. Chosen to collapse the target subpath count, but Kalam's Latin is
**disconnected** — `O` outline + `O` counter + `w` + `n` + `i` stem + `i` dot +
`x` = **7 subpaths**, exactly the mismatch it was picked to avoid. Its only
usable weight is 700, which breaks the 600 Ceiling.

### Kalam plus an underscore or brush swash to force a union

Rejected once Bespoke Stencil surfaced, but the reasoning was sound: a stroke
overlapping every baseline lets a Boolean Union merge the letters, leaving
3 subpaths (body, `O` counter, `i` dot). The blocker was that the wordmark sits
inside an `<a>`, where a horizontal rule reads as `text-decoration: underline`.

### A connected script (Pacifico, Dancing Script, Grand Hotel)

Rejected. Would union to ~2 subpaths, but every candidate reads warm-casual
against a system whose stated personality is "bold, precise, crafted," and all
would fork the wordmark from the Inter rendering used on the landing page.

### Keep the drawer and morph inside it

Rejected. Cheapest option — no sidebar refactor — but the morph would play on an
element that was off-screen a frame earlier, reading as part of the slide-in
rather than as the rail transforming.

### Full glyph morph of the whole word

Rejected. Requires outlining all of `Ownix`, forfeiting selectable text and font
fallback, and with 3 letters having no source contour the effect degrades into a
fade with extra steps.

### `GrainGradient` (the hero shader) in the footer

Rejected. `hero-gradient.tsx` already caps `maxPixelCount` because uncapped
canvases wedge machines on software WebGL. A WebGL canvas per 40px logo across
three pages is a bad trade — reuse the palette, not the shader.
