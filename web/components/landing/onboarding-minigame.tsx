'use client';

import dynamic from 'next/dynamic';
import { useEffect, useRef, useState } from 'react';
import { LayoutDashboard, RotateCcw, Send, Sparkles } from 'lucide-react';
import OwnixLogo from '@/app/ownix-logo.svg';

const MinigameRive = dynamic(() => import('./onboarding-minigame-rive'), {
  ssr: false,
  loading: () => null,
});

// Pacing lives inside the Rive state machine (ADR-0038); this is the single
// dumb safety net for a state machine that never reports `end_screen`.
const SAFETY_TIMEOUT_MS = 25_000;

const END_BUTTONS = [
  {
    id: 'reusable',
    label: 'Reusable',
    // "rerun enrichment" leads the product on purpose — tracked as ownix#398.
    detail: 'Tag, rerun enrichment or copy your content.',
  },
  {
    id: 'searchable',
    label: 'Searchable',
    detail: 'Search every job, link and tag — or ask your Second Brain.',
  },
  {
    id: 'stored',
    label: 'Stored',
    detail: 'Everything also lands in your Google Drive as markdown.',
  },
];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(media.matches);
    const update = () => setReduced(media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return reduced;
}

function EndScreen() {
  const [open, setOpen] = useState<string | null>(null);
  const active = END_BUTTONS.find((button) => button.id === open);
  return (
    <div className="flex h-full min-h-[300px] flex-col items-center justify-center gap-4 p-6 text-center">
      <OwnixLogo className="h-12 w-12 text-signal" aria-hidden="true" />
      <p className="text-xl font-semibold text-ink">Ownix</p>
      <div className="flex flex-wrap justify-center gap-2">
        {END_BUTTONS.map((button) => (
          <button
            key={button.id}
            type="button"
            aria-expanded={open === button.id}
            onClick={() => setOpen(open === button.id ? null : button.id)}
            className={`inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium leading-none transition-ui ${
              open === button.id
                ? 'bg-raised text-ink'
                : 'bg-transparent text-body hover:bg-raised hover:text-ink'
            }`}
          >
            {button.label}
          </button>
        ))}
      </div>
      <p aria-live="polite" className="min-h-10 max-w-[38ch] text-sm leading-relaxed text-body">
        {active ? active.detail : 'Your internet. Own it. Reuse it.'}
      </p>
    </div>
  );
}

// ponytail: placeholder "zoo map" built from lucide glyphs; swap for the flat
// SVG exported from the game artwork once onboarding-minigame.riv is authored.
function ZooMap() {
  const steps = [
    { Icon: Send, label: 'Share' },
    { Icon: Sparkles, label: 'AI pass' },
    { Icon: LayoutDashboard, label: 'Reuse' },
  ];
  return (
    <div
      aria-hidden="true"
      className="flex items-center justify-center gap-3 border-t border-line p-4 font-mono text-[11px] tracking-[0.4px] text-muted"
    >
      {steps.map(({ Icon, label }, index) => (
        <span key={label} className="flex items-center gap-3">
          {index > 0 ? <span>→</span> : null}
          <span className="flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5" aria-hidden="true" />
            {label}
          </span>
        </span>
      ))}
    </div>
  );
}

export function OnboardingMinigame() {
  const reducedMotion = usePrefersReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const [started, setStarted] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [ended, setEnded] = useState(false);
  const [restartNonce, setRestartNonce] = useState(0);

  // Starts on scroll-into-view — which also covers arrival via the hero's
  // "See how it works" tab (arrival = intent, ADR-0038).
  useEffect(() => {
    if (reducedMotion || failed) return;
    const node = rootRef.current;
    if (!node) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry && entry.intersectionRatio >= 0.6) {
          setStarted(true);
          observer.disconnect();
        }
      },
      { threshold: [0, 0.6, 1] },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [reducedMotion, failed]);

  useEffect(() => {
    if (!started || failed || reducedMotion || ended) return;
    const timer = window.setTimeout(() => setEnded(true), SAFETY_TIMEOUT_MS);
    return () => window.clearTimeout(timer);
  }, [started, failed, reducedMotion, ended, restartNonce]);

  // Degrade to the destination: the payload without the theater (ADR-0038).
  if (reducedMotion || failed) {
    return (
      <div ref={rootRef} className="w-full overflow-hidden rounded-2xl border border-line bg-surface">
        <EndScreen />
        <ZooMap />
      </div>
    );
  }

  const restart = () => {
    setEnded(false);
    setRestartNonce((nonce) => nonce + 1);
  };

  return (
    <div
      ref={rootRef}
      aria-label="Ownix mini-game: share content to the Telegram bot, the AI pass runs, then store and reuse everything in the dashboard"
      className="relative aspect-square w-full overflow-hidden rounded-2xl border border-line bg-surface"
    >
      <MinigameRive
        active={started}
        restartNonce={restartNonce}
        onLoad={() => setLoaded(true)}
        onEnd={() => setEnded(true)}
        onError={() => setFailed(true)}
      />
      {!loaded ? (
        <div className="absolute inset-0 flex items-end justify-center bg-surface">
          <ZooMap />
        </div>
      ) : null}
      {ended ? (
        <div className="absolute inset-0 bg-surface/95">
          <EndScreen />
        </div>
      ) : null}
      {started && loaded ? (
        <button
          type="button"
          onClick={restart}
          aria-label="Replay the mini-game"
          className="absolute bottom-3 right-3 grid h-9 w-9 place-items-center rounded-lg border border-line bg-raised text-muted shadow-overlay transition-ui hover:text-ink"
        >
          <RotateCcw className="h-4 w-4" aria-hidden="true" />
        </button>
      ) : null}
    </div>
  );
}
