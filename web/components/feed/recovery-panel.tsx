'use client';

import { useCallback, useEffect, useState } from 'react';
import type React from 'react';

import { useRecovery } from '@/lib/hooks/useRecovery';
import { useSubmitJobOptional } from '@/components/feed/submit-job';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

function RecoveryButton({
  children,
  disabled,
  onClick,
}: {
  children: React.ReactNode;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="h-8 rounded-md border border-line bg-surface px-3 text-label font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink active:bg-canvas disabled:cursor-not-allowed disabled:border-line disabled:bg-canvas disabled:text-muted"
    >
      {children}
    </button>
  );
}

export function RecoveryPanel({
  contentType,
  onRecovered,
  active = true,
}: {
  contentType: string;
  onRecovered: () => Promise<void> | void;
  /** false on the Links view — link inventory has no job status lifecycle, so
   * the panel and its launcher commands are suppressed. */
  active?: boolean;
}) {
  const {
    summary,
    loading,
    acting,
    error,
    reload,
    retryPending,
    retryError,
    clearFailed,
  } = useRecovery(contentType, onRecovered);

  const failedActionCount = summary.error_jobs + summary.stale_in_flight;
  const canClearFailed = summary.error_jobs > 0;

  // Mirrors Clear Failed into the command launcher (when mounted inside
  // SubmitJobProvider) so its scope + availability stay in sync with this
  // panel. `requestClearFailed` just opens the one styled confirm below -
  // shared by this panel's own button, the "c" keyboard shortcut, and the
  // command palette, instead of each gating its own native confirm().
  const [confirmClearOpen, setConfirmClearOpen] = useState(false);
  const requestClearFailed = useCallback(
    () => setConfirmClearOpen(true),
    [],
  );

  const registerFeedRecovery =
    useSubmitJobOptional()?.registerFeedRecovery;
  useEffect(() => {
    if (!registerFeedRecovery) return;
    if (!active) {
      registerFeedRecovery(null);
      return;
    }
    registerFeedRecovery({ canClearFailed, requestClearFailed });
    return () => registerFeedRecovery(null);
  }, [active, canClearFailed, registerFeedRecovery, requestClearFailed]);

  const attentionCount =
    summary.stale_pending + summary.error_jobs + summary.stale_in_flight;
  const disabled = loading || acting !== null;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (attentionCount === 0) setOpen(false);
  }, [attentionCount]);

  if (!active) return null;

  if (attentionCount === 0) {
    if (!error) return null;
    return (
      <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-muted">
        <span>{error}. The feed is still usable.</span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => void reload()}
          className="h-7 rounded-md border border-line bg-surface px-2.5 text-label font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center justify-end gap-2">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="recovery-actions"
        onClick={() => setOpen((current) => !current)}
        className="h-8 rounded-md border border-status-error/40 bg-status-error-tint px-3 font-mono text-mono-label font-medium text-status-error tabular-nums transition-ui hover:border-status-error hover:bg-status-error-tint/80"
      >
        {attentionCount} need attention
      </button>
      {/* Rendered only when expanded so assistive tech (and tests) don't see
          collapsed actions — a CSS-only `hidden` class stays in the a11y tree. */}
      {open && (
        <div
          id="recovery-actions"
          role="group"
          aria-label="Recovery"
          className="flex flex-wrap items-center gap-2"
        >
          {summary.stale_in_flight > 0 && (
            <span className="font-mono text-mono-label text-muted">
              {summary.stale_in_flight} stale in-flight
            </span>
          )}
          {summary.stale_pending > 0 && (
            <RecoveryButton
              disabled={disabled}
              onClick={() => void retryPending()}
            >
              {acting === 'pending'
                ? 'Retrying...'
                : `Retry pending (${summary.stale_pending})`}
            </RecoveryButton>
          )}
          {failedActionCount > 0 && (
            <RecoveryButton
              disabled={disabled}
              onClick={() => void retryError()}
            >
              {acting === 'error'
                ? 'Retrying...'
                : `Retry failed (${failedActionCount})`}
            </RecoveryButton>
          )}
          {summary.error_jobs > 0 && (
            <RecoveryButton disabled={disabled} onClick={requestClearFailed}>
              {acting === 'clear'
                ? 'Clearing...'
                : `Clear failed (${summary.error_jobs})`}
            </RecoveryButton>
          )}
        </div>
      )}
      <ConfirmDialog
        open={confirmClearOpen}
        onOpenChange={setConfirmClearOpen}
        title="Clear failed jobs?"
        description="This marks them cancelled in this tab. It does not delete them from the database."
        confirmLabel="Clear failed"
        pending={acting === 'clear'}
        pendingLabel="Clearing…"
        onConfirm={() => clearFailed()}
      />
      {error && (
        <div className="flex w-full items-center justify-end gap-2 text-xs text-muted">
          <span>{error}. Retry recovery when ready.</span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void reload()}
            className="h-7 rounded-md border border-line bg-surface px-2.5 text-label font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
