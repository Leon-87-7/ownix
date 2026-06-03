/**
 * startPolling — calls fetchFn on a fixed interval.
 * Automatically stops when isIdleFn() returns true.
 * Returns a cancel function that stops polling immediately.
 */
export function startPolling(
  fetchFn: () => Promise<void>,
  isIdleFn: () => boolean,
  intervalMs = 10_000,
): () => void {
  let cancelled = false;

  const tick = async () => {
    if (cancelled || isIdleFn()) return;
    try {
      await fetchFn();
    } catch {
      // swallow fetch errors — caller handles UI state
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
