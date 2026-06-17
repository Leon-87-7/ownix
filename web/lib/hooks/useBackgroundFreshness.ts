'use client';

import { useEffect, useRef } from 'react';

const BACKSTOP_INTERVAL_MS = 120_000; // ~2 min

/**
 * useBackgroundFreshness — silent focus-refetch + backstop poll.
 *
 * Given the `reload` function from `useFeedData` (which never sets `loading`,
 * so no skeleton flashes), this hook:
 *
 * 1. Fires ONE immediate `reload()` whenever the tab becomes visible
 *    (visibilitychange → visible). This is the load-bearing trigger: the main
 *    flow is "send a link on Telegram → flip back to dashboard".
 *
 * 2. Runs a ~2 min interval that calls `reload()` ONLY while the tab is
 *    visible. The interval is paused when hidden and resumes on the next tick
 *    after the tab becomes visible again.
 *
 * SSR-safe: all DOM access is guarded inside effects.
 * Cleans up listeners and timers on unmount.
 */
export function useBackgroundFreshness(reload: () => Promise<void>) {
  // Keep a stable ref so event listeners always call the latest reload without
  // being replaced (avoids effect re-runs on every render).
  const reloadRef = useRef(reload);
  reloadRef.current = reload;

  useEffect(() => {
    if (typeof document === 'undefined') return;

    // Guards against the unmount-racing-the-async-callback case: if the effect
    // is cleaned up while the awaited reload() is in flight, this flag stops the
    // callback from rescheduling an orphaned timer that would never be cleared.
    let cancelled = false;

    // -------------------------------------------------------------------------
    // 1. Backstop interval — only ticks while the tab is visible.
    // -------------------------------------------------------------------------
    let backstopTimer: ReturnType<typeof setTimeout> | null = null;

    const scheduleBackstop = () => {
      backstopTimer = setTimeout(async () => {
        if (cancelled) return;
        if (document.visibilityState === 'visible') {
          await reloadRef.current();
        }
        // Reschedule regardless so we keep a consistent cadence — unless the
        // effect was torn down while the await above was pending.
        if (!cancelled) scheduleBackstop();
      }, BACKSTOP_INTERVAL_MS);
    };

    scheduleBackstop();

    // -------------------------------------------------------------------------
    // 2. visibilitychange — fire one immediate reload on becoming visible.
    // -------------------------------------------------------------------------
    const onVisibilityChange = () => {
      if (cancelled) return;
      if (document.visibilityState === 'visible') {
        void reloadRef.current();
      }
    };

    document.addEventListener('visibilitychange', onVisibilityChange);

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibilityChange);
      if (backstopTimer !== null) clearTimeout(backstopTimer);
    };
  }, []); // intentionally empty — reloadRef keeps the ref fresh
}
