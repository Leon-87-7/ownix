'use client';

/* @ds
name: DemoVideo
purpose: A landing-page product demo video that plays when scrolled into view, pauses out of view, and loops while visible — muted + playsInline to satisfy autoplay policy, controls always available.
when-not: Server-renders a plain non-autoplaying <video> — reduced-motion and no-JS visitors just get a normal player, never a broken autoplay attempt.
notes: The IntersectionObserver's first callback (which can fire "intersecting" before any real scroll, e.g. on a short viewport or in Lighthouse) is deliberately ignored — playback only starts on a later, genuine visibility change.
status: inferred
*/

import { useEffect, useRef } from 'react';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

/** Plays when a real scroll brings it into view, pauses when it scrolls out,
 * loops while visible. Muted + playsInline so the browser's autoplay policy
 * allows it; controls stay on so visitors can unmute or pause manually.
 * Server-renders a plain non-autoplaying video, so no-JS and reduced-motion
 * visitors just get a normal player.
 *
 * The observer's first callback fires immediately on `observe()` with
 * whatever the current visibility happens to be — on a short viewport (or a
 * lab tool like Lighthouse) that can already be "intersecting" before the
 * visitor has scrolled at all, autoplaying and eagerly downloading the whole
 * file on page load. That first callback is deliberately ignored; playback
 * only starts on a later, real intersection change. */
export function DemoVideo({
  src,
  poster,
  className,
}: {
  src: string;
  poster?: string;
  className?: string;
}) {
  const ref = useRef<HTMLVideoElement>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion) return;
    let sawFirstEntry = false;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!sawFirstEntry) {
          sawFirstEntry = true;
          return;
        }
        if (entry.intersectionRatio >= 0.5) el.play().catch(() => {});
        else el.pause();
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [reducedMotion]);

  return (
    <video
      ref={ref}
      controls
      loop
      muted
      playsInline
      preload="metadata"
      poster={poster}
      className={className}
    >
      <source src={src} type="video/mp4" />
    </video>
  );
}
