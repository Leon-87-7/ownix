'use client';

import Link from 'next/link';
import { useState } from 'react';
import { BriefcaseBusiness, ExternalLink, Trash2 } from 'lucide-react';
import { DateTime } from '@/components/ui/date-time';
import { StatusBadge } from '@/components/ui/badges';
import { NoPreviewRing } from '@/components/ui/no-preview-ring';
import type { DigestCandidate } from '@/lib/newsletter-digest';

function asUtcIso(raw: string): string {
  return /[Zz]|[+-]\d\d:?\d\d$/.test(raw) ? raw : `${raw.replace(' ', 'T')}Z`;
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

function Thumbnail({ candidate }: { candidate: DigestCandidate }) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(candidate.thumbnail_url) && !failed;

  return (
    <div className="relative aspect-video overflow-hidden rounded-md border border-line bg-canvas">
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element -- arbitrary OG image URL
        <img
          src={candidate.thumbnail_url ?? ''}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="relative flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
          <NoPreviewRing seed={candidate.id} label={hostname(candidate.url)} />
          <ExternalLink className="relative h-[22px] w-[22px] text-muted" aria-hidden="true" />
          <span className="relative font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
            {hostname(candidate.url)}
          </span>
        </div>
      )}
    </div>
  );
}

// Same shape as PreviewCard (components/feed/preview-card.tsx) — the Feed's
// thumbnail-forward grid card — not the dense JobCard list row: a full-card
// link overlay, a thumbnail block, a title + status row, and a footer line
// with timestamp left / actions right in a pointer-events-auto z-10 pocket
// so real buttons can sit on top of the overlay anchor.
export function NewsletterCandidateCard({
  candidate,
  onPromote,
  onDismiss,
  busy = false,
}: {
  candidate: DigestCandidate;
  onPromote?: (candidateId: string) => void;
  onDismiss?: (candidateId: string) => void;
  busy?: boolean;
}) {
  const promotedHref = candidate.job_id ? `/jobs/${candidate.job_id}` : undefined;
  const title = candidate.title || hostname(candidate.url);
  const actionDisabled = busy || candidate.status !== 'pending';

  return (
    <div className="group relative flex h-full flex-col rounded-lg border border-line bg-surface p-3 transition-ui hover:border-line-strong hover:bg-raised">
      <a
        href={candidate.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={title}
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset"
      />

      <div className="pointer-events-none">
        <Thumbnail candidate={candidate} />
      </div>

      <div className="pointer-events-none mt-3 flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex items-start gap-2">
          <p className="min-w-0 flex-1 truncate text-sm font-medium leading-5 text-ink">
            {title}
          </p>
          <span className="shrink-0">
            <StatusBadge label={candidate.status} />
          </span>
        </div>

        <div className="mt-auto flex items-center justify-between gap-3">
          <span className="truncate font-mono text-xs text-muted">
            Found <DateTime iso={asUtcIso(candidate.created_at)} />
          </span>
          <span className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-2">
            {promotedHref && (
              <Link
                href={promotedHref}
                className="h-8 rounded-md border border-line px-3.5 py-2 text-button font-medium text-ink transition-ui hover:bg-surface"
              >
                Open job
              </Link>
            )}
            {onDismiss && candidate.status === 'pending' && (
              <button
                type="button"
                onClick={() => onDismiss(candidate.id)}
                disabled={busy}
                aria-label={`Dismiss ${title}`}
                className="flex h-8 w-8 items-center justify-center rounded-md text-muted transition-ui hover:bg-surface hover:text-status-error active:scale-[0.96] disabled:text-muted"
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
            {onPromote && candidate.status === 'pending' && (
              <button
                type="button"
                onClick={() => onPromote(candidate.id)}
                disabled={actionDisabled}
                className="flex h-8 items-center gap-1.5 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] active:bg-signal-deep disabled:bg-surface disabled:text-muted"
              >
                <BriefcaseBusiness className="h-3.5 w-3.5" aria-hidden="true" />
                {busy ? <span className="ownix-shimmer">Creating...</span> : 'Create job'}
              </button>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
