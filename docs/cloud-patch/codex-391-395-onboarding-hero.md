# Codex prompt — implement issues #391–#395 (Ownix mobile onboarding hero)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0037-mobile-onboarding-storyboard-rive-nextjs.md` — the accepted
   decision: Rive scenes composed by React, what React owns vs what Rive owns,
   section order, end-card + auto-scroll rules.
2. `docs/plans/2026-07-17-ownix-mobile-onboarding-hero.md` — the full
   implementation plan. Its **Codebase Grounding** section and the resolved
   Open Questions 6–7 are authoritative where they differ from older wording
   elsewhere in the file.
3. `DESIGN.md` and `PRODUCT.md` (repo root) — visual system and brand bar.
4. `web/app/page.tsx` — the landing page you are changing.
5. GitHub issues #391–#395 (`gh issue view <n> --repo Leon-87-7/vig`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per slice.

## Key decisions already made (do not relitigate)

- The storyboard **replaces the demo video in place**: the current demo section
  (directly after `#hero`) keeps its "Three taps. Nothing new to learn."
  heading and the index-badges row; its `<section>` gains `id="onboarding"`,
  and the video slot becomes the phone-frame storyboard. The recording
  (`/demo-capture.mp4`) moves to a new minimal `#demo` proof section later in
  the page, before `#invite`.
- Anchor convention is mixed: `#hero` / `#invite` / `#top` are element ids;
  `#demo` / `#showcase` are ids on `<h2>` headings. Put `id="onboarding"` on
  the section element; keep the heading-id convention for the relocated
  `#demo`.
- `page.tsx` is a server component (exports `metadata`). All storyboard logic
  lives in a `'use client'` component:
  `web/components/landing/onboarding-storyboard.tsx` (kebab-case, colocated
  `.test.tsx`, no barrel files — same pattern as `count-up.tsx` /
  `demo-video.tsx`).
- Stack: Next 14.2 App Router, React 18, Tailwind 3, Vitest + RTL. Any Rive
  package you add must support React 18; dynamic-import the runtime.
- Reduced motion is mandatory: no autoplay and no auto-scroll under
  `prefers-reduced-motion: reduce` (JS gate via
  `matchMedia('(prefers-reduced-motion: reduce)')`; CSS uses the existing
  `motion-safe:` Tailwind convention).

## Work order

Implement in issue order — each slice builds on the previous, and each must
leave the app working (`npm run build`, `npm run test:run`, `npm run lint`
from `web/`).

### #391 — landing restructure

Restructure `web/app/page.tsx` per the decisions above. The onboarding phone
frame is a stable placeholder for now: `aspect-ratio: 9/16`, capped by
`max-height: calc(100svh - <section chrome>)`, no layout shift, containing the
plan's screen-reader/reduced-motion text summary. Final section order:

```
#top → #hero → #onboarding → #showcase → #features → #stats → #demo → #invite
```

Verify: anchors work, `Get an invite` → `#invite`, `Look inside` →
`/restricted`, no auto-scroll from `#hero`, no horizontal scroll on mobile
widths, existing tests pass.

### #392 — storyboard orchestration (placeholder scenes)

Build `OnboardingStoryboard` against fake scene players so every React-owned
behavior works before any Rive asset exists: visibility observer with ~60%
start threshold, the 7-scene sequence from the plan's `OnboardingScene[]`
metadata, `done`-event advancement with per-scene max-duration fallback,
crossfades inside the stable frame, 5s end-card hold, smooth-scroll to
`#showcase` only if the visitor has not interacted, cancellation on
scroll/click/keypress/focus, reduced-motion static fallback.

Colocated Vitest tests must cover at minimum: reduced motion disables
autoplay; interaction cancels auto-scroll; a withheld `done` advances via max
duration; the end-card hold triggers scroll only when allowed.

### #393 — Rive runtime + one test scene

Pick the Rive React package against current docs (React 18 / Next 14.2
compatible; likely `@rive-app/react-canvas` or `@rive-app/react-webgl2`),
dynamic-import it, and wire **one** real `.riv` through the scene-player
contract (`onLoad` / `onDone` from the state machine, resize without
distortion, no layout shift). Assets live under `web/public/rive/`. Preload:
first two scenes eagerly when `#onboarding` nears the viewport, the rest in
the background. Hero rendering must not block on Rive.

### #394 — seven production Rive scenes (HITL — scaffold only)

The `.riv` authoring is art-directed work in the Rive editor and is **not
yours to do**. Your part: make sure the scene metadata, player contract, and
asset paths for all seven scenes
(`onboarding-doomscroll` … `onboarding-end-card`) are wired so dropping in
each finished `.riv` requires no code change, and document the per-scene
contract (static first frame, state-machine name, `done` signal, max
duration, reduced-motion still) in a short README at `web/public/rive/`.

### #395 — copy, timing, verification (HITL — prepare only)

Final copy/timing decisions are human calls. Your part: put the plan's
recommended in-scene labels and prompt/reply fragments in as defaults, keep
all timings in the one `OnboardingScene[]` table so tuning is data-only, and
run the mechanical verification you can (build, tests, lint, reduced-motion
behavior, no text overlap, no horizontal scroll, `#demo` later in page).

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Do not touch anything outside `web/` and (if needed) `docs/`.
- No literal Telegram screenshots, no fake ChatGPT/Claude/Gemini interfaces,
  no visitor-controlled carousel, no dashboard-submit branch in the storyboard
  (plan's Non-Goals list is binding).
- Index Amber (`signal`) only for action moments; no gradient-orb decoration;
  the page must still read as Ownix: quiet, precise, premium, product-real.

## Deliverable

Uncommitted working-tree changes implementing #391–#393 fully and the
scaffolding halves of #394–#395, plus a short summary of what was done per
issue and anything that blocked you.
