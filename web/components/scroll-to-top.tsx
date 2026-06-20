"use client";

import { useEffect, useState } from "react";

// #188: floating button that scrolls the <main> container back to top.
// <main> is the scroll container (overflow-auto in the dashboard layout).
export function ScrollToTop() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const main = document.querySelector("main");
    if (!main) return;
    const onScroll = () => setVisible(main.scrollTop > 200);
    main.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => main.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <button
      type="button"
      onClick={() => document.querySelector<HTMLElement>("main")?.scrollTo({ top: 0, behavior: "smooth" })}
      aria-label="Scroll to top"
      aria-hidden={!visible}
      tabIndex={visible ? 0 : -1}
      className={`fixed bottom-6 right-6 z-30 flex h-9 w-9 items-center justify-center rounded-md border border-line bg-surface text-muted transition-[opacity,background-color] duration-150 hover:bg-raised hover:text-ink active:translate-y-px focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal motion-reduce:transition-none ${
        visible ? "opacity-100" : "pointer-events-none opacity-0"
      }`}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="h-4 w-4">
        <path d="M12 19V5M5 12l7-7 7 7" />
      </svg>
    </button>
  );
}
