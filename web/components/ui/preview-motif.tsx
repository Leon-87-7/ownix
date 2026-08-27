import { useEffect, useId, useRef } from 'react';
import OwnixLogo from '@/app/ownix-logo.svg';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';

// Hero-only pointer reaction: letters near the cursor grow and nudge outward.
// Toned down from an initial 1.5x/22px pass (brand-lens flagged it as
// bouncy/elastic, off the "quiet, restrained" motif language in
// docs/brand/CONSTITUTION.md) to a subtler 1.15x/10 that reads as "noticing
// the visitor" rather than performing for them.
const HERO_MAX_SCALE = 1.15;
const HERO_MAX_PUSH = 10; // SVG user-units (176x176 viewBox), not CSS px
const HERO_INFLUENCE_FRACTION = 0.6; // of the motif's own rendered width
const HERO_EASE = 0.15;

export default function PreviewMotif({
  label,
  ariaLabel,
  className,
  size = 'default',
  treatment = 'default',
}: {
  label: string;
  /** Screen-reader name when the ring text alone is too terse. */
  ariaLabel?: string;
  className: string;
  size?: 'default' | 'fill';
  treatment?: 'default' | 'hero';
}) {
  const ringId = useId();
  const gradientId = useId();
  const reducedMotion = useReducedMotion();
  const motifSize = size === 'fill' ? 'h-full w-full' : 'h-44 w-44';
  const logoSize =
    size === 'fill' ? 'h-[32%] w-[32%]' : 'h-14 w-14';
  const logoAnimation =
    treatment === 'hero'
      ? 'motion-safe:animate-[ownix-logo-cycle_35s_linear_infinite]'
      : 'motion-safe:animate-[ownix-logo-cycle_7s_linear_infinite]';
  const ringAnimation =
    treatment === 'hero'
      ? 'motion-safe:animate-[spin_35s_linear_infinite]'
      : 'motion-safe:animate-[spin_14s_linear_infinite]';

  const ringText = `◉ ${label} ◉ ${label}`;
  const letters = treatment === 'hero' ? ringText.split('') : [];

  const containerRef = useRef<HTMLDivElement>(null);
  const letterRefs = useRef<(SVGTextElement | null)[]>([]);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const pushRef = useRef(letters.map(() => ({ x: 0, y: 0 })));
  const scaleRef = useRef(letters.map(() => 1));

  useEffect(() => {
    if (treatment !== 'hero' || reducedMotion) return;

    let raf = 0;
    let alive = true;

    const tick = () => {
      if (!alive) return;

      const pointer = pointerRef.current;
      const containerRect = containerRef.current?.getBoundingClientRect();
      const influenceRadius = containerRect
        ? containerRect.width * HERO_INFLUENCE_FRACTION
        : 0;
      const cx = containerRect ? containerRect.left + containerRect.width / 2 : 0;
      const cy = containerRect ? containerRect.top + containerRect.height / 2 : 0;

      letterRefs.current.forEach((el, i) => {
        if (!el) return;

        let targetPushX = 0;
        let targetPushY = 0;
        let targetScale = 1;

        if (pointer && containerRect) {
          const rect = el.getBoundingClientRect();
          const lx = rect.left + rect.width / 2;
          const ly = rect.top + rect.height / 2;
          const dist = Math.hypot(lx - pointer.x, ly - pointer.y);

          if (dist < influenceRadius) {
            let influence = 1 - dist / influenceRadius;
            influence = influence * influence * (3 - 2 * influence); // smoothstep
            targetScale = 1 + (HERO_MAX_SCALE - 1) * influence;

            const rlen = Math.hypot(lx - cx, ly - cy) || 1;
            targetPushX = ((lx - cx) / rlen) * HERO_MAX_PUSH * influence;
            targetPushY = ((ly - cy) / rlen) * HERO_MAX_PUSH * influence;
          }
        }

        const push = pushRef.current[i];
        push.x += (targetPushX - push.x) * HERO_EASE;
        push.y += (targetPushY - push.y) * HERO_EASE;
        scaleRef.current[i] += (targetScale - scaleRef.current[i]) * HERO_EASE;

        el.style.transform = `translate(${push.x.toFixed(2)}px, ${push.y.toFixed(2)}px) scale(${scaleRef.current[i].toFixed(3)})`;
      });

      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => {
      alive = false;
      cancelAnimationFrame(raf);
    };
  }, [treatment, reducedMotion, letters.length]);

  return (
    <div
      ref={containerRef}
      role="status"
      aria-label={ariaLabel ?? label}
      className={`flex items-center justify-center ${className}`}
      onPointerMove={
        treatment === 'hero'
          ? (e) => {
              pointerRef.current = { x: e.clientX, y: e.clientY };
            }
          : undefined
      }
      onPointerLeave={
        treatment === 'hero' ? () => { pointerRef.current = null; } : undefined
      }
    >
      <div className={`relative max-h-full max-w-full ${motifSize}`}>
        <OwnixLogo
          aria-hidden="true"
          focusable="false"
          className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 ${logoAnimation} ${logoSize}`}
        />
        <svg
          viewBox="0 0 176 176"
          aria-hidden="true"
          className={`absolute inset-0 h-full w-full origin-center motion-reduce:animate-none ${ringAnimation}`}
        >
          <defs>
            <path
              id={ringId}
              d="M 88,88 m -66,0 a 66,66 0 1,1 132,0 a 66,66 0 1,1 -132,0"
            />
            <linearGradient
              id={gradientId}
              x1="22"
              y1="22"
              x2="154"
              y2="154"
              gradientUnits="userSpaceOnUse"
              gradientTransform="rotate(35 88 88)"
            >
              <stop offset="0" stopColor="#a57534" />
              <stop offset="0.32" stopColor="#efb566" />
              <stop offset="0.66" stopColor="#9ec9ff" />
              <stop offset="1" stopColor="#649ca1" />
            </linearGradient>
          </defs>
          {treatment === 'hero' ? (
            letters.map((ch, i) => {
              const angle = (i / letters.length) * 2 * Math.PI - Math.PI / 2;
              const x = 88 + 66 * Math.cos(angle);
              const y = 88 + 66 * Math.sin(angle);
              const rotDeg = (angle * 180) / Math.PI + 90;

              return (
                <g
                  key={i}
                  transform={`translate(${x} ${y}) rotate(${rotDeg})`}
                >
                  <text
                    ref={(el) => {
                      letterRefs.current[i] = el;
                    }}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fill={`url(#${gradientId})`}
                    className="font-mono text-micro font-medium tracking-[0.18em]"
                  >
                    {ch}
                  </text>
                </g>
              );
            })
          ) : (
            <text
              className="fill-muted font-mono text-micro font-medium tracking-[0.18em]"
            >
              <textPath
                href={`#${ringId}`}
                startOffset="0"
                textLength="408"
                lengthAdjust="spacing"
              >
                {ringText}
              </textPath>
            </text>
          )}
        </svg>
      </div>
    </div>
  );
}
