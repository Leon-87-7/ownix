'use client';

import { useEffect, useRef, useState } from 'react';

function dashboardScroller(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-dashboard-scroll]');
}

const INTERACTIVE_SELECTOR =
  'button, a, summary, input, select, textarea, [role="button"], [tabindex]';

// #188: floating button that scrolls the dashboard content region back to top.
// The app header sits above this scroll container, so the scrollbar starts below it.
export function ScrollToTop() {
  const [visible, setVisible] = useState(false);
  const [dimmed, setDimmed] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const scroller = dashboardScroller();
    if (!scroller) return;

    // ponytail: only rechecks on scroll/resize, not on layout shifts from
    // other accordions opening above this button. Add a ResizeObserver on
    // the scroller's content if that turns out to matter.
    //
    // Samples the center + all 4 corners (native z-index-aware hit testing,
    // not a raw rectangle overlap): a naive rect intersection treats any
    // interactive element sharing screen space as "blocked", even ones that
    // already render above this button (e.g. the dev persona switch, z-50)
    // and don't need it to get out of the way at all.
    const checkOverlap = () => {
      const btn = buttonRef.current;
      if (!btn || typeof document.elementFromPoint !== 'function') return;
      const rect = btn.getBoundingClientRect();
      const inset = 4;
      const points: Array<[number, number]> = [
        [rect.left + rect.width / 2, rect.top + rect.height / 2],
        [rect.left + inset, rect.top + inset],
        [rect.right - inset, rect.top + inset],
        [rect.left + inset, rect.bottom - inset],
        [rect.right - inset, rect.bottom - inset],
      ];
      const isButton = (el: Element | null) =>
        el === btn || Boolean(el && btn.contains(el));

      let blocking = false;
      try {
        const coveredPoints = points.filter(([x, y]) =>
          isButton(document.elementFromPoint(x, y)),
        );
        if (coveredPoints.length > 0) {
          const prevPointerEvents = btn.style.pointerEvents;
          btn.style.pointerEvents = 'none';
          blocking = coveredPoints.some(([x, y]) =>
            Boolean(document.elementFromPoint(x, y)?.closest(INTERACTIVE_SELECTOR)),
          );
          btn.style.pointerEvents = prevPointerEvents;
        }
      } catch {
        // jsdom doesn't implement elementFromPoint
      }
      setDimmed(blocking);
    };

    const onScroll = () => {
      setVisible(scroller.scrollTop > 200);
      checkOverlap();
    };
    scroller.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', checkOverlap);
    onScroll();
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', checkOverlap);
    };
  }, []);

  return (
    <button
      ref={buttonRef}
      type="button"
      onClick={() =>
        dashboardScroller()?.scrollTo({ top: 0, behavior: 'smooth' })
      }
      aria-label="Scroll to top"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      className={`group fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-md bg-signal text-onsignal shadow-[0_6px_20px_-4px_rgba(217,154,69,0.5)] outline-none transition-[opacity,transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:bg-signal-bright hover:shadow-[0_12px_30px_-6px_rgba(217,154,69,0.7)] active:translate-y-0 active:bg-signal-deep focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas motion-reduce:transition-none ${
        visible
          ? `translate-y-0 scale-100 ${dimmed ? 'pointer-events-none opacity-60' : 'opacity-100'}`
          : 'pointer-events-none translate-y-1 scale-90 opacity-0'
      }`}
    >
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className="h-5 w-5 transition-transform duration-200 ease-out group-hover:-translate-y-0.5 motion-reduce:transition-none"
      >
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  );
}
