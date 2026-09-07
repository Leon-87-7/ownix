'use client';

import Link from 'next/link';
import { Newspaper, RotateCcw, Trash2 } from 'lucide-react';
import { DateTime } from '@/components/ui/date-time';
import { StatusBadge } from '@/components/ui/badges';
import type { NewsletterWatch } from '@/lib/newsletter-digest';

function asUtcIso(raw: string): string {
  return /[Zz]|[+-]\d\d:?\d\d$/.test(raw) ? raw : `${raw.replace(' ', 'T')}Z`;
}

export function NewsletterWatchCard({
  watch,
  onDelete,
  onRetry,
  deleting = false,
  retrying = false,
}: {
  watch: NewsletterWatch;
  onDelete?: (id: string) => void;
  onRetry?: (id: string) => void;
  deleting?: boolean;
  retrying?: boolean;
}) {
  const pending = watch.pending_count ?? 0;
  const errors = watch.error_count ?? 0;

  return (
    <div className="group rounded-lg border border-line bg-surface p-4 transition-ui hover:bg-raised">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Link href={`/newsletter-digest/${watch.id}`} className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 shrink-0 text-signal" aria-hidden="true" />
            <h2 className="truncate text-title font-semibold text-ink">{watch.name}</h2>
          </div>
          <p className="mt-1 truncate font-mono text-label text-muted">{watch.archive_url}</p>
        </Link>
        <div className="flex items-center gap-2">
          {errors > 0 && <StatusBadge label="error" />}
          {pending > 0 && <StatusBadge label="pending" />}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3 font-mono text-label text-muted">
          <span className="tabular-nums">{pending} pending</span>
          <span className="tabular-nums">{watch.promoted_count ?? 0} promoted</span>
          <span>
            Watching since <DateTime iso={asUtcIso(watch.watched_from)} />
          </span>
        </div>
        <div className="flex items-center gap-1">
          {errors > 0 && onRetry && (
            <button
              type="button"
              onClick={() => onRetry(watch.id)}
              disabled={retrying}
              className="flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-button font-medium text-ink transition-ui hover:bg-surface active:scale-[0.96] disabled:text-muted"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              {retrying ? 'Retrying...' : 'Retry'}
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              onClick={() => onDelete(watch.id)}
              disabled={deleting}
              aria-label={`Delete ${watch.name}`}
              className="flex h-8 w-8 items-center justify-center rounded-md text-muted transition-ui hover:bg-surface hover:text-status-error active:scale-[0.96] disabled:text-muted"
            >
              <Trash2 className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
