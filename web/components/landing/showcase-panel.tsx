import type { ReactNode } from 'react';
import Image from 'next/image';
import leonAvatar from '@/images/leon-avatar-for-landing.png';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';

/**
 * The two-card "before -> after" vignette pattern shared by every real
 * workflow demo on the landing page (transcript -> AGENTS.md, reel ->
 * checklist, ...). ShowcaseCard owns the chrome each card repeats
 * (role=group wrapper, corner badge, filename/status header bar);
 * `children` is the already-styled content pane (a `<pre>` or a plain
 * `<div>`), since that's the one part that genuinely differs per card.
 */
export function ShowcaseCard({
  ariaLabel,
  cornerBadge,
  filename,
  status,
  children,
}: {
  ariaLabel: string;
  cornerBadge?: ReactNode;
  filename?: string;
  status?: string;
  children: ReactNode;
}) {
  return (
    <div
      role="group"
      className="relative overflow-hidden rounded-lg border border-line bg-surface"
      aria-label={ariaLabel}
    >
      {cornerBadge}
      {filename && (
        <div className="flex items-center justify-between border-b border-line px-3 py-2">
          <span className="min-w-0 truncate font-mono text-mono-label tracking-[0.4px] text-muted">
            {filename}
          </span>
          {status && (
            <span className="rounded-sm bg-status-done-tint px-1.5 py-0.5 font-mono text-mono-label font-medium tracking-[0.4px] text-status-done">
              {status}
            </span>
          )}
        </div>
      )}
      {children}
    </div>
  );
}

export function ShowcasePanel({
  id,
  heading,
  subheading,
  vignette,
  leftCard,
  rightCard,
  closing,
}: {
  id: string;
  heading: string;
  subheading: string;
  vignette: ReactNode;
  leftCard: ReactNode;
  rightCard: ReactNode;
  closing: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-[960px] px-6">
      <h2
        id={id}
        className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
      >
        {heading}
      </h2>

      <div className="mb-8 max-w-[62ch] text-prose leading-relaxed">
        <h3 className="font-subtitle mb-2 text-title font-semibold font-subtitle text-ink">
          &emsp;{subheading}
        </h3>
        <p className="text-pretty mb-4">{vignette}</p>
        <p className="flex items-center gap-2 font-mono text-xs text-muted">
          <Image
            src={leonAvatar}
            alt=""
            sizes="40px"
            className="h-10 w-10 rounded-full object-cover"
          />
          A real workflow from Leon, building Ownix
        </p>
      </div>

      <div className="grid items-center gap-4 md:grid-cols-[1fr_auto_1fr]">
        {leftCard}
        <OwnixChevronRight
          aria-hidden="true"
          className="h-4 w-4 mx-auto rotate-90 text-muted md:rotate-0"
        />
        {rightCard}
      </div>

      <p className="text-pretty mt-6 max-w-[58ch] text-prose leading-relaxed">
        {closing}
      </p>
    </div>
  );
}
