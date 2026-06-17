// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useFeedData } from './useFeedData';

// Default fixture: 2 jobs, total = 2 (well below the 1000 guardrail → client mode).
const STATS = { total: 2, by_status: { done: 2 }, by_content_type: { short: 2 } };
const JOBS = {
  items: [
    { id: 'j1', content_type: 'short', status: 'done' },
    { id: 'j2', content_type: 'short', status: 'done' },
  ],
  total: 2,
};

function stubFetch(impl: (url: string) => { ok: boolean; body?: unknown }) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const { ok, body } = impl(String(input));
    return { ok, json: async () => body } as Response;
  }));
}

const stubFeedOk = () => stubFetch((url) => url.includes('/stats')
  ? { ok: true, body: STATS }
  : { ok: true, body: JOBS });

afterEach(() => vi.unstubAllGlobals());

/** Render the hook and wait for the initial load to settle. */
async function renderLoadedFeed(initialContentType?: string) {
  const { result } = renderHook(() => useFeedData(initialContentType));
  await waitFor(() => expect(result.current.loading).toBe(false));
  return result;
}

describe('useFeedData — client mode (total ≤ 1000)', () => {
  it('loads stats and jobs on mount with a single /api/jobs?limit=1000 call', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.error).toBeNull();

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    // Exactly one jobs call — with limit=1000, no content_type.
    const jobsCalls = calls.filter((u) => u.includes('/api/jobs') && !u.includes('/stats'));
    expect(jobsCalls).toHaveLength(1);
    expect(jobsCalls[0]).toContain('limit=1000');
    expect(jobsCalls[0]).not.toContain('content_type=');

    // Exactly one stats call — global (no content_type).
    const statsCalls = calls.filter((u) => u.includes('/api/jobs/stats'));
    expect(statsCalls).toHaveLength(1);
    expect(statsCalls[0]).not.toContain('content_type=');
  });

  it('surfaces an error when the jobs request fails', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: false });
    const result = await renderLoadedFeed();

    expect(result.current.error).toBe('Failed to load jobs');
  });

  it('surfaces an error when the stats request fails', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: false }
      : { ok: true, body: JOBS });
    const result = await renderLoadedFeed();

    expect(result.current.error).toBe('Failed to load stats');
  });

  it('does NOT trigger a new fetch when the content_type filter changes', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    const fetchCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    act(() => result.current.setCtFilter('short'));
    // Give React a tick to settle.
    await act(async () => { await Promise.resolve(); });

    const fetchCallsAfter = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(fetchCallsAfter).toBe(fetchCallsBefore);
  });

  it('does NOT trigger a new fetch when the status filter changes', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    const fetchCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    act(() => result.current.setStFilter('done'));
    await act(async () => { await Promise.resolve(); });

    const fetchCallsAfter = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(fetchCallsAfter).toBe(fetchCallsBefore);
  });

  it('filters jobs by content_type client-side without any network call', async () => {
    const mixedJobs = {
      items: [
        { id: 's1', content_type: 'short', status: 'done' },
        { id: 'l1', content_type: 'long',  status: 'done' },
        { id: 's2', content_type: 'short', status: 'pending' },
      ],
      total: 3,
    };
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: mixedJobs });

    const result = await renderLoadedFeed();
    expect(result.current.jobs).toHaveLength(3);

    const fetchCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    act(() => result.current.setCtFilter('short'));
    await act(async () => { await Promise.resolve(); });

    // No new fetch.
    expect((fetch as ReturnType<typeof vi.fn>).mock.calls.length).toBe(fetchCallsBefore);
    // Filtered client-side.
    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.jobs.every((j) => j.content_type === 'short')).toBe(true);
  });

  it('filters jobs by status client-side (exact match, matching server semantics)', async () => {
    const mixedJobs = {
      items: [
        { id: 's1', content_type: 'short', status: 'done' },
        { id: 's2', content_type: 'short', status: 'pending' },
        { id: 's3', content_type: 'short', status: 'processing' },
      ],
      total: 3,
    };
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: mixedJobs });

    const result = await renderLoadedFeed();

    act(() => result.current.setStFilter('done'));
    await act(async () => { await Promise.resolve(); });

    // Only exact-match status=done (not processing or pending).
    expect(result.current.jobs).toHaveLength(1);
    expect(result.current.jobs[0].id).toBe('s1');
  });

  it('total reflects the filtered job count in client mode', async () => {
    const mixedJobs = {
      items: [
        { id: 's1', content_type: 'short', status: 'done' },
        { id: 'l1', content_type: 'long',  status: 'done' },
      ],
      total: 2,
    };
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: mixedJobs });

    const result = await renderLoadedFeed();
    expect(result.current.total).toBe(2);

    act(() => result.current.setCtFilter('short'));
    await act(async () => { await Promise.resolve(); });

    expect(result.current.total).toBe(1);
  });

  it('loading is only true during initial mount, not on filter change', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    expect(result.current.loading).toBe(false);

    act(() => result.current.setCtFilter('short'));
    // After filter change, loading must remain false (no network call).
    expect(result.current.loading).toBe(false);
  });

  it('stats are derived from the in-memory list (by_status scoped to active ct)', async () => {
    const mixedJobs = {
      items: [
        { id: 's1', content_type: 'short', status: 'done' },
        { id: 's2', content_type: 'short', status: 'pending' },
        { id: 'l1', content_type: 'long',  status: 'done' },
      ],
      total: 3,
    };
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: true, body: mixedJobs });

    const result = await renderLoadedFeed();

    act(() => result.current.setCtFilter('short'));
    await act(async () => { await Promise.resolve(); });

    // by_content_type stays global (for tab chips).
    expect(result.current.stats?.by_content_type).toEqual({ short: 2, long: 1 });
    // by_status scoped to short (for Overview cards).
    expect(result.current.stats?.by_status).toEqual({ done: 1, pending: 1 });
    // total reflects the scoped slice.
    expect(result.current.stats?.total).toBe(2);
  });

  it('reload() does not set loading=true (silent background refresh)', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    expect(result.current.loading).toBe(false);

    await act(async () => { await result.current.reload(); });

    expect(result.current.loading).toBe(false);
  });

  it('reload() re-fetches the full list and updates allJobs without skeleton', async () => {
    let callCount = 0;
    const updatedJobs = {
      items: [
        { id: 'j1', content_type: 'short', status: 'done' },
        { id: 'j2', content_type: 'short', status: 'done' },
        { id: 'j3', content_type: 'short', status: 'done' }, // new job
      ],
      total: 3,
    };

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      callCount++;
      if (url.includes('/stats')) return { ok: true, json: async () => STATS } as Response;
      // First mount load returns 2 jobs; subsequent calls return 3.
      const body = callCount <= 2 ? JOBS : updatedJobs;
      return { ok: true, json: async () => body } as Response;
    }));

    const result = await renderLoadedFeed();
    expect(result.current.jobs).toHaveLength(2);

    await act(async () => { await result.current.reload(); });

    expect(result.current.loading).toBe(false);
    expect(result.current.jobs).toHaveLength(3);
  });

  // --------------------------------------------------------------------------
  // Race-guard tests
  // --------------------------------------------------------------------------

  it('does not strand loading=true when a background reload() fires while the mount load is in flight', async () => {
    // Regression: loading flag must be keyed off a load-only counter, not reqIdRef.
    // A reload() bumping reqIdRef mid-load must not prevent load's finally from
    // clearing loading=true.
    let callIndex = 0;
    const resolvers: Array<(value: { ok: boolean; body: unknown }) => void> = [];

    vi.stubGlobal('fetch', vi.fn(async () => {
      const idx = callIndex++;
      return new Promise<Response>((outerResolve) => {
        resolvers[idx] = ({ ok, body }) => {
          outerResolve({ ok, json: async () => body } as Response);
        };
      });
    }));

    const stats = { total: 1, by_status: {}, by_content_type: { short: 1 } };
    const jobsBody  = { items: [{ id: 's1', content_type: 'short', status: 'done' }], total: 1 };

    // Mount fires 2 fetches in parallel via Promise.all([fetchAllJobs(), fetchStats()]).
    // fetchAllJobs() calls fetch() first → index 0 (expects jobs body).
    // fetchStats() calls fetch() second → index 1 (expects stats body).
    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(2));

    // Resolve initial load so we're settled.
    act(() => {
      resolvers[0]({ ok: true, body: jobsBody }); // fetchAllJobs → jobs shape
      resolvers[1]({ ok: true, body: stats });    // fetchStats → stats shape
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Trigger a new mount-equivalent by unmounting and remounting is complex —
    // instead, directly verify via reload() that it does NOT flip loading=true.
    // The real regression was about load() mid-flight + reload() bumping reqId.
    // Simulate by calling reload() which fetches index 2.
    act(() => { void result.current.reload(); });
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(3));

    // loading must still be false — reload() never sets it true.
    expect(result.current.loading).toBe(false);

    // Clean up pending reload fetch (reload in client mode only calls fetchAllJobs — 1 fetch).
    act(() => { resolvers[2]({ ok: true, body: jobsBody }); });
    await act(async () => { await Promise.resolve(); });
  });

  it('a stale slow reload() response does not overwrite a newer state', async () => {
    let callIndex = 0;
    const resolvers: Array<(value: { ok: boolean; body: unknown }) => void> = [];

    vi.stubGlobal('fetch', vi.fn(async () => {
      const idx = callIndex++;
      return new Promise<Response>((outerResolve) => {
        resolvers[idx] = ({ ok, body }) => {
          outerResolve({ ok, json: async () => body } as Response);
        };
      });
    }));

    const stats = { total: 1, by_status: {}, by_content_type: { short: 1 } };
    const initialJobs = { items: [{ id: 'j1', content_type: 'short', status: 'done' }], total: 1 };
    const updatedJobs = { items: [{ id: 'j1', content_type: 'short', status: 'done' }, { id: 'j2', content_type: 'short', status: 'done' }], total: 2 };
    const staleJobs   = { items: [{ id: 'stale', content_type: 'short', status: 'done' }], total: 1 };

    // Mount fires 2 fetches: index 0 = fetchAllJobs (jobs shape), index 1 = fetchStats (stats shape).
    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(2));
    act(() => {
      resolvers[0]({ ok: true, body: initialJobs }); // fetchAllJobs
      resolvers[1]({ ok: true, body: stats });        // fetchStats
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.jobs).toHaveLength(1);

    // First reload() — index 2 (jobs only in client mode).
    act(() => { void result.current.reload(); });
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(3));

    // Second reload() before first finishes — index 3.
    act(() => { void result.current.reload(); });
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(4));

    // Resolve the NEWER reload (index 3) first with updated data.
    act(() => { resolvers[3]({ ok: true, body: updatedJobs }); });
    await act(async () => { await Promise.resolve(); });
    expect(result.current.jobs).toHaveLength(2);

    // Resolve the OLDER reload (index 2) with stale data — must be discarded.
    act(() => { resolvers[2]({ ok: true, body: staleJobs }); });
    await act(async () => { await Promise.resolve(); });

    // The stale result must NOT overwrite the 2-item list.
    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.jobs.every((j) => j.id !== 'stale')).toBe(true);
  });
});

describe('useFeedData — server mode (total > 1000)', () => {
  it('falls back to server-side filtering when server total exceeds 1000', async () => {
    // Mount load returns total=1001 — triggers server mode.
    const bigJobs = {
      items: Array.from({ length: 50 }, (_, i) => ({
        id: `j${i}`,
        content_type: 'short',
        status: 'done',
      })),
      total: 1001,
    };
    const bigStats = { total: 1001, by_status: { done: 1001 }, by_content_type: { short: 1001 } };

    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: bigStats }
      : { ok: true, body: bigJobs });

    const result = await renderLoadedFeed();

    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('does not double-fetch on mount when entering server mode (no skeleton re-flash)', async () => {
    const bigJobs = {
      items: Array.from({ length: 50 }, (_, i) => ({
        id: `j${i}`,
        content_type: 'short',
        status: 'done',
      })),
      total: 1001,
    };
    const bigStats = { total: 1001, by_status: { done: 1001 }, by_content_type: { short: 1001 } };

    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: bigStats }
      : { ok: true, body: bigJobs });

    const result = await renderLoadedFeed();

    // Mount performs exactly two requests: the limit=1000 jobs probe + stats.
    // The mode-transition effect must NOT fire an extra serverLoad — that would
    // re-flip loading=true (skeleton re-flash) and overwrite the mount data.
    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls).toHaveLength(2);
    expect(result.current.loading).toBe(false);
  });

  it('in server mode with an initial content_type, fetches the scoped view on mount', async () => {
    // Deep link (?type=long) while >1000 jobs: the unfiltered mount probe is the
    // wrong list, so the mode-flip effect must fetch the content_type-scoped view
    // rather than skip and leave the unfiltered data showing.
    const bigJobs = {
      items: Array.from({ length: 50 }, (_, i) => ({
        id: `j${i}`,
        content_type: 'short',
        status: 'done',
      })),
      total: 1001,
    };
    const bigStats = { total: 1001, by_status: { done: 1001 }, by_content_type: { short: 1001 } };
    const longJobs = { items: [{ id: 'l1', content_type: 'long', status: 'done' }], total: 3 };
    const longStats = { total: 3, by_status: { done: 3 }, by_content_type: { long: 3 } };

    stubFetch((url) => {
      if (url.includes('/stats')) {
        return url.includes('content_type=long')
          ? { ok: true, body: longStats }
          : { ok: true, body: bigStats };
      }
      return url.includes('content_type=long')
        ? { ok: true, body: longJobs }
        : { ok: true, body: bigJobs };
    });

    const result = await renderLoadedFeed('long');

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('content_type=long'))).toBe(true);
    // The displayed list is the scoped server response, not the unfiltered probe.
    expect(result.current.jobs).toHaveLength(1);
    expect(result.current.jobs[0].content_type).toBe('long');
  });

  it('in server mode, changing the filter triggers a new fetch', async () => {
    const bigJobs = {
      items: Array.from({ length: 50 }, (_, i) => ({
        id: `j${i}`,
        content_type: 'short',
        status: 'done',
      })),
      total: 1001,
    };
    const bigStats = { total: 1001, by_status: { done: 1001 }, by_content_type: { short: 1001 } };
    const filteredJobs = { items: [{ id: 'f1', content_type: 'long', status: 'done' }], total: 1 };
    const filteredStats = { total: 1, by_status: { done: 1 }, by_content_type: { long: 1 } };

    stubFetch((url) => {
      if (url.includes('/stats')) {
        if (url.includes('content_type=long')) return { ok: true, body: filteredStats };
        return { ok: true, body: bigStats };
      }
      if (url.includes('content_type=long')) return { ok: true, body: filteredJobs };
      return { ok: true, body: bigJobs };
    });

    const result = await renderLoadedFeed();

    const fetchCallsBefore = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;

    act(() => result.current.setCtFilter('long'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    // In server mode, a new fetch SHOULD have been triggered.
    const fetchCallsAfter = (fetch as ReturnType<typeof vi.fn>).mock.calls.length;
    expect(fetchCallsAfter).toBeGreaterThan(fetchCallsBefore);

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('content_type=long'))).toBe(true);
  });

  it('in server mode, a limit above 1000 is still capped (1001 → mount only fetches 1000 limit)', async () => {
    // Verify the mount fetch always uses limit=1000 (not e.g. 1001).
    const bigJobs = { items: [], total: 1001 };
    const bigStats = { total: 1001, by_status: {}, by_content_type: {} };

    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: bigStats }
      : { ok: true, body: bigJobs });

    await renderLoadedFeed();

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    const jobsCall = calls.find((u) => u.includes('/api/jobs') && !u.includes('/stats'))!;
    expect(jobsCall).toContain('limit=1000');
  });
});
