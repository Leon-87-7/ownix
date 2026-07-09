'use client';

import { useEffect, useState } from 'react';

function dashboardScroller(): HTMLElement | null {
  return document.querySelector<HTMLElement>('[data-dashboard-scroll]');
}

// #188: floating button that scrolls the dashboard content region back to top.
// The app header sits above this scroll container, so the scrollbar starts below it.
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
      className={`group fixed bottom-6 right-6 z-30 flex h-11 w-11 items-center justify-center rounded-md bg-signal text-onsignal shadow-[0_6px_20px_-4px_rgba(217,154,69,0.5)] outline-none transition-[opacity,transform,box-shadow,background-color] duration-200 ease-out hover:-translate-y-0.5 hover:bg-signal-bright hover:shadow-[0_12px_30px_-6px_rgba(217,154,69,0.7)] active:translate-y-0 active:bg-signal-deep focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas motion-reduce:transition-none ${
        visible
          ? 'translate-y-0 scale-100 opacity-100'
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
