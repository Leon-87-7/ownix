'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { startPolling } from '@/lib/polling';
import type { JobSummary } from '@/components/feed/job-card';
import type { IntakeResponseShape } from '@/lib/hooks/useIntake';

/** Statuses that mean "still working" — mirrors `useInFlightPolling`. */
const IN_FLIGHT = new Set(['pending', 'queued', 'processing', 'transcript_done', 'enriching']);

const STORAGE_KEY = 'ownix.intake.thread';

export interface IntakeThreadItem {
  id: string;
  /** What the user sent, echoed above the card so the reply has a subject. */
  echo?: string;
  response: IntakeResponseShape;
  /**
   * Live job state, re-derived from `/api/jobs` — never persisted. A restored
   * card must not trust its stored text: a card saved while the job read
   * `processing` would otherwise reload an hour later still claiming so.
   */
  job?: JobSummary | null;
  /**
   * Replays the submit that produced this item. Not persisted — an upload's
   * `File` cannot survive `sessionStorage`, so retry is unavailable after a
   * reload rather than silently broken.
   */
  retry?: () => Promise<void>;
}

interface PersistedItem {
  id: string;
  echo?: string;
  response: IntakeResponseShape;
}

function readStored(): IntakeThreadItem[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    // Keep only entries that still look like the contract — a half-written or
    // schema-drifted payload should degrade to an empty thread, never throw.
    return (parsed as PersistedItem[])
      .filter((i) => i && typeof i.id === 'string' && i.response && typeof i.response.kind === 'string')
      .map((i) => ({ id: i.id, echo: i.echo, response: i.response }));
  } catch {
    return [];
  }
}

function jobIdsOf(items: IntakeThreadItem[]): string[] {
  return items.map((i) => i.response.job_id).filter((id): id is string => Boolean(id));
}

export function useIntakeThread() {
  const [items, setItems] = useState<IntakeThreadItem[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const itemsRef = useRef<IntakeThreadItem[]>([]);

  useEffect(() => {
    itemsRef.current = items;
  }, [items]);

  // Hydrate once from sessionStorage: survives reload and back/forward, empty
  // in a new tab and after the browser session ends (issue #488).
  useEffect(() => {
    setItems(readStored());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      const persisted: PersistedItem[] = items.map(({ id, echo, response }) => ({ id, echo, response }));
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(persisted));
    } catch {
      // Quota or a disabled store: the thread just doesn't survive reload.
    }
  }, [items, hydrated]);

  /**
   * One request per tick regardless of card count. Intake-created jobs are
   * usually the newest rows (`list_jobs` orders `created_at DESC`), so a
   * window sized to the card count almost always contains them without a
   * `?ids=` filter this endpoint doesn't have. An id that falls outside the
   * window (older jobs pushed out by newer ones elsewhere) keeps its prior
   * resolved state rather than being assumed deleted — a real deletion is
   * still caught once the job re-enters the window on a later poll tick.
   */
  const refreshIds = useCallback(async (ids: string[]) => {
    if (ids.length === 0) return;

    const limit = Math.min(Math.max(ids.length, 20), 1000);
    const res = await fetch(`/api/jobs?limit=${limit}`);
    if (!res.ok) return;
    const data = (await res.json()) as { items?: JobSummary[] };
    const byId = new Map((data.items ?? []).map((j) => [j.id, j]));

    setItems((prev) =>
      prev.map((item) => {
        const jobId = item.response.job_id;
        if (!jobId || !byId.has(jobId)) return item;
        return { ...item, job: byId.get(jobId) ?? null };
      }),
    );
  }, []);

  const refresh = useCallback(
    () => refreshIds(jobIdsOf(itemsRef.current)),
    [refreshIds],
  );

  useEffect(() => {
    if (!hydrated) return;
    void refresh();
  }, [hydrated, refresh]);

  useEffect(() => {
    if (!hydrated) return;
    const isIdle = () =>
      itemsRef.current.every((i) => {
        if (!i.response.job_id) return true;
        // `undefined` means "not resolved yet" — keep polling until it is.
        if (i.job === undefined) return false;
        return i.job === null || !IN_FLIGHT.has(i.job.status);
      });
    return startPolling(refresh, isIdle, 10_000);
  }, [hydrated, refresh]);

  const add = useCallback(
    (item: Omit<IntakeThreadItem, 'id'> & { id?: string }) => {
      const withId: IntakeThreadItem = { ...item, id: item.id ?? crypto.randomUUID() };
      setItems((prev) => [withId, ...prev]);
      // A brand-new job starts in flight; pull its real state without waiting a
      // full poll interval. The id is passed explicitly rather than read back
      // off the ref, which is still a render behind this call.
      if (withId.response.job_id) {
        void refreshIds([withId.response.job_id, ...jobIdsOf(itemsRef.current)]);
      }
    },
    [refreshIds],
  );

  const clear = useCallback(() => setItems([]), []);

  // Drops a saved offer (e.g. a `create_tag` action) from whichever item
  // still lists it, so a later `y` doesn't resurface and resubmit it.
  const removeAction = useCallback((actionId: string) => {
    setItems((prev) =>
      prev.map((item) =>
        item.response.actions.some((a) => a.action_id === actionId)
          ? {
              ...item,
              response: {
                ...item.response,
                actions: item.response.actions.filter((a) => a.action_id !== actionId),
              },
            }
          : item,
      ),
    );
  }, []);

  return { items, hydrated, add, clear, refresh, removeAction };
}
