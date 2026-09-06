'use client';

import Link from 'next/link';
import { BriefcaseBusiness, ExternalLink, Trash2 } from 'lucide-react';
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
    <article className="rounded-lg border border-line bg-surface p-4 transition-ui hover:bg-raised">
      <div className="flex gap-4">
        {candidate.thumbnail_url ? (
          // eslint-disable-next-line @next/next/no-img-element -- arbitrary OG image URL
          <img
            src={candidate.thumbnail_url}
            alt=""
            className="hidden aspect-video w-32 shrink-0 rounded-md object-cover outline outline-1 outline-white/10 sm:block"
          />
        ) : (
          <div className="hidden aspect-video w-32 shrink-0 items-center justify-center rounded-md border border-line bg-canvas sm:flex">
            <ExternalLink className="h-5 w-5 text-muted" aria-hidden="true" />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <a
              href={candidate.url}
              target="_blank"
              rel="noopener noreferrer"
              className="min-w-0 flex-1 text-title font-semibold text-ink transition-ui hover:text-signal"
            >
              <span className="line-clamp-2">{title}</span>
            </a>
            <StatusBadge label={candidate.status} />
          </div>
          <p className="mt-1 truncate font-mono text-label text-muted">
            {hostname(candidate.url)}
          </p>
          <p className="mt-2 line-clamp-2 break-all font-mono text-label text-body">
            {candidate.url}
          </p>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
            <span className="font-mono text-label text-muted">
              Found <DateTime iso={asUtcIso(candidate.created_at)} />
            </span>
            <div className="flex items-center gap-2">
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
                  {busy ? 'Creating...' : 'Create job'}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </article>
  );
}
