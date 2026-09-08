'use client';

import Link from 'next/link';
import { BriefcaseBusiness, Trash2 } from 'lucide-react';
import { DateTime } from '@/components/ui/date-time';
import { StatusBadge } from '@/components/ui/badges';
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

// List-layout sibling of NewsletterCandidateCard — same shape as JobCard
// (components/feed/job-card.tsx): a dense single row, no thumbnail. Toggled
// against the card via the grid/list control on NewsletterDigestDetail, the
// same control the Feed page uses for jobs.
export function NewsletterCandidateRow({
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
    <div className="relative rounded-lg border border-line bg-surface px-4 py-3 transition-ui hover:bg-raised">
      <a
        href={candidate.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={title}
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset"
      />
      <div className="pointer-events-none flex items-start justify-between gap-3">
        <p className="min-w-0 flex-1 truncate text-sm text-ink">{title}</p>
        <StatusBadge label={candidate.status} />
      </div>
      <div className="pointer-events-none mt-2 flex items-center justify-between gap-3">
        <p className="truncate font-mono text-xs text-muted">
          {hostname(candidate.url)} · <DateTime iso={asUtcIso(candidate.created_at)} />
        </p>
        <div className="pointer-events-auto relative z-10 flex shrink-0 items-center gap-2">
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
        </div>
      </div>
    </div>
  );
}
