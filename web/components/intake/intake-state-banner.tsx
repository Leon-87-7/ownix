'use client';

import { useCallback, useEffect, useState } from 'react';

interface PendingState {
  mode: string;
  job_id: string;
  expires_at: string;
}

const MODE_LABEL: Record<string, string> = {
  awaiting_intent: 'Waiting for your intent text',
  awaiting_freestyle: 'Waiting for your freestyle prompt',
};

/**
 * Pending-flow banner for `/intake` (issue #474). Pending state is
 * last-write-wins across channels (chat_id-keyed, not per-channel — see
 * `src/intake/state.py`), so this always reflects the single active flow
 * regardless of whether it was armed from Telegram or the dashboard.
 */
const POLL_INTERVAL_MS = 20_000;

export function IntakeStateBanner() {
  const [pending, setPending] = useState<PendingState | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/intake/state');
      if (!res.ok) return;
      const data = (await res.json()) as { pending: PendingState | null };
      setPending(data.pending);
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    load();
    // Pending state can resolve/expire server-side (Telegram reply, the
    // sweeper) without any local event to react to — poll so the banner
    // doesn't go stale until the next full page load.
    const interval = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [load]);

  const handleCancel = async () => {
    setCancelling(true);
    setCancelError(false);
    try {
      const res = await fetch('/api/intake/state', { method: 'DELETE' });
      if (res.ok) {
        setPending(null);
      } else {
        setCancelError(true);
      }
    } catch {
      setCancelError(true);
    } finally {
      setCancelling(false);
    }
  };

  if (!loaded || !pending) return null;

  return (
    <section className="space-y-2">
      <div className="flex items-center justify-between gap-3 rounded-lg border border-signal/40 bg-status-pending-tint px-4 py-3">
        <p className="text-sm text-ink">
          {MODE_LABEL[pending.mode] ?? pending.mode} —{' '}
          <span className="font-mono">job_{pending.job_id.slice(-4)}</span>
        </p>
        <button
          type="button"
          onClick={handleCancel}
          disabled={cancelling}
          className="h-8 shrink-0 rounded-md border border-line bg-raised px-3 text-sm font-medium text-ink transition-ui hover:border-status-error hover:text-status-error disabled:opacity-50"
        >
          {cancelling ? 'Cancelling…' : 'Cancel'}
        </button>
      </div>
      {cancelError && (
        <p
          role="alert"
          className="text-sm text-status-error"
        >
          Couldn&apos;t cancel — try again.
        </p>
      )}
    </section>
  );
}
