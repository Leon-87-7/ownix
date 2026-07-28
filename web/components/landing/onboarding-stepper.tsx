'use client';

import { useRef } from 'react';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { useGSAP } from '@gsap/react';
import { Share, Sparkles, Search } from 'lucide-react';

gsap.registerPlugin(ScrollTrigger, useGSAP);

// The product's canonical triad (CONTEXT.md `Restricted mode`, AppHeader rhythm
// block): Collect / Own / Recall mapped to Index / Feed / Brain. These are the
// same three beats ADR-0038's mini-game taught by making the visitor perform
// them — share -> AI pass -> store/reuse — expressed as a scroll-driven stepper
// instead of a Rive state machine.
const STEPS = [
  {
    id: 'collect',
    kicker: 'COLLECT',
    surface: 'INDEX',
    icon: Share,
    title: 'Share it from wherever you found it.',
    body: 'Instagram, YouTube, TikTok, GitHub, a PDF, a plain link. Hit share, pick Ownix. Three taps, then keep scrolling.',
    meta: 'short ◉ long ◉ article ◉ repo ◉ document',
  },
  {
    id: 'own',
    kicker: 'OWN',
    surface: 'FEED',
    icon: Sparkles,
    title: "Ownix reads it so you don't have to.",
    body: 'Transcript, summary, every link it mentioned, tags. Yours in about a minute — and it lands in your own Google Drive as markdown.',
    meta: 'transcript ◉ summary ◉ links ◉ tags',
  },
  {
    id: 'recall',
    kicker: 'RECALL',
    surface: 'BRAIN',
    icon: Search,
    title: 'Find it again — even from a glimpse.',
    body: 'Search by title, tag, thumbnail, or whatever you actually remember. Copy one segment, or take the whole .md straight into your AI.',
    meta: 'search ◉ copy ◉ export',
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
          gsap.set(steps, {
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
          });
          gsap.set(steps.slice(1), { opacity: 0, y: 28 });
          gsap.set(fills.slice(1), { scaleX: 0 });

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
            })
              // The rail fill spans the whole hand-off so progress stays legible
              // during the gap when neither step is visible.
              .to(fills[i], { scaleX: 1, duration: 0.7, ease: 'none' }, '<')
              .to(steps[i], {
                opacity: 1,
                y: 0,
                duration: 0.35,
                ease: 'power2.out',
              })
              .addLabel(STEPS[i].id);
          }
        },
      );
    },
    { scope: root },
  );

  return (
    <div ref={root}>
      {/* Progress rail. Signal marks current position, consistent with active
          nav (DESIGN.md: amber = act here / you are here), not decoration. */}
      <ol
        className="mb-8 grid grid-cols-3 gap-2"
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
            <span className="mt-2 block font-mono text-[11px] font-medium tracking-[0.4px] text-muted">
              {step.kicker}
            </span>
          </li>
        ))}
      </ol>

      {/* Stage. min-height reserves the tallest step so the pinned viewport
          doesn't resize as steps swap; in the stacked fallback it's harmless. */}
      <div
        ref={stage}
        className="relative sm:min-h-[300px]"
      >
        {STEPS.map((step) => {
          const Icon = step.icon;
          return (
            <article
              key={step.id}
              data-step
              className="mb-6 rounded-lg border border-line bg-surface p-6 last:mb-0 sm:mb-0"
            >
              <div className="mb-3 flex items-center gap-3">
                <Icon
                  aria-hidden="true"
                  className="h-5 w-5 shrink-0 text-contrasignal"
                />
                <span className="font-mono text-[11px] font-medium tracking-[0.4px] text-contrasignal">
                  {step.surface}
                </span>
              </div>
              <h3 className="text-pretty mb-3 max-w-[24ch] text-[clamp(20px,3vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink">
                {step.title}
              </h3>
              <p className="text-pretty max-w-[58ch] text-[15px] leading-relaxed text-body">
                {step.body}
              </p>
              <p className="mt-4 font-mono text-[11px] text-muted">
                {step.meta}
              </p>
            </article>
          );
        })}
      </div>
    </div>
  );
}
