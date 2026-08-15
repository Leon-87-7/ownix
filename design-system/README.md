# Ownix Design System (gallery)

A single reference page that renders every design token — and, once its
rendering strategy is decided, every component — live from the app's real
source. Primary consumer: agents working on Ownix.

## The one rule

**The gallery references the source; it never copies it.** Token *values* are
never typed into this folder. They are read live from the app's compiled
Tailwind CSS via `getComputedStyle`, so a drifted value is visibly wrong and a
token change in the app shows up here on the next build. Verified: changing a
token in `web/tailwind.config.ts` and re-running the build changes the swatches,
with no edit to any file in `design-system/`.

## Build & open

```shell
npx tsx design-system/build.mjs      # regenerates _generated/ + index.html
```

Then open `design-system/index.html` — `file://` works, no server needed.

What the build does:

1. Reads token **names** from `web/tailwind.config.ts` (the app's real config,
   which mirrors `DESIGN.md` frontmatter). No values are read or copied.
2. Regenerates `index.html`, emitting each swatch/specimen with its literal
   token class (`bg-canvas`, `text-stat`, …).
3. Runs the real Tailwind CLI over that HTML + `web/app/globals.css` (via
   `tailwind.gallery.config.ts`, which inherits the app theme as a `preset`) to
   produce `_generated/app.css` — the exact CSS the app ships.
4. Writes `_generated/manifest.json` (build SHA, timestamp, token lists,
   component `@ds` blocks, source-file hashes for the staleness check).

## Status

- **Tokens — done, fully live.** Colors (36), type scale (11), font families,
  radii, the single overlay shadow. Each value is read live; nothing is hard-coded.
- **Components — pending an architecture decision.** See below. The Tokens work
  does not depend on it.

### Known limitation (tokens)

Font *family* specimens fall back to system fonts here, because Inter /
JetBrains / Montserrat / Merienda are injected by Next.js as CSS variables
(`--font-inter`, …) at app runtime and are not present in a standalone page.
The font *stack* (the token) is still correct; only the loaded face differs. If
we want true faces in the gallery, the build can `@font-face` them into
`_generated/`.

## The open decision: how to render real components

`DESIGN.md`'s handoff §0 forbids copying component markup into the gallery, and
§6 says "static HTML plus one extract script, no new framework." Ownix
components are React/TSX that lean on Radix, GSAP, and `next/*`, so there is a
real tension to resolve before building the components section. Options are
written up for decision; nothing is built until one is chosen. This file is
updated once it is.

## Phase 1 inventory & decisions

- `_inventory/` — the five read-only audits (tokens, components, responsive,
  drift, usage).
- `DECISIONS.md` — Phase 1 gate decisions.
- `DRIFT-BACKLOG.md` — drift to fix in separate PRs (not touched by this work).
