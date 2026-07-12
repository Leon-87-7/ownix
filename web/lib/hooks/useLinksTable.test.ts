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

  it('retries the view preference load after leaving Links mid-fetch', async () => {
    const firstView = deferred<Response>();
    let viewCalls = 0;
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/brain/links/view') {
        viewCalls += 1;
        if (viewCalls === 1) return firstView.promise;
        return Promise.resolve(
          new Response(JSON.stringify({ sort: 'last_seen', order: 'desc', size: 25 })),
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
        new Response(JSON.stringify({ sort: 'last_seen', order: 'desc', size: 25 })),
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
});
