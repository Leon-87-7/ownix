'use client';

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
      className="h-8 rounded-md border border-line bg-surface px-3 text-[12px] font-medium text-body transition-ui hover:bg-raised hover:text-ink disabled:cursor-not-allowed disabled:bg-canvas disabled:text-muted"
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
    retryPending,
    retryError,
    clearFailed,
  } = useRecovery(contentType, onRecovered);

  const failedActionCount = summary.error_jobs + summary.stale_in_flight;
  const disabled = loading || acting !== null;

  const onClear = () => {
    if (!confirm(CLEAR_CONFIRM_COPY)) return;
    void clearFailed();
  };

  return (
    <section aria-label="Recovery" className="rounded-lg border border-line bg-surface p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">Recovery</h2>
        <span className="font-mono text-[11px] text-muted">
          {summary.stale_in_flight} stale in-flight
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <RecoveryButton disabled={disabled || summary.stale_pending === 0} onClick={() => void retryPending()}>
          {acting === 'pending' ? 'Retrying...' : `Retry pending (${summary.stale_pending})`}
        </RecoveryButton>
        <RecoveryButton disabled={disabled || failedActionCount === 0} onClick={() => void retryError()}>
          {acting === 'error' ? 'Retrying...' : `Retry failed (${failedActionCount})`}
        </RecoveryButton>
        <RecoveryButton disabled={disabled || summary.error_jobs === 0} onClick={onClear}>
          {acting === 'clear' ? 'Clearing...' : `Clear failed (${summary.error_jobs})`}
        </RecoveryButton>
      </div>
      {error && <p className="mt-2 text-xs text-status-error">{error}</p>}
    </section>
  );
}
