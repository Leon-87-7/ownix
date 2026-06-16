// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useFeedData } from './useFeedData';

const STATS = { total: 2, by_status: { done: 2 }, by_content_type: { short: 2 } };
const JOBS = { items: [{ id: 'j1' }, { id: 'j2' }], total: 2 };

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
async function renderLoadedFeed() {
  const { result } = renderHook(() => useFeedData());
  await waitFor(() => expect(result.current.loading).toBe(false));
  return result;
}

describe('useFeedData', () => {
  it('loads stats and jobs on mount', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    expect(result.current.stats).toEqual(STATS);
    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.total).toBe(2);
    expect(result.current.error).toBeNull();
  });

  it('surfaces an error when the jobs request fails', async () => {
    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: STATS }
      : { ok: false });
    const result = await renderLoadedFeed();

    expect(result.current.error).toBe('Failed to load jobs');
  });

  it('refetches with content_type param when the filter changes', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    act(() => result.current.setCtFilter('short'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('content_type=short'))).toBe(true);
  });

  it('uses the initial content type on first load', async () => {
    stubFeedOk();
    const { result } = renderHook(() => useFeedData('long'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const calls = (fetch as ReturnType<typeof vi.fn>).mock.calls.map((c) => String(c[0]));
    expect(calls.some((u) => u.includes('content_type=long'))).toBe(true);
  });

  it('scopes the stats request to content_type (but not status) for the active tab', async () => {
    stubFeedOk();
    const result = await renderLoadedFeed();

    act(() => result.current.setStFilter('done'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.setCtFilter('article'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    const statsCalls = (fetch as ReturnType<typeof vi.fn>).mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/api/jobs/stats'));

    // The latest stats request carries the active content_type…
    expect(statsCalls.at(-1)!).toContain('content_type=article');
    // …but never the status filter — cards show the full status split for the type.
    expect(statsCalls.every((u) => !u.includes('status='))).toBe(true);
  });

  it('omits content_type from the stats request for global totals when no tab is active', async () => {
    stubFeedOk();
    await renderLoadedFeed();

    const statsCalls = (fetch as ReturnType<typeof vi.fn>).mock.calls
      .map((c) => String(c[0]))
      .filter((u) => u.includes('/api/jobs/stats'));

    expect(statsCalls.every((u) => !u.includes('content_type='))).toBe(true);
  });

  // --------------------------------------------------------------------------
  // Race-guard tests (criteria 1, 2, 3, 4, 5)
  // --------------------------------------------------------------------------

  it('ignores a stale "All" response that resolves after a newer "Short" response (out-of-order race)', async () => {
    // We need manual control over the resolution order of each fetch call.
    // Strategy: use a resolvable-promise map keyed by call index.
    let callIndex = 0;
    const resolvers: Array<(value: { ok: boolean; body: unknown }) => void> = [];

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const idx = callIndex++;
      const result = await new Promise<{ ok: boolean; body: unknown }>((resolve) => {
        resolvers[idx] = resolve;
      });
      return { ok: result.ok, json: async () => result.body } as Response;
    }));

    // The hook fires the initial "All" load on mount — 2 fetches (stats + jobs),
    // indices 0 (/stats) and 1 (/api/jobs).
    const { result } = renderHook(() => useFeedData());

    // Wait until the hook has dispatched the first pair of fetches.
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(2));

    // Switch to "short" — fires a second pair: indices 2 (stats) and 3 (jobs).
    act(() => result.current.setCtFilter('short'));

    // Wait until all 4 fetches are in-flight.
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(4));

    const shortJobs = { items: [{ id: 'short-1', content_type: 'short' }], total: 1 };
    const allJobs   = { items: [{ id: 'all-1',   content_type: 'long'  }], total: 1 };
    const shortStats = { total: 1, by_status: {}, by_content_type: { short: 1 } };
    const allStats   = { total: 1, by_status: {}, by_content_type: { long: 1 } };

    // Resolve the "short" request (indices 2 & 3) FIRST.
    act(() => {
      resolvers[2]({ ok: true, body: shortStats });
      resolvers[3]({ ok: true, body: shortJobs });
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Now resolve the older "All" request (indices 0 & 1) LAST.
    act(() => {
      resolvers[0]({ ok: true, body: allStats });
      resolvers[1]({ ok: true, body: allJobs });
    });

    // Give React a tick to process.
    await act(async () => { await Promise.resolve(); });

    // The stale "All" response must NOT overwrite the "Short" result.
    expect(result.current.jobs.every((j) => j.id !== 'all-1')).toBe(true);
    // The short job should still be present.
    expect(result.current.jobs.some((j) => j.id === 'short-1')).toBe(true);
  });

  it('clears jobs when the filter changes so mismatched cards do not show during in-flight fetch', async () => {
    // First load resolves normally.
    let callIndex = 0;
    const resolvers: Array<(value: { ok: boolean; body: unknown }) => void> = [];

    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const idx = callIndex++;
      const result = await new Promise<{ ok: boolean; body: unknown }>((resolve) => {
        resolvers[idx] = resolve;
      });
      return { ok: result.ok, json: async () => result.body } as Response;
    }));

    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(2));

    const allStats = { total: 2, by_status: {}, by_content_type: { long: 2 } };
    const allJobs  = { items: [{ id: 'a1', content_type: 'long' }, { id: 'a2', content_type: 'long' }], total: 2 };

    // Resolve initial "All" load.
    act(() => {
      resolvers[0]({ ok: true, body: allStats });
      resolvers[1]({ ok: true, body: allJobs });
    });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.jobs).toHaveLength(2);

    // Switch to "short" — do NOT resolve the new fetch yet.
    act(() => result.current.setCtFilter('short'));

    // Immediately after filter change, jobs should be cleared (not showing stale "All" cards).
    await waitFor(() => expect(result.current.jobs).toHaveLength(0));
  });

  it('drops items whose content_type does not match the active filter (defensive guard)', async () => {
    // Server returns a mixed list even though filter is "short" (defensive scenario).
    const mixedJobs = {
      items: [
        { id: 's1', content_type: 'short' },
        { id: 'l1', content_type: 'long' },   // should be dropped
        { id: 's2', content_type: 'short' },
      ],
      total: 3,
    };
    const shortStats = { total: 3, by_status: {}, by_content_type: { short: 3 } };

    stubFetch((url) => url.includes('/stats')
      ? { ok: true, body: shortStats }
      : { ok: true, body: mixedJobs });

    const { result } = renderHook(() => useFeedData('short'));
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Only the 2 short items should be exposed; the 'long' item is dropped.
    expect(result.current.jobs).toHaveLength(2);
    expect(result.current.jobs.every((j) => j.content_type === 'short')).toBe(true);
    // total reflects the SERVER-reported count, not the client-filtered list length.
    expect(result.current.total).toBe(3);
  });

  it('does not strand loading=true when a background reload() fires while a load() is in flight', async () => {
    // Regression: load and reload share reqIdRef for data-staleness, but the
    // loading flag must be keyed off a load-only counter. Otherwise a reload
    // bumping reqIdRef mid-load makes load's finally skip setLoading(false).
    let callIndex = 0;
    const resolvers: Array<(value: { ok: boolean; body: unknown }) => void> = [];

    vi.stubGlobal('fetch', vi.fn(async () => {
      const idx = callIndex++;
      const result = await new Promise<{ ok: boolean; body: unknown }>((resolve) => {
        resolvers[idx] = resolve;
      });
      return { ok: result.ok, json: async () => result.body } as Response;
    }));

    const stats = { total: 1, by_status: {}, by_content_type: { short: 1 } };
    const jobs = { items: [{ id: 's1', content_type: 'short' }], total: 1 };

    // Initial mount load: fetches 0 (stats) + 1 (jobs).
    const { result } = renderHook(() => useFeedData());
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(2));
    act(() => {
      resolvers[0]({ ok: true, body: stats });
      resolvers[1]({ ok: true, body: jobs });
    });
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Filter change → second load (fetches 2 + 3), loading goes true.
    act(() => result.current.setCtFilter('short'));
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(4));
    expect(result.current.loading).toBe(true);

    // Background reload() fires while that load is still in flight (fetches 4 + 5).
    // This bumps the shared reqIdRef, superseding the in-flight load's data.
    act(() => { void result.current.reload(); });
    await waitFor(() => expect(resolvers.length).toBeGreaterThanOrEqual(6));

    // Resolve the LOAD (2 + 3). Its data is discarded (reload superseded reqIdRef),
    // but its finally must still clear loading via the load-only counter.
    act(() => {
      resolvers[2]({ ok: true, body: stats });
      resolvers[3]({ ok: true, body: jobs });
    });

    // loading must end up false — not stranded at true.
    await waitFor(() => expect(result.current.loading).toBe(false));

    // Clean up the still-pending reload fetches.
    act(() => {
      resolvers[4]({ ok: true, body: stats });
      resolvers[5]({ ok: true, body: jobs });
    });
  });
});
