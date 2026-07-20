// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useLinksTable } from './useLinksTable';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe('useLinksTable', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('starts idle and does not fetch while disabled', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useLinksTable({ enabled: false }));

    expect(result.current.state).toBe('idle');
    expect(result.current.viewLoaded).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('cancels a pending hover without clearing committed selection', () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const { result } = renderHook(() => useLinksTable({ enabled: false }));

    act(() => {
      result.current.selectLink('committed');
      result.current.hoverLink('pending');
      result.current.cancelHover();
      vi.advanceTimersByTime(220);
    });

    expect(result.current.selectedLinkId).toBe('committed');
  });

  it('retries the view preference load after leaving Links mid-fetch', async () => {
    const firstView = deferred<Response>();
    let viewCalls = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/brain/links/view') {
        viewCalls += 1;
        if (viewCalls === 1) return firstView.promise;
        return Promise.resolve(
          new Response(JSON.stringify({ order: 'desc', size: 25 })),
        );
      }
      if (url.startsWith('/api/brain/links?')) {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], limit: 25, offset: 0, total: 0 })),
        );
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result, rerender } = renderHook(
      ({ enabled }) => useLinksTable({ enabled }),
      { initialProps: { enabled: true } },
    );

    await waitFor(() => expect(viewCalls).toBe(1));
    rerender({ enabled: false });

    await act(async () => {
      firstView.resolve(
        new Response(JSON.stringify({ order: 'desc', size: 25 })),
      );
      await firstView.promise;
    });
    expect(result.current.viewLoaded).toBe(false);
    expect(result.current.state).toBe('idle');

    rerender({ enabled: true });

    await waitFor(() => expect(viewCalls).toBe(2));
    await waitFor(() => expect(result.current.viewLoaded).toBe(true));
    await waitFor(() => expect(result.current.state).toBe('ready'));
  });

  it('starts without a preview, then fetches on navigation and caches per id', async () => {
    const previewCalls: string[] = [];
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/brain/links/view') {
        return Promise.resolve(
          new Response(JSON.stringify({ order: 'desc', size: 25 })),
        );
      }
      if (url.startsWith('/api/brain/links?')) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              items: [
                { id: 'lnk_1', url: 'https://a.example', seen_count: 1, first_seen: 't', last_seen: 't' },
                { id: 'lnk_2', url: 'https://b.example', seen_count: 1, first_seen: 't', last_seen: 't' },
              ],
              limit: 25,
              offset: 0,
              total: 2,
            }),
          ),
        );
      }
      const previewMatch = url.match(/^\/api\/brain\/links\/(.+)\/preview$/);
      if (previewMatch) {
        previewCalls.push(previewMatch[1]);
        return Promise.resolve(
          new Response(
            JSON.stringify({ id: previewMatch[1], og_image_url: null }),
          ),
        );
      }
      return Promise.reject(new Error(`Unexpected fetch: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useLinksTable({ enabled: true }));

    await waitFor(() => expect(result.current.state).toBe('ready'));
    expect(result.current.selectedLinkId).toBeNull();
    expect(result.current.previewState).toBe('idle');
    expect(previewCalls).toEqual([]);

    act(() => {
      result.current.selectAdjacent(1);
    });
    expect(result.current.selectedLinkId).toBe('lnk_1');
    await waitFor(() => expect(result.current.previewState).toBe('ready'));
    expect(previewCalls).toEqual(['lnk_1']);

    act(() => {
      result.current.selectAdjacent(1);
    });
    expect(result.current.selectedLinkId).toBe('lnk_2');
    await waitFor(() => expect(result.current.previewState).toBe('ready'));
    expect(previewCalls).toEqual(['lnk_1', 'lnk_2']);

    // Re-selecting an id already fetched this session must not re-fetch.
    act(() => {
      result.current.selectAdjacent(-1);
    });
    expect(result.current.selectedLinkId).toBe('lnk_1');
    await waitFor(() => expect(result.current.previewState).toBe('ready'));
    expect(previewCalls).toEqual(['lnk_1', 'lnk_2']);

    // Clamps at the last row instead of wrapping.
    act(() => {
      result.current.selectAdjacent(1);
    });
    act(() => {
      result.current.selectAdjacent(1);
    });
    expect(result.current.selectedLinkId).toBe('lnk_2');
  });
});
