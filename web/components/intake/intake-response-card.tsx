'use client';

import Link from 'next/link';
import { useState } from 'react';

import { IntakeActions } from '@/components/intake/intake-actions';
import { IntakeStatusLine } from '@/components/intake/intake-status-line';
import { PreviewCard } from '@/components/feed/preview-card';
import type { IntakeThreadItem } from '@/lib/hooks/useIntakeThread';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';

const KIND_LABEL: Record<string, string> = {
  job_created: 'Job created',
  job_deduped: 'Already tracked',
  unsupported: 'Unsupported',
  rejected: 'Rejected',
  error: 'Error',
  command_result: 'Command',
  state_update: 'State',
  action_ack: 'Action',
};

const NEGATIVE_KINDS = new Set(['unsupported', 'rejected', 'error']);

export function IntakeResponseCard({
  item,
  onAction,
  pendingActionId,
}: {
  item: IntakeThreadItem;
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
}) {
  const { response, job, echo, retry } = item;
  const negative = NEGATIVE_KINDS.has(response.kind);
  const [retrying, setRetrying] = useState(false);

  const handleRetry = async () => {
    if (!retry || retrying) return;
    setRetrying(true);
    try {
      await retry();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <div className="space-y-1">
      {echo && (
        <p className="truncate pl-1 font-mono text-label text-muted" title={echo}>
          {echo}
        </p>
      )}

      <div
        className={`rounded-lg border p-4 ${
          negative ? 'border-status-error/40 bg-status-error-tint' : 'border-line bg-surface'
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-mono text-label uppercase tracking-wide text-muted">
            {KIND_LABEL[response.kind] ?? response.kind}
          </span>
          {response.retryable && retry && (
            <button
              type="button"
              onClick={handleRetry}
              disabled={retrying}
              className="h-7 shrink-0 rounded-md border border-line bg-raised px-2.5 font-mono text-label text-ink transition-ui hover:border-signal hover:text-signal disabled:opacity-50"
            >
              {retrying ? 'Retrying…' : 'Try again'}
            </button>
          )}
        </div>

        <p className="mt-1 whitespace-pre-wrap text-sm text-body">{response.text}</p>

        {/* `job === undefined` means not yet resolved; `null` means the row is
            gone (deleted). Only a resolved job drives the live treatment. */}
        {job && job.status !== 'done' && <IntakeStatusLine status={job.status} />}

        {job && job.status === 'done' && (
          <div className="mt-3 max-w-xs">
            <PreviewCard job={job} index={0} variant="compact" />
          </div>
        )}

        {job === null && response.job_id && (
          <p className="mt-2 font-mono text-label text-muted">Job no longer exists.</p>
        )}

        {/* The finished PreviewCard is itself a link to the job, so the text
            link is only needed until then. */}
        {response.job_id && job?.status !== 'done' && (
          <Link
            href={response.job_url ?? `/jobs/${response.job_id}`}
            className="mt-2 inline-block text-sm font-medium text-signal hover:text-signal-bright"
          >
            View job →
          </Link>
        )}

        {onAction && (
          <IntakeActions
            actions={response.actions}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        )}
      </div>
    </div>
  );
}
