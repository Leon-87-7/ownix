'use client';

import { useEffect, useRef, useState } from 'react';
import { Bot, BotOff } from 'lucide-react';
import { PulsingBorder } from '@paper-design/shaders-react';
import { useRestrictedMode } from '@/lib/restricted/context';

// Dev/mock builds only (inlined at build time, so this whole branch is dead
// code in prod): a floating, draggable switch between the two dev personas —
// mock user and unauthenticated visitor (Restricted mode).
const DEV_PERSONA_SWITCH =
  process.env.NODE_ENV !== 'production' &&
  process.env.NEXT_PUBLIC_API_MOCK === '1';

// Tuned on shaders.paper.design/pulsing-border; only `colors` varies by state.
const SHADER = {
  colorBack: '#000000',
  roundness: 1,
  thickness: 0,
  softness: 0.75,
  aspectRatio: 'square',
  intensity: 0.2,
  bloom: 0.45,
  spots: 3,
  spotSize: 0.4,
  pulse: 0.5,
  smoke: 1,
  smokeSize: 0,
  speed: 1,
  scale: 0.6,
} as const;

// Below this many pixels of pointer travel, treat the gesture as a click, not a drag.
const DRAG_THRESHOLD = 4;
// Keep the whole circle on-screen.
const SIZE = 48;

export default function DevPersonaSwitch() {
  const { restricted } = useRestrictedMode();
  // null = never dragged: sit in the default corner via classes.
  const [pos, setPos] = useState<{ x: number; y: number } | null>(
    null,
  );
  const drag = useRef<{ startX: number; startY: number; dx: number; dy: number } | null>(
    null,
  );
  const moved = useRef(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  if (!DEV_PERSONA_SWITCH) return null;

  const Icon = restricted ? BotOff : Bot;
  const label = restricted
    ? 'dev: visitor active — switch to mock user'
    : 'dev: mock user active — switch to visitor';

  return (
    // Plain <a>: the route handler sets/clears the httpOnly preview
    // cookie, so the switch needs a full navigation, not a client one.
    <a
      href={restricted ? '/restricted?exit=1' : '/restricted'}
      aria-label={label}
      title={label}
      style={
        pos
          ? { left: pos.x, top: pos.y, right: 'auto', bottom: 'auto' }
          : undefined
      }
      onPointerDown={(e) => {
        const rect = e.currentTarget.getBoundingClientRect();
        drag.current = {
          startX: e.clientX,
          startY: e.clientY,
          dx: e.clientX - rect.left,
          dy: e.clientY - rect.top,
        };
        moved.current = false;
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        if (!drag.current) return;
        if (
          !moved.current &&
          Math.hypot(e.clientX - drag.current.startX, e.clientY - drag.current.startY) <
            DRAG_THRESHOLD
        ) {
          return;
        }
        moved.current = true;
        const maxX = window.innerWidth - SIZE;
        const maxY = window.innerHeight - SIZE;
        setPos({
          x: Math.min(Math.max(e.clientX - drag.current.dx, 0), maxX),
          y: Math.min(Math.max(e.clientY - drag.current.dy, 0), maxY),
        });
      }}
      onPointerUp={() => {
        drag.current = null;
      }}
      onClick={(e) => {
        // A drag must not also trigger the persona switch.
        if (moved.current) e.preventDefault();
        moved.current = false;
      }}
      className="fixed bottom-10 right-10 z-50 flex size-12 cursor-grab touch-none select-none items-center justify-center overflow-hidden rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
    >
      <PulsingBorder
        {...SHADER}
        speed={reducedMotion ? 0 : SHADER.speed}
        colors={[restricted ? '#f87272' : '#4ade80']}
        className="absolute inset-0 size-full"
      />
      <Icon
        className="relative z-10 size-5 text-ink"
        aria-hidden="true"
      />
    </a>
  );
}
