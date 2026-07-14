'use client';

import { useEffect, useRef } from 'react';

/** Plays the moment it scrolls into view, pauses when it scrolls out, loops
 * while visible. Muted + playsInline so the browser's autoplay policy allows
 * it; controls stay on so visitors can unmute or pause manually. Server-
 * renders a plain non-autoplaying video, so no-JS and reduced-motion
 * visitors just get a normal player. */
export function DemoVideo({
  src,
  className,
}: {
  src: string;
  className?: string;
}) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) void el.play();
        else el.pause();
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <video
      ref={ref}
      controls
      loop
      muted
      playsInline
      preload="metadata"
      className={className}
    >
      <source src={src} type="video/mp4" />
    </video>
  );
}
