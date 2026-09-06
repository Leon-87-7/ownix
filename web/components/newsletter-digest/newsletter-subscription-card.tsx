'use client';

import Link from 'next/link';
import { Newspaper, RotateCcw, Trash2 } from 'lucide-react';
import { DateTime } from '@/components/ui/date-time';
import { CopyButton } from '@/components/ui/copy-button';
import { StatusBadge } from '@/components/ui/badges';
import type { NewsletterSubscription } from '@/lib/newsletter-digest';

function asUtcIso(raw: string): string {
  return /[Zz]|[+-]\d\d:?\d\d$/.test(raw) ? raw : `${raw.replace(' ', 'T')}Z`;
}

export function NewsletterSubscriptionCard({
  subscription,
  onDelete,
  onRetry,
  deleting = false,
  retrying = false,
}: {
  subscription: NewsletterSubscription;
  onDelete?: (id: string) => void;
  onRetry?: (id: string) => void;
  deleting?: boolean;
  retrying?: boolean;
}) {
  const pending = subscription.pending_count ?? 0;
  const errors = subscription.error_count ?? 0;

  return (
    <div className="group rounded-lg border border-line bg-surface p-4 transition-ui hover:bg-raised">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Link href={`/newsletter-digest/${subscription.id}`} className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Newspaper className="h-5 w-5 shrink-0 text-signal" aria-hidden="true" />
            <h2 className="truncate text-title font-semibold text-ink">
              {subscription.name}
            </h2>
          </div>
          <p className="mt-1 truncate font-mono text-label text-muted">
            {subscription.sender_email}
          </p>
        </Link>
        <div className="flex items-center gap-2">
          {errors > 0 && <StatusBadge label="error" />}
          {pending > 0 && <StatusBadge label="pending" />}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <code className="rounded-md border border-line bg-canvas px-2 py-1 font-mono text-label text-ink">
          {subscription.alias}
        </code>
        <CopyButton value={subscription.alias} ariaLabel="Copy alias" label="Copy" />
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-3 font-mono text-label text-muted">
          <span className="tabular-nums">{pending} pending</span>
          <span className="tabular-nums">{subscription.promoted_count ?? 0} promoted</span>
          <span>
            Created <DateTime iso={asUtcIso(subscription.created_at)} />
          </span>
        </div>
        <div className="flex items-center gap-1">
          {errors > 0 && onRetry && (
            <button
              type="button"
              onClick={() => onRetry(subscription.id)}
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
              onClick={() => onDelete(subscription.id)}
              disabled={deleting}
              aria-label={`Delete ${subscription.name}`}
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
