/** Job statuses that mean "still working" — the single source of truth for in-flight polling. */
export const IN_FLIGHT_STATUSES = new Set([
  'pending',
  'queued',
  'processing',
  'transcript_done',
  'enriching',
]);

/**
 * startPolling — calls fetchFn on a fixed interval.
 * Automatically stops when isIdleFn() returns true.
 * Skips the tick (but keeps scheduling) when the document is hidden, so all
 * polling pauses while the tab is not visible and resumes on the next natural
 * tick once it becomes visible again.
 * Returns a cancel function that stops polling immediately.
 */
export function startPolling(
  fetchFn: () => Promise<void>,
  isIdleFn: () => boolean,
  intervalMs = 10_000,
): () => void {
  let cancelled = false;

  const isHidden = () =>
    typeof document !== 'undefined' && document.visibilityState === 'hidden';

  const tick = async () => {
    if (cancelled || isIdleFn()) return;
    // Skip the fetch when the tab is hidden; schedule the next tick anyway so
    // polling picks back up on the next interval after the tab becomes visible.
    if (!isHidden()) {
      try {
        await fetchFn();
      } catch {
        // swallow fetch errors — caller handles UI state
      }
    }
    if (!cancelled && !isIdleFn()) {
      setTimeout(tick, intervalMs);
    }
  };

  // Kick off after first interval
  const timer = setTimeout(tick, intervalMs);

  return () => {
    cancelled = true;
    clearTimeout(timer);
  };
}
