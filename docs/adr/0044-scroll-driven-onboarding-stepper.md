---
adr: "0044"
title: Scroll-driven inline onboarding stepper on the landing page
status: accepted
date: 2026-07-29
supersedes: "0038"
---

## Context

ADR-0037 specified landing onboarding as seven passive autoplay Rive scenes;
ADR-0038 superseded it with a single interactive Rive state machine. **Neither
was ever built.** `web/public/rive/` contains only `README.md` — no `.riv`
file; there is no `rive` package in `package.json`; and `onboarding` /
`MiniGame` appear nowhere in `app/`, `components/`, or `lib/`. (`app/mini/page.tsx`
is the Telegram Mini App — `initData` verification and Google connect — and is
unrelated.) Two accepted ADRs, one superseding the other, describe a feature
with no code behind it.

Meanwhile the landing page already carries a working explainer: the "Three taps.
Nothing new to learn." section with `DemoVideo`, and the transcript → `AGENTS.md`
showcase below it. Those cover the same ground ADR-0038 set out to teach.

A stepper **modal** was the initial proposal. `DESIGN.md` names that move
directly: *"Don't reach for a modal first. Prefer inline and progressive
disclosure when it keeps the user in flow."* On a landing page, a modal also
fires before the visitor has decided they care.

## Decision

**Abandon the Rive mini-game concept entirely.** ADR-0037 and ADR-0038 are both
superseded; no `.riv` asset will be authored and no Rive runtime is added.

**The landing `#demo` section becomes an inline, scroll-driven stepper** —
`components/landing/onboarding-stepper.tsx`. `DemoVideo` moves down into
`#stats`, which becomes CountUp tiles + `DemoVideo` + the Drive card.

**Three steps, using the product's canonical triad** (already load-bearing in the
`AppHeader` rhythm block and the Restricted-mode banner): **Collect / Own /
Recall** — which is also ADR-0038's beat sequence (share → AI pass →
store/reuse), expressed as scroll rather than as a state machine.

The three **surface** labels are **Index / Feed / Search**, deliberately *not*
Index / Feed / Brain. The Second Brain is the **shared** semantic link graph;
step three describes searching your own private Index, so labelling it `BRAIN`
would sell a private action as the collective layer and dilute the term. Search
is also where the recall genuinely happens — fuse.js over the job list, plus
scanning job-card thumbnails.

**Advance is driven by scroll, not clicks.** ADR-0038's central finding survives
the change of medium: *most landing visitors never click*, so click-gating
strands them on step 1. GSAP `ScrollTrigger` with `pin: true`, `scrub: 1`, and
`snap: { snapTo: "labels" }` gives discrete steps — each timeline label *is* a
step — with no interaction required.

**Pinning is desktop-only, via one `gsap.matchMedia()` query:**
`(min-width: 640px) and (prefers-reduced-motion: no-preference)`. Breakpoint and
motion preference are the same decision here, and GSAP reverts every `gsap.set`
automatically when the query stops matching.

**The default render is the fallback**, preserving ADR-0038's "degrade to the
destination" principle: all three steps are server-rendered stacked in normal
flow, fully readable with no JS, on mobile, and under reduced motion. GSAP only
overlaps and pins them when the query matches. Steps animate on **`opacity`, not
`autoAlpha`** — `autoAlpha` sets `visibility: hidden`, which would pull
un-reached steps out of the accessibility tree; screen readers should get all
three in order regardless of scroll position.

**The whole `<section>` is pinned, not just the stepper**, so the section
heading stays on screen with the steps. Step transitions are **sequential, not
cross-faded** — the outgoing step fully leaves before the incoming one arrives,
because overlapping two headlines mid-scrub reads as a rendering bug. The
progress rail spans the hand-off so progress stays legible during the gap.

## Consequences

- **This is what justifies the GSAP dependency.** `ScrollTrigger` pinning and
  scrub have no CSS equivalent. By contrast the sidebar rail expansion and the
  footer sweep in ADR-0043 are both plain CSS, and the wordmark morph is a
  single path tween — GSAP earns its place here, not there.
- **Pinning hijacks scroll on desktop.** ~700px of scroll per step sits between
  the visitor and the `#invite` CTA. Mitigated by capping at three steps and by
  never pinning on mobile, where the pattern is most disliked and where the CTA
  is closest.
- **Two accepted ADRs are retired without ever shipping.** Recorded deliberately:
  the design work in 0037/0038 was real, and the reason it was dropped is that
  the premise changed, not that it failed.

## Considered Options

### Stepper as a modal

Rejected. Contradicts `DESIGN.md`'s explicit inline-first rule, and on a landing
page it interrupts visitors before they have any reason to engage.

### No pinning — reveal each step on enter

Rejected as the primary treatment. Safe and cheap, but it is barely
distinguishable from the `hero-rise` reveals already on the page, and it would
not replace what the mini-game was meant to do. It remains the fallback for
mobile and reduced motion.

### Pin and scrub everywhere, mobile included

Rejected. Pinned scroll-jacking on a phone, directly above the invite CTA.

### Auto-advancing timed stepper, no scroll link

Rejected. Closest to ADR-0038's "idle auto-advance," but it animates whether or
not anyone is watching, and a visitor arriving mid-cycle sees a half-told story.

### Keep the Rive mini-game and add a stepper elsewhere

Rejected. Would leave two unbuilt ADRs standing alongside a third plan for the
same surface.
