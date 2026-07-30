'use client';

import { Fragment, useState } from 'react';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { STEPS } from './onboarding-stepper';

/**
 * Tappable onboarding stepper for the mobile breakpoint (`sm:hidden`).
 *
 * Copy comes from the desktop stepper's `STEPS` so the two breakpoints can
 * never drift; only interaction and layout differ. Desktop scrubs the steps
 * with a pinned GSAP timeline, this one advances on tap.
 *
 * Sticking, without ScrollTrigger. The section holds the viewport while the
 * visitor taps through, then releases — the same read as the desktop pin, but
 * built from `position: sticky` inside a taller runway rather than a second
 * ScrollTrigger (`.stepper-runway` / `.stepper-stick` in globals.css, which
 * also carry the viewport-height guard). Sticky costs no JS, can't desync from
 * the desktop timeline, and — unlike a pin with `scrub` — never takes the
 * scroll away from the finger: a visitor who doesn't want to tap just keeps
 * scrolling and the section lets go. That directness is what makes this safe to
 * do on a phone at all, and it supersedes the desktop-only note in
 * `onboarding-stepper.tsx` (which reasoned about *scroll-jacking* pins
 * specifically, ADR-0038).
 *
 * Selection is `bg-selected`, not `bg-signal`. DESIGN.md rations signal to mean
 * *act here*; on this breakpoint the action is `Next`, so an amber chip would
 * spend signal on *you are here* and leave two controls wearing the same
 * colour. The chip earns a dedicated plate one rung above `raised` plus an ink
 * underline; the progress rail drops to `ink/60` so it reads as progress rather
 * than competing with that underline. Signal stays on `Next` and on focus
 * rings, which are genuinely actions.
 */
export function MobileOnboardingStepper() {
  const [activeIndex, setActiveIndex] = useState(0);
  const step = STEPS[activeIndex];
  const Icon = step.icon;
  const isFirst = activeIndex === 0;
  const isLast = activeIndex === STEPS.length - 1;
  const progress = `${((activeIndex + 1) / STEPS.length) * 100}%`;

  return (
    <div className="sm:hidden">
      {/* Scroll runway + stuck child. Both rules live in globals.css, not here:
          they are guarded on viewport *height* as well as motion preference (a
          sticky element taller than the viewport would park the invite link
          off-screen on a landscape phone), and expressing that as stacked
          Tailwind arbitrary variants would be six unreadable class names for
          six lines of plain CSS. See the `.stepper-stick` block there. */}
      <div className="stepper-runway">
        <div className="stepper-stick">
          <div className="mb-4 rounded-lg border border-line bg-surface p-2">
            <ol
              className="grid grid-cols-3 gap-2"
              aria-label="Onboarding steps"
            >
              {STEPS.map((item, index) => {
                const isActive = index === activeIndex;
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => setActiveIndex(index)}
                      aria-current={isActive ? 'step' : undefined}
                      aria-label={`Go to ${item.kicker} step`}
                      className={`flex min-h-11 w-full flex-col items-start justify-between rounded-md border px-3 py-2 text-left transition-ui focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface ${
                        isActive
                          ? 'border-line-strong border-b-2 border-b-ink bg-selected text-ink'
                          : 'border-line bg-canvas text-muted hover:bg-raised hover:text-body'
                      }`}
                    >
                      <span className="font-mono text-mono-label font-medium tracking-[0.06em]">
                        {String(index + 1).padStart(2, '0')}
                      </span>
                      <span className="mt-1 font-mono text-mono-label font-medium tracking-[0.06em]">
                        {item.kicker}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </div>

          <div
            aria-hidden="true"
            className="mb-4 h-0.5 overflow-hidden bg-line"
          >
            <div
              className="h-full bg-ink/60 transition-[width] duration-200 ease-out-quart motion-reduce:transition-none"
              style={{ width: progress }}
            />
          </div>

          <article
            key={step.id}
            className="rounded-lg border border-line bg-surface p-5 motion-safe:animate-slide-up-in"
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
            <h3 className="text-balance mb-3 max-w-[24ch] text-[clamp(1.25rem,6vw,1.5rem)] font-semibold leading-tight tracking-[-0.25px] text-ink">
              {step.title}
            </h3>
            <p className="text-pretty max-w-[58ch] text-base leading-relaxed tracking-[0.01em] text-body">
              {step.body.map((line, li) => (
                <Fragment key={`${step.id}-${li}`}>
                  {li > 0 && <br />}
                  {line}
                </Fragment>
              ))}
            </p>
            <p className="mt-4 font-mono text-xs text-muted">
              {step.meta}
            </p>
          </article>

          <div className="mt-4 grid grid-cols-2 gap-3">
            <button
              type="button"
              onClick={() => setActiveIndex((index) => Math.max(0, index - 1))}
              disabled={isFirst}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-md border border-line bg-transparent px-4 text-button font-medium leading-none text-ink transition-ui hover:bg-raised active:scale-[0.98] disabled:cursor-not-allowed disabled:bg-surface disabled:text-muted motion-reduce:active:scale-100"
            >
              <ArrowLeft
                aria-hidden="true"
                className="h-4 w-4"
              />
              Back
            </button>
            {/* `group` so the press drives the arrow as well as the plate: the
                button sinks 2% and the arrow travels 4px in the direction it
                points. Transform-only, and neutralised under motion-reduce. */}
            <button
              type="button"
              onClick={() =>
                setActiveIndex((index) =>
                  index === STEPS.length - 1
                    ? 0
                    : Math.min(STEPS.length - 1, index + 1),
                )
              }
              className="group inline-flex h-11 items-center justify-center gap-2 rounded-md bg-signal px-4 text-button font-medium leading-none text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep active:scale-[0.98] motion-reduce:active:scale-100"
            >
              {isLast ? 'Review again' : 'Next'}
              <ArrowRight
                aria-hidden="true"
                className="h-4 w-4 transition-transform duration-200 ease-out-quart group-active:translate-x-1 motion-reduce:transition-none motion-reduce:group-active:translate-x-0"
              />
            </button>
          </div>

          <a
            href="#invite"
            className="mt-3 inline-flex h-11 w-full items-center justify-center rounded-md border border-line border-b-2 border-b-contrasignal-deep bg-transparent px-5 text-button font-medium leading-none text-ink transition-ui hover:bg-raised focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas"
          >
            Get an invite
          </a>
        </div>
      </div>
    </div>
  );
}
