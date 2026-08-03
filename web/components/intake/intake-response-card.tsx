import Link from 'next/link';

import { IntakeActions } from '@/components/intake/intake-actions';
import type { IntakeActionShape, IntakeResponseShape } from '@/lib/hooks/useIntake';

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
  response,
  onAction,
  pendingActionId,
}: {
  response: IntakeResponseShape;
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
}) {
  const negative = NEGATIVE_KINDS.has(response.kind);
  return (
    <div
      className={`rounded-lg border p-4 ${
        negative ? 'border-status-error/40 bg-status-error-tint' : 'border-line bg-surface'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-label uppercase tracking-wide text-muted">
          {KIND_LABEL[response.kind] ?? response.kind}
        </span>
        {response.retryable && (
          <span className="font-mono text-label text-status-error">Retryable</span>
        )}
      </div>
      <p className="mt-1 whitespace-pre-wrap text-sm text-body">{response.text}</p>
      {response.job_id && (
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
  );
}
