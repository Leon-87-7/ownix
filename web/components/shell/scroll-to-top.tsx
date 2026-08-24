'use client';

import { useEffect, useState } from 'react';
import { OwnixChevronDown } from '@/components/svg/ownix-chevron-down';

function dashboardScroller(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-dashboard-scroll]');
}

// #188: floating button that scrolls the dashboard content region back to top.
// The app header sits above this scroll container, so the scrollbar starts below it.
// ponytail: always rendered dimmed instead of detecting overlap with content beneath —
// per-frame elementFromPoint hit-testing during scroll caused the button to flicker
// on/off as it swept over cards. A constant dim is simpler and doesn't flash.
export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const scroller = dashboardScroller();
    if (!scroller) return;

    const onScroll = () => setVisible(scroller.scrollTop > 200);
    scroller.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => scroller.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <button
      type="button"
      onClick={() =>
        dashboardScroller()?.scrollTo({ top: 0, behavior: 'smooth' })
      }
      aria-label="Scroll to top"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      className={`group fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-md bg-signal text-onsignal shadow-[0_6px_20px_-4px_rgba(217,154,69,0.5)] outline-none transition-[opacity,transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:bg-signal-bright hover:shadow-[0_12px_30px_-6px_rgba(217,154,69,0.7)] hover:opacity-100 active:translate-y-0 active:bg-signal-deep focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas motion-reduce:transition-none ${
        visible
          ? 'translate-y-0 scale-100 opacity-60'
          : 'pointer-events-none translate-y-1 scale-90 opacity-0'
      }`}
    >
      <OwnixChevronDown
        aria-hidden="true"
        className="h-4 w-4 rotate-180 transition-transform duration-200 ease-out group-hover:-translate-y-0.5 motion-reduce:transition-none"
      />
    </button>
  );
}
