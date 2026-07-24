'use client';

import { useEffect, useRef } from 'react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

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
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (reducedMotion) {
      // A live preference flip mid-animation lands here too — make sure it
      // doesn't leave an eased intermediate number stuck in the DOM.
      el.textContent = Math.round(value).toString();
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
  }, [value, delay, reducedMotion]);

  return <span ref={ref}>{value}</span>;
}
