---
adr: "0038"
title: Onboarding mini-game as a single interactive Rive state machine
status: superseded by ADR-0044
date: 2026-07-20
supersedes: "0037"
superseded-by: "0044"
---

## Context

ADR-0037 shipped the landing onboarding as seven passive autoplay Rive scenes
composed by React (crossfades, per-scene `done` events, `maxDurationMs`
fallbacks, auto-scroll to `#showcase`). A design revision changed the premise:
onboarding is now an **interactive mini-game** that teaches the product's
business logic — share content → AI pass → store/reuse in the dashboard — by
making the visitor perform it.

That revision breaks 0037's composition model in three ways:

- Scenes are **click-gated** (funnel, package), so advancement is user input,
  not a completion event React can sequence.
- Scene 3 (the Telegram plane flying through the Ownix logo) is a *continuous
  transition across a scene boundary* — impossible to author across separate
  `.riv` files without a visible cut.
- Scenes share cast members (pipeline icons, the bot, the package) that must
  persist and transform rather than pop between files.

## Decision

Replace the storyboard with **one `.riv` file
(`web/public/rive/onboarding-minigame.riv`), one artboard, one state machine
(`MiniGame`)** that owns the entire game — cover, gated scenes, idle pacing,
payoff, end state. This deliberately reverses 0037's rejection of a
"monolithic Rive film": the premise changed. It is not a film React needs to
recompose beat-by-beat; it is an interactive state machine, and state machines
are exactly what Rive authors natively. Scene-level flexibility now lives in
the Rive editor, not in React composition.

The full behavioral contract (scene table, gates, icon cast, events) lives in
`web/public/rive/README.md`. Load-bearing decisions:

- **Interactive-first with idle auto-advance.** Gated scenes advance on a
  center-canvas click or after ~3.5 s idle. Non-clickers always get the full
  story; strict click-gating was rejected because most landing visitors never
  click.
- **Pacing lives in the state machine**, authored as timed transitions. React
  keeps exactly one safety timeout (~25 s without an `end_screen` event ⇒
  treat as ended) instead of the per-scene `maxDurationMs` table.
- **The end screen is HTML, not canvas.** The finale (three explained buttons:
  reusable / searchable / stored) is real UI: keyboard-reachable, design-token
  styled, copy editable in one diff. Rive fires `end_screen`; React overlays
  the buttons. A fully Rive-authored finale was rejected — canvas text is
  un-greppable, inaccessible, and every copy tweak is a re-export.
- **Generic AI motif.** No Gemini or vendor branding baked into the file; the
  enrichment engine is swappable (ADR-0006 territory) and the game teaches the
  flow, not the vendor.
- **Degrade to the destination.** Reduced-motion, load-error, and no-JS
  visitors get the end state directly as static HTML plus a flat "zoo map" of
  the journey — the same payload minus the theater. No animation-shaped
  skeletons.
- **No auto-scroll after the game.** 0037's end-card hold + scroll to
  `#showcase` is deleted; the visitor is holding an interactive object.
- Discovery is a **"See how it works" edge-tab anchor** on the hero's bottom
  edge (grab-tab aesthetic, plain `<a href="#onboarding">`), not a third hero
  button — signal orange stays rationed to "Get an invite".

## Consequences

- The React↔Rive contract shrinks to one input (`restart` trigger), one event
  (`end_screen`), and one safety timeout. Timing tweaks are Rive-editor work,
  not code changes.
- The seven-file contract, `onboarding-end-card.riv` (artwork folds into the
  new file as the cover), the FakeScene placeholders, and the interaction-
  cancelled auto-scroll machinery are all deleted.
- The end-screen claim "rerun enrichment" leads the product slightly:
  per-job freestyle re-run is tracked as ownix#398 and was kept deliberately
  (option B) rather than softening the copy.
- Until the `.riv` is authored, the load-error path renders the static
  fallback, so the landing page stays shippable throughout.

## Considered Options

### Port the per-scene multi-file contract (0037's model)

Rejected. Cuts the plane-through-logo transition, duplicates shared cast
across files, and needs a chatty React↔Rive bridge for every click gate.

### React-owned pacing (timers fire triggers into the state machine)

Rejected. Two sources of truth for rhythm; every timing tweak becomes a code
change instead of an animator-side change.

### Strict click-gating (pure mini-game)

Rejected. Most visitors never click; they would stay frozen on scene 1 and
learn nothing — defeating the section's purpose.

### Autoplay-only with decorative clicks

Rejected. Loses the point of the revision: the visitor performing the loop is
the lesson.
