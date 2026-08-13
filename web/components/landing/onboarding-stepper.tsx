'use client';

import { Fragment, useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { GhostButton } from '../ui/ghost-button';
import {
  Shapes,
  Fingerprint,
  BookOpenCheck,
} from 'lucide-react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

// The product's canonical triad (CONTEXT.md `Restricted mode`, AppHeader rhythm
// block): Collect / Own / Recall. These are the same three beats ADR-0038's
// mini-game taught by making the visitor perform them — share -> AI pass ->
// store/reuse — expressed as a scroll-driven stepper instead of a Rive state
// machine.
//
// Surfaces are Index / Feed / SEARCH, deliberately NOT Index / Feed / Brain.
// The Second Brain is the *shared* semantic link graph; step 3 describes
// searching your own private Index, so labelling it BRAIN would sell a private
// action as the collective layer. Search is where the recall actually happens.
//
// `body` is an array of lines, not a string with "\n" — JSX collapses newlines
// inside a string to a single space, so the break has to be structural. One
// sentence per line: the breaks are authored rhythm, not wrapping.
export const STEPS = [
  {
    id: 'collect',
    kicker: 'COLLECT',
    surface: 'INDEX',
    icon: Shapes,
    title: 'Share it from wherever you found it.',
    body: [
      'Instagram, YouTube, TikTok, GitHub, a PDF, a plain link.',
      'Hit share, pick the Ownix Telegram bot, keep scrolling.',
    ],
    meta: 'reels ◉ videos ◉ articles ◉ repos ◉ PDFs',
  },
  {
    id: 'own',
    kicker: 'OWN',
    surface: 'FEED',
    icon: Fingerprint,
    title: 'The AI reads it. You still know it.',
    body: [
      'Your prompt decides what gets pulled out,',
      'your tags decide what it means to you.',
      'Markdown in your own Google Drive, a minute later.',
    ],
    meta: 'transcript ◉ summary ◉ links ◉ tags',
  },
  {
    id: 'recall',
    kicker: 'RECALL',
    surface: 'SEARCH',
    icon: BookOpenCheck,
    title: 'Find it again, even from a glimpse.',
    body: [
      'Search by title, tag, or just scan the feed and spot the thumbnail.',
      'Copy one segment, or take the whole .md straight into your AI.',
    ],
    meta: 'copy a segment ◉ copy all ◉ grab the .md',
  },
] as const;

/**
 * Scroll-driven onboarding stepper for the landing page.
 *
 * Progressive enhancement, not a JS-only widget: the default render is all
 * three steps stacked in normal flow, fully readable with no JS, on mobile, and
 * under `prefers-reduced-motion: reduce`. Only when the matchMedia query
 * matches does GSAP overlap them and pin the section — and `gsap.matchMedia()`
 * reverts every one of those changes automatically when the query stops
 * matching (viewport resize, OS motion-preference flip), so the stacked layout
 * is always the state we fall back to.
 *
 * Pinning is desktop-only by deliberate choice: ADR-0038 established that
 * landing visitors mostly don't click (hence scroll rather than click-gating),
 * and pinned scroll-jacking on a phone sits directly above the invite CTA.
 */
export function OnboardingStepper() {
  const root = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const cta = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();

      // Breakpoint AND motion preference in one query — sm: (640px) matches the
      // Tailwind breakpoint the rest of the landing page uses.
      mm.add(
        '(min-width: 640px) and (prefers-reduced-motion: no-preference)',
        () => {
          const steps = gsap.utils.toArray<HTMLElement>(
            '[data-step]',
            stage.current,
          );
          const fills = gsap.utils.toArray<HTMLElement>(
            '[data-rail-fill]',
            root.current,
          );
          if (steps.length === 0) return;
          const focusables = steps.map((step) =>
            gsap.utils.toArray<HTMLElement>(
              'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
              step,
            ),
          );

          // Pin the whole <section>, not just this component, so the section
          // heading ("Three taps. Nothing new to learn.") stays on screen with
          // the steps instead of scrolling away and leaving them contextless.
          const section = root.current?.closest('section');
          if (!section) return;

          // Center the pinned content in the viewport. gsap.set writes inline
          // styles, which matchMedia reverts along with everything else when
          // the query stops matching — so this never leaks into the stacked
          // mobile/reduced-motion layout.
          gsap.set(section, {
            minHeight: '100svh',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
          });

          // Overlap the steps only while pinned. Plain `opacity` rather than
          // autoAlpha: autoAlpha sets visibility:hidden, which would pull the
          // un-reached steps out of the accessibility tree. Screen readers
          // should get all three in order regardless of scroll position.
          // Stack the steps into a single grid cell rather than absolutely
          // positioning them. The cell sizes itself to the tallest step, so the
          // stage needs no hand-tuned min-height — which would otherwise go
          // stale the moment any step's copy or the CTA changes height.
          gsap.set(stage.current, { display: 'grid' });
          gsap.set(steps, { gridArea: '1 / 1' });
          // pointerEvents travels with opacity: the grid-stack overlaps every
          // step in the same cell, and later-DOM steps paint on top of earlier
          // ones regardless of opacity, so an un-reached step's invisible hit
          // area would otherwise swallow clicks meant for the step underneath
          // it (e.g. the collect step's "more ways to add" link).
          gsap.set(steps.slice(1), {
            opacity: 0,
            y: 28,
            pointerEvents: 'none',
          });
          gsap.set(focusables.slice(1).flat(), {
            attr: { tabindex: -1 },
          });
          gsap.set(fills.slice(1), { scaleX: 0 });

          // autoAlpha (opacity + visibility) is deliberate HERE, and is exactly
          // what the steps must NOT use. A cta the visitor hasn't reached yet
          // should be genuinely absent — not announced by a screen reader, not
          // reachable by Tab, not clickable through a transparent layer.
          // `visibility: hidden` covers all three in one property and reverses
          // cleanly when the visitor scrubs back up. Step *content* is the
          // opposite case: it should stay readable regardless of scroll.
          if (cta.current) gsap.set(cta.current, { autoAlpha: 0 });

          const tl = gsap.timeline({
            scrollTrigger: {
              trigger: section,
              pin: true,
              start: 'top top',
              // ~700px of scroll per step reads as deliberate without feeling
              // like the page has stopped responding.
              end: `+=${STEPS.length * 700}`,
              scrub: 1,
              // snapTo:'labels' is what makes this a *stepper* — the playhead
              // settles on a step instead of resting mid-transition.
              snap: {
                snapTo: 'labels',
                duration: { min: 0.2, max: 0.6 },
                delay: 0.08,
                ease: 'power1.inOut',
              },
            },
          });

          tl.addLabel(STEPS[0].id);
          for (let i = 1; i < steps.length; i += 1) {
            // Sequential, NOT overlapping: the outgoing step is fully gone
            // before the incoming one starts. A cross-fade renders two
            // headlines on top of each other mid-scrub, which reads as a
            // rendering bug rather than a transition.
            tl.to(steps[i - 1], {
              opacity: 0,
              y: -28,
              duration: 0.35,
              ease: 'power2.in',
              pointerEvents: 'none',
            })
              .set(focusables[i - 1], { attr: { tabindex: -1 } }, '<')
              // The rail fill spans the whole hand-off so progress stays legible
              // during the gap when neither step is visible.
              .to(
                fills[i],
                { scaleX: 1, duration: 0.7, ease: 'none' },
                '<',
              )
              .to(steps[i], {
                opacity: 1,
                y: 0,
                duration: 0.35,
                ease: 'power2.out',
                pointerEvents: 'auto',
              })
              .set(focusables[i], { attr: { tabindex: 0 } }, '<')
              .addLabel(STEPS[i].id);
          }

          // Rides in with the final step's fade-in ('<' = start of the previous
          // tween), so the exit appears exactly when the story finishes rather
          // than costing the visitor extra scroll to discover.
          if (cta.current) {
            tl.to(
              cta.current,
              { autoAlpha: 1, duration: 0.35, ease: 'power2.out' },
              '<',
            );
          }
        },
      );
    },
    { scope: root },
  );

  return (
    <div ref={root}>
      {/* Progress rail. Signal marks current position, consistent with active
          nav (DESIGN.md: amber = act here / you are here), not decoration.

          Shown only when the timeline is actually driving it — same condition
          as the matchMedia query. Stacked visitors (mobile, reduced motion,
          no JS) see every step at once, so a three-segment progress indicator
          sitting permanently at 100% would be decoration claiming to be state,
          and it spends signal amber on something that isn't a position. */}
      <ol
        className="mb-8 hidden grid-cols-3 gap-2 sm:motion-safe:grid"
        aria-hidden="true"
      >
        {STEPS.map((step) => (
          <li key={step.id}>
            <div className="h-0.5 w-full overflow-hidden bg-line">
              <div
                data-rail-fill
                className="h-full w-full origin-left bg-signal"
              />
            </div>
            {/* 0.06em, not DESIGN.md's +0.4px. That token is specified for
                badge text, where caps sit inside a tinted pill; standing bare
                at 11px it works out to 0.036em, below the 5% floor all-caps
                needs before the letters start crowding. */}
            <span className="mt-2 block font-mono text-mono-label font-medium tracking-[0.06em] text-muted">
              {step.kicker}
            </span>
          </li>
        ))}
      </ol>

      {/* Stage. Flow-stacked with real spacing by default; GSAP flips it to a
          single-cell grid when pinning, which auto-sizes to the tallest step.
          No fixed height in either mode, so cards fit whatever the copy is. */}
      <div
        ref={stage}
        className="flex flex-col gap-6"
      >
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const isFirst = i === 0;
          const isLast = i === STEPS.length - 1;
          return (
            <article
              key={step.id}
              data-step
              className="rounded-lg border border-line bg-surface p-5 sm:p-6"
            >
              <div className="mb-3 flex items-center gap-3">
                <Icon
                  aria-hidden="true"
                  className="h-5 w-5 shrink-0 text-contrasignal"
                />
                <span className="font-mono text-mono-label font-medium tracking-[0.06em] text-contrasignal">
                  {step.surface}
                </span>
              </div>
              {/* balance, not pretty: `pretty` only fixes orphans, which is a
                  prose problem. A 2-3 line heading wants even line lengths.

                  Capped at 24px, not 28px. The section h2 above tops out at
                  28px, so the old clamp made this h3 exactly the same size as
                  its own parent heading at any viewport ≥933px — a hierarchy
                  inversion, and the two sit on screen together while pinned. */}
              <h3 className="text-balance mb-3 max-w-[24ch] text-[clamp(1.25rem,2.6vw,1.5rem)] font-semibold leading-tight tracking-[-0.25px] text-ink">
                {step.title}
              </h3>
              {/* <br /> rather than separate <p>s: these are one paragraph
                  broken for rhythm, not three paragraphs. Screen readers read
                  it as continuous prose either way, and it keeps a single
                  measure/leading for the block. */}
              {/* 16px, up from 15px. This is the landing page — brand register,
                  where the text IS the product — not the dashboard's dense
                  14px data surfaces. The hero paragraph is already `text-base`,
                  so 15px here made the same role two different sizes.

                  +0.01em is light-on-dark compensation: pale type on a dark
                  plate reads lighter and tighter than it measures. `leading-
                  relaxed` already covers the line-height half of that. */}
              <p className="text-pretty max-w-[58ch] text-base leading-relaxed tracking-[0.01em] text-body">
                {step.body.map((line, li) => (
                  <Fragment key={`${step.id}-${li}`}>
                    {li > 0 && <br />}
                    {line}
                  </Fragment>
                ))}
              </p>
              {/* DESIGN.md's mono-meta token (12px/400), not mono-label
                  (11px/500). This line is metadata, not a label — it was
                  borrowing the label's size with the meta's weight, which is
                  neither token and left three different roles sharing 11px. */}
              <p className="mt-4 font-mono text-xs text-muted">
                {step.meta}
              </p>

              {/* Wayfinding, not a second CTA: points at #capture, the
                  section that already covers share sheet / dashboard intake /
                  extension in full, rather than duplicating those three
                  channels inside this card. Plain text link deliberately
                  undersells itself next to "Get an invite" below - it's an
                  optional detour, not the ask. */}
              {isFirst && (
                <GhostButton
                  as="a"
                  accent="body"
                  borderLine="1"
                  href="#capture"
                  className="ownix-shimmer inline-flex mt-4 h-8 items-center justify-center rounded-md border border-line border-b-1 border-b-ink bg-transparent px-3.5 text-button font-medium leading-none text-ink transition-ui hover:bg-raised [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:px-5"
                >
                  More ways to collect
                </GhostButton>
              )}

              {/* The pinned section is the most engaged a visitor gets, and
                  without an exit it dead-ends into #showcase with the hero CTA
                  long since scrolled away. Ghost treatment, not signal — this
                  is the section's escape hatch, not a second primary CTA
                  competing with the hero.

                  Lives inside the final step's card, but carries its own ref so
                  the timeline can drive it with `autoAlpha` independently of the
                  step's `opacity`. That distinction is load-bearing: the step
                  fades on opacity alone so its text stays in the accessibility
                  tree at all times, whereas this link must be genuinely absent
                  until reached — `visibility: hidden` keeps it unfocusable and
                  unclickable behind the earlier steps. In the stacked fallback
                  the matchMedia branch never runs, so it simply renders at the
                  bottom of step three's card. */}
              {isLast && (
                <div
                  ref={cta}
                  className="mt-5"
                >
                  <GhostButton
                    as="a"
                    accent="signal"
                    borderLine="2"
                    href="#invite"
                    className="inline-flex h-8 items-center justify-center rounded-md border border-line border-b-2 border-b-contrasignal-deep bg-transparent px-3.5 text-button font-medium leading-none text-ink transition-ui hover:bg-raised [@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:px-5"
                  >
                    Get started
                  </GhostButton>
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
}
