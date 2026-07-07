---
target: the feed page
total_score: 27
p0_count: 0
p1_count: 2
timestamp: 2026-07-06T21-20-19Z
slug: web-app-dashboard-page-tsx
---
# Feed page critique — vig dashboard (`web/app/(dashboard)/page.tsx`)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Best-in-class: stats tiles, filled status badges, live count (aria-live), skeletons, in-flight polling, optimistic rows |
| 2 | Match System / Real World | 3 | Mostly plain; "stale in-flight", Latin motto, icon-only nav lean technical |
| 3 | User Control and Freedom | 3 | Clear-filters, retry, Esc-to-close drawer; destructive actions use native confirm() |
| 4 | Consistency and Standards | 3 | Two filter vocabularies stacked (segmented tabs + pill buttons), two active-orange styles, native confirm() breaks the custom-modal vocabulary |
| 5 | Error Prevention | 3 | confirm() before Clear failed / disconnect; forgiving search |
| 6 | Recognition Rather Than Recall | 3 | Icon-only sidebar taxes first-timers (tooltips + expand drawer mitigate) |
| 7 | Flexibility and Efficiency | 2 | No keyboard shortcuts, no bulk-select on jobs — a gap for a daily operator tool |
| 8 | Aesthetic and Minimalist Design | 2 | Recovery panel is always-on clutter: 3 disabled "(0)" buttons + a red error in the default healthy view |
| 9 | Error Recovery | 2 | "Failed to load recovery summary" is a vague, retry-less red line for a secondary tool |
| 10 | Help and Documentation | 2 | Good tooltips + teaching empty state; no real help/docs |
| **Total** | | **27/40** | **Acceptable (top of band, near Good)** |

## Anti-Patterns Verdict

**Does this look AI-generated? No.** This is the opposite of template slop. The
"Operator's Console" system has a genuine, committed point of view: a cool
near-black plate ladder, JetBrains Mono reserved for machine facts (timestamps,
counts, IDs), rationed signal orange that only marks actionable elements, and
filled+labeled semantic status badges. A category-fluent user (Linear/Vercel
lineage) would trust it, not pause at every component. It passes both the
first- and second-order category-reflex checks.

**Deterministic scan (detect.mjs):** 2 findings, both `border-accent-on-rounded`
(warning) — the `border-b-2` accent underline on the header Submit URL button
(`app-header.tsx:51`) and the mobile Submit trigger (`page.tsx:321`). These are
**false positives in intent**: a bottom-only 2px affordance underline is not the
banned thick side-stripe accent; it deliberately marks the button's color
(contrasignal/signal) without a full fill. Accepted deviation, not a defect.

**Visual overlays:** No script overlay was injected into the page (the CLI
detector already satisfied the deterministic-scan requirement, and I relied on
direct screenshots for browser evidence rather than the injection pipeline).
Browser evidence = live screenshots at 1440px (feed list + preview grid) and the
live "Failed to load recovery summary" error.

## Overall Impression

Strong, opinionated, product-grade. The chassis and state-coverage are the best
parts and they're genuinely good — this reads as a real product, not an internal
panel. The single biggest opportunity: **the control zone between the stats and
the job list is doing too much.** A permanently-visible recovery panel (3 disabled
zero-count buttons + a red error) pollutes the calm the rest of the design earns,
and it's the one place the "state at a glance / earn every element" principles
slip.

## What's Working

1. **State at a glance is real, not aspirational.** The 5-tile stats row
   (tabular-nums, status hues), the filled+labeled status badges, and the live
   mono job count deliver PRODUCT.md's first principle. Status is genuinely the
   loudest layer.
2. **State coverage is complete.** Skeletons (not spinners), a teaching empty
   state ("Send a video… to the Telegram bot"), an error banner with Retry,
   optimistic rows on submit, and in-flight polling. This breadth is rare and
   is exactly what the product register demands.
3. **The two-voice type system lands.** Inter for human language, JetBrains Mono
   for every machine fact. It does more "technical instrument" work than any
   decoration could, and it's applied consistently (timestamps, counts, @handles).

## Priority Issues

### [P1] The recovery panel is always-on clutter in the healthy default view
**Why it matters:** In the normal state (0 stale, 0 pending, 0 failed) the filter
bar still shows "0 stale in-flight" plus three disabled buttons — "Retry pending
(0) / Retry failed (0) / Clear failed (0)". That is precisely the *cluttered
enterprise admin* anti-reference (everything visible at once, no hierarchy) and
it violates "earn every element." A maintenance affordance should appear only when
there's something to recover.
**Fix:** Collapse the recovery controls entirely when `stale + pending + failed
=== 0`. Surface them (or a single "N need attention" chip that expands) only when
counts are non-zero. This also frees the filter row to breathe.
**Suggested command:** `/impeccable distill`

### [P1] "Failed to load recovery summary" reads as a false alarm
**Why it matters:** A red error line sits under the status filters whenever the
recovery summary endpoint fails — even though nothing is wrong with the user's
jobs. Red is the loudest status signal in this system; spending it on a secondary
maintenance tool's fetch failure makes the operator think their pipeline is
broken. It's also vague and offers no retry. ("Status never lies" / error-recovery.)
**Fix:** Demote a recovery-summary fetch failure to a quiet, non-red inline note
(muted text + a small retry), or fold it into the collapsed recovery affordance so
it never competes with real job status. Give it a cause + retry, not a bare
"Failed to load…".
**Suggested command:** `/impeccable clarify`

### [P2] Preview-grid cards are mostly empty box when thumbnails are missing
**Why it matters:** Short/Reels frequently have no thumbnail. In that case each
card is ~65% an empty gray panel with a small platform glyph + an identical
uppercase "SHORT" — repeated down the grid. That's a lot of dead space and reads
as the *identical card grid* tell, and the layout is clearly designed for the
happy path where images exist (Riley/stress-tester flag).
**Fix:** When there's no `thumbnail_url`, drop the tall aspect box for a denser
placeholder — shorter ratio, or use the title/first-frame-less layout so text
carries the card instead of a big empty rectangle. Make the no-image state a
first-class layout, not a fallback inside the image slot.
**Suggested command:** `/impeccable layout`

### [P2] Two filter vocabularies stack, both using active-orange
**Why it matters:** Row 1 is a segmented control (count badges + sliding orange
thumb); row 2 is a row of pill buttons (All/Done/Pending/Processing/Error) with a
solid-orange active pill. They're both "filters" but read as different control
families, and two orange-active controls are on screen at once (active content tab
+ active status "All"), pushing past the "one or two signal elements" rule and
blurring which selection is primary. (Consistency and Standards.)
**Fix:** Unify the two filter rows into one vocabulary, or visually subordinate the
status row (e.g. status as a quieter secondary control, not a second orange-fill
set). Reserve the orange fill for a single active selection per region.
**Suggested command:** `/impeccable layout`

### [P2] No power-user accelerators for a tool used many times a day
**Why it matters:** PRODUCT.md's primary user is an operator returning many times
daily. There are no keyboard shortcuts (e.g. `/` to focus search, `n` to submit),
and no bulk actions on jobs (multi-select → retry/cancel). Alex the power user
hits a one-item-at-a-time ceiling. (Flexibility and Efficiency.)
**Fix:** Add `/` to focus search and a shortcut to open Submit URL at minimum;
consider row multi-select for batch retry/clear as the pipeline grows into
web-driven operation.
**Suggested command:** `/impeccable shape`

## Persona Red Flags

**Alex (Power User):** No keyboard shortcuts anywhere — can't focus search, open
Submit, or filter from the keyboard. No bulk-select on the 223-row list; recovery
is the only batch action and it's buried in the filter bar. Returns daily and
still clicks through everything.

**Sam (Accessibility-Dependent):** Mostly strong — status badges pair hue with a
text label (never color-only), focus rings are present, the drawer follows the APG
dialog pattern (focus trap, Esc, restore). Watch items: the mobile stat strip's
T/D/P/E letters are decorative (screen-reader summary exists — good), and `muted`
meta text must stay ≥4.5:1 (DESIGN.md claims it does; verify the mono timestamps
on `surface`).

**The Operator (project persona):** Glances in to confirm system state — served
well by the stats row. But the recovery panel's red error + zero-count buttons
inject false "something's wrong" noise into that glance, working directly against
the reason they opened the page.

## Minor Observations

- The AppHeader Latin motto ("Servavi. Ditavi. Inveni." over cyan mono
  "Saved./Enriched./Found.") is a charming, on-brand signature ("delighted by the
  craft"). Keep it — but it's opaque to a first-timer and eats header width; watch
  it as the product goes multi-tenant.
- The scroll-to-top FAB is signal-orange — it *is* an action so it's within the
  rule, but it's a third orange element once you scroll. Fine, just noting the count.
- Icon-only sidebar (Rss=Feed, Brain, LayoutGrid=Spaces, MessageSquareText=Prompts,
  SlidersHorizontal=Controls) isn't self-evident; tooltips + an expand drawer with
  labels mitigate it, so this is P3, not a blocker.
- Native `confirm()` for "Clear failed" and Google disconnect breaks the otherwise
  custom modal/dialog vocabulary — minor consistency seam.

## Questions to Consider

- What if the recovery tools were invisible until something actually needed
  recovering — would the default view feel calmer and more "at a glance"?
- Is the status-filter row earning its second orange, or could the segmented tabs
  carry both content-type *and* status in one vocabulary?
- What would the confident version of the no-thumbnail card look like if you
  designed *that* state first instead of treating it as a fallback?
