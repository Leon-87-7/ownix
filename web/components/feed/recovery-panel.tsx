'use client';

import { useEffect, useState } from 'react';
import type React from 'react';

import { useRecovery } from '@/lib/hooks/useRecovery';

const CLEAR_CONFIRM_COPY = 'Clear failed jobs in this tab? This marks them cancelled; it does not delete them from DB.';

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
      className="h-8 rounded-md border border-line bg-surface px-3 text-[12px] font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink active:bg-canvas disabled:cursor-not-allowed disabled:border-line disabled:bg-canvas disabled:text-muted"
    >
      {children}
    </button>
  );
}

export function RecoveryPanel({
  contentType,
  onRecovered,
}: {
  contentType: string;
  onRecovered: () => Promise<void> | void;
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
  const attentionCount =
    summary.stale_pending + summary.error_jobs + summary.stale_in_flight;
  const disabled = loading || acting !== null;
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (attentionCount === 0) setOpen(false);
  }, [attentionCount]);

  const onClear = () => {
    if (!confirm(CLEAR_CONFIRM_COPY)) return;
    void clearFailed();
  };

  if (attentionCount === 0) {
    if (!error) return null;
    return (
      <div className="flex flex-wrap items-center justify-end gap-2 text-xs text-muted">
        <span>{error}. The feed is still usable.</span>
        <button
          type="button"
          disabled={disabled}
          onClick={() => void reload()}
          className="h-7 rounded-md border border-line bg-surface px-2.5 text-[12px] font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
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
        className="h-8 rounded-md border border-status-error/40 bg-status-error-tint px-3 font-mono text-[11px] font-medium text-status-error tabular-nums transition-ui hover:border-status-error hover:bg-status-error-tint/80"
      >
        {attentionCount} need attention
      </button>
      <div
        id="recovery-actions"
        role="group"
        aria-label="Recovery"
        className={`flex flex-wrap items-center gap-2 ${open ? '' : 'hidden'}`}
      >
        {summary.stale_in_flight > 0 && (
          <span className="font-mono text-[11px] text-muted">
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
          <RecoveryButton disabled={disabled} onClick={onClear}>
            {acting === 'clear'
              ? 'Clearing...'
              : `Clear failed (${summary.error_jobs})`}
          </RecoveryButton>
        )}
      </div>
      {error && (
        <div className="flex w-full items-center justify-end gap-2 text-xs text-muted">
          <span>{error}. Retry recovery when ready.</span>
          <button
            type="button"
            disabled={disabled}
            onClick={() => void reload()}
            className="h-7 rounded-md border border-line bg-surface px-2.5 text-[12px] font-medium text-body transition-ui hover:border-line-strong hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
          >
            Retry
          </button>
        </div>
      )}
    </div>
  );
}
