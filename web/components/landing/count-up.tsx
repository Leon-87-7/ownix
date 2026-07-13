'use client';

import { useEffect, useRef } from 'react';

/** Animates a stat from 0 to its value the first time it scrolls into view.
 * Server-renders the final value, so no-JS, reduced-motion, and headless
 * visitors always see the real number — the count-up only ever plays on top. */
export function CountUp({
  value,
  delay = 0,
}: {
  value: number;
  delay?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      return;
    }
    let raf = 0;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        io.disconnect();
        const duration = 900;
        let start: number | undefined;
        const step = (now: number) => {
          if (start === undefined) start = now + delay;
          const p = Math.min(
            Math.max((now - start) / duration, 0),
            1,
          );
          const eased = 1 - Math.pow(1 - p, 4);
          el.textContent = Math.round(eased * value).toString();
          if (p < 1) raf = requestAnimationFrame(step);
        };
        raf = requestAnimationFrame(step);
      },
      { threshold: 0.6 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      cancelAnimationFrame(raf);
    };
  }, [value, delay]);

  return <span ref={ref}>{value}</span>;
}
