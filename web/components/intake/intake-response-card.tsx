'use client';

/* @ds
name: IntakeResponseCard
purpose: One turn of the intake console — echoes what was submitted, then renders the server's response: kind label, retry, extracted links, in-flight status or a finished PreviewCard, action buttons, and inline tag-creation offers.
when-not: Session-thread specific (IntakeThread); not a general-purpose response/result card.
notes: create_tag actions render as IntakeTagOffer inline forms, split out from the plain IntakeActions button row — don't lump the two together.
status: inferred
*/

import Link from 'next/link';
import { useState } from 'react';

import { IntakeActions } from '@/components/intake/intake-actions';
import { IntakeLinksList, extractLinks } from '@/components/intake/intake-links-list';
import { IntakeStatusLine } from '@/components/intake/intake-status-line';
import { IntakeTagOffer } from '@/components/intake/intake-tag-offer';
import { PreviewCard } from '@/components/feed/preview-card';
import type { IntakeThreadItem } from '@/lib/hooks/useIntakeThread';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';
import { CopyButton } from '@/components/ui/copy-button';

const KIND_LABEL: Record<string, string> = {
  job_created: 'Job created',
  job_deduped: 'Already tracked',
  unsupported: 'Unsupported',
  rejected: 'Rejected',
  error: 'Error',
  command_result: 'Command',
  checklists_result: 'Checklist',
  state_update: 'State',
  action_ack: 'Action',
};

const NEGATIVE_KINDS = new Set(['unsupported', 'rejected', 'error']);

export function IntakeResponseCard({
  item,
  onAction,
  pendingActionId,
  openOfferId,
  onOpenOffer,
  onSaveOffer,
}: {
  item: IntakeThreadItem;
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
  /** The one `create_tag` offer currently expanded — offers open one at a time. */
  openOfferId?: string | null;
  onOpenOffer?: (actionId: string | null) => void;
  onSaveOffer?: (action: IntakeActionShape) => Promise<void>;
}) {
  const { response, job, echo, retry } = item;
  const negative = NEGATIVE_KINDS.has(response.kind);
  const [retrying, setRetrying] = useState(false);
  const links = extractLinks(response.artifacts);

  // `create_tag` renders as its own inline form, not as a generic action button.
  const tagOffers = onSaveOffer
    ? response.actions.filter((a) => a.kind === 'create_tag')
    : [];
  const plainActions = response.actions.filter((a) => !tagOffers.includes(a));

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

        {response.kind === 'checklists_result' && (
          <div className="mt-3">
            <CopyButton value={response.text} ariaLabel="Copy checklist" label="Copy" />
          </div>
        )}

        {links.length > 0 && <IntakeLinksList links={links} />}

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
        {response.job_id && job !== null && job?.status !== 'done' && (
          <Link
            href={response.job_url ?? `/jobs/${response.job_id}`}
            className="mt-2 inline-block text-sm font-medium text-signal hover:text-signal-bright"
          >
            View job →
          </Link>
        )}

        {onAction && plainActions.length > 0 && (
          <IntakeActions
            actions={plainActions}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        )}

        {tagOffers.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {tagOffers.map((action, i) => (
              <IntakeTagOffer
                key={action.action_id}
                action={action}
                index={i}
                total={tagOffers.length}
                open={openOfferId === action.action_id}
                onOpen={() => onOpenOffer?.(action.action_id)}
                onCancel={() => onOpenOffer?.(null)}
                onSave={(values) =>
                  onSaveOffer!({
                    ...action,
                    payload: { ...action.payload, ...values, tag_name: values.name },
                  })
                }
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
