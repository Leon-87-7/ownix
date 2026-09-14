# Product

## Register

product

## Users

The primary user today is the **operator** — the owner running vig as a personal
second-brain and pipeline console. They return to it many times a day to: check
which videos/articles are processing, inspect per-job enrichment results, search
the accumulated corpus, curate the semantic link graph (Brain), and steer the
system (Spaces, Prompts, Controls). Context is focused desk work, often glancing
in to confirm system state between other tasks.

The architecture is being built toward **multi-tenant SaaS**, so screens should
read as a real product others could sign up for — not a throwaway internal panel.
Single-operator efficiency wins today, but no shortcuts you'd be embarrassed to
ship to a paying user.

## Product Purpose

vig (Video Intelligence Gateway) ingests short and long videos (Instagram Reels,
YouTube Shorts, TikTok, YouTube) plus articles and repos via Telegram, enriches
them with Gemini vision/text, stores results in Google Drive + Sheets, and
accumulates a semantic **Second Brain** link graph.

The dashboard is the human window into that pipeline: see what's processing,
inspect the enriched result of any job, search the corpus, and tune the system.
Success = the operator can glance and know system state, and can move from "what
happened" to "the enriched knowledge" in seconds.

Today the pipeline is driven mainly through Telegram, with the dashboard as the
read/monitor-and-tune surface. In the **near future the operator should be able
to drive the pipeline directly from the web interface** — submitting URLs,
triggering and re-running jobs, and managing the full lifecycle without leaving
the dashboard. Design the relevant surfaces (Feed, job detail, Controls) so they
can grow from monitoring into full operation without a redesign.

## Brand Personality

**Bold, precise, crafted.** Confident and opinionated without being loud for its
own sake. The voice is direct and technical but not cold — it should feel like a
sharp instrument, not a toy and not a beige enterprise console. Emotionally: the
operator feels *in command* (and a little delighted by the craft); a future
customer feels this is a serious, well-made product.

## Anti-references

- **Cluttered enterprise admin** — gray-on-gray density, toolbars stuffed with
  controls, everything visible at once, no hierarchy. (The current monochrome
  `gray-950`/`gray-800` shell is most at risk of drifting here.)
- **Toy / consumer-cute** — mascots, rounded-everything, oversized emoji, bouncy
  elastic motion, jokey copy. Too informal for a tool you operate daily.
- Plus the universal slop bans: gradient text, the hero-metric template,
  identical icon+heading card grids, side-stripe borders, and a tracked
  uppercase eyebrow above every section. (The `PageHeader` icon's gradient
  stroke is a named exception — DESIGN.md's Header Icon Gradient Rule — not a
  slop pattern to flag.)

## Design Principles

1. **State at a glance.** The operator should read system health in one look.
   Status is the loudest signal on any screen — never decoration.
2. **Bold but legible.** Commit to a strong accent and confident typography, but
   expressiveness never costs readability or information density.
3. **One step from job to knowledge.** Every surface optimizes the path from
   "what happened" to "the enriched result" — minimize clicks and detours.
4. **Built like a product, used like a console.** Single-operator speed today,
   but every screen must hold up when it's multi-tenant. No internal-tool
   shortcuts that wouldn't survive a real signup.
5. **Earn every element.** Bold means deliberate, not busy. Reject the enterprise
   reflex to show everything; cut what doesn't carry its weight.

## Accessibility & Inclusion

- **WCAG 2.1 AA.** Body text ≥ 4.5:1 against its surface; large text ≥ 3:1.
  Known gap to fix: `gray-500` meta text (timestamps, labels) on dark surfaces
  likely fails — bump toward the ink end of the ramp.
- **Reduced motion is not optional.** Every animation needs a
  `@media (prefers-reduced-motion: reduce)` fallback (crossfade or instant).
- **Status never relies on color alone.** Pair every status/content-type badge
  with its text label (already the pattern in `job-card.tsx` — keep it).
- Keyboard-navigable navigation and controls with a visible focus state (the
  current indigo focus ring is a starting point).
