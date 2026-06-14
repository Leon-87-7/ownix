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
});
