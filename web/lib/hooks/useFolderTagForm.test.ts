// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useFolderTagForm } from './useFolderTagForm';

describe('useFolderTagForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function mockTopics(topics: { topic: string; link_ids: string[]; count: number }[]) {
    return vi.fn(async (url: string, init?: RequestInit) => {
      if (typeof url === 'string' && url.endsWith('/link-topics')) {
        return { ok: true, json: async () => topics } as Response;
      }
      throw new Error(`unexpected fetch: ${url} ${init?.method ?? 'GET'}`);
    });
  }

  it('loads topics, all checked by default, with distinct pre-assigned colors', async () => {
    const fetchMock = mockTopics([
      { topic: 'rust', link_ids: ['l1'], count: 1 },
      { topic: 'screeners', link_ids: ['l2', 'l3'], count: 2 },
    ]);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });

    expect(result.current.assignments).toHaveLength(2);
    expect(result.current.assignments.every((a) => a.checked)).toBe(true);
    expect(result.current.assignments.map((a) => a.topic)).toEqual(['rust', 'screeners']);
    // Colors come only from the shared palette.
    const { PRESET_COLORS } = await import('@/components/ui/tag-picker');
    for (const a of result.current.assignments) {
      expect(PRESET_COLORS).toContain(a.color);
    }
  });

  it('toggle flips only the targeted folder', async () => {
    const fetchMock = mockTopics([
      { topic: 'rust', link_ids: ['l1'], count: 1 },
      { topic: 'screeners', link_ids: ['l2'], count: 1 },
    ]);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    act(() => {
      result.current.toggle('rust');
    });

    expect(result.current.assignments.find((a) => a.topic === 'rust')?.checked).toBe(false);
    expect(result.current.assignments.find((a) => a.topic === 'screeners')?.checked).toBe(true);
  });

  it('confirm creates a tag per checked folder and attaches it to every link', async () => {
    const calls: { url: string; method: string; body?: unknown }[] = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      calls.push({
        url,
        method,
        body: init?.body ? JSON.parse(init.body as string) : undefined,
      });
      if (url.endsWith('/link-topics')) {
        return {
          ok: true,
          json: async () => [{ topic: 'rust', link_ids: ['l1', 'l2'], count: 2 }],
        } as Response;
      }
      if (url === '/api/controls/tags' && method === 'POST') {
        return { ok: true, json: async () => ({ id: 'tag-1' }) } as Response;
      }
      if (url.includes('/tags/tag-1') && method === 'POST') {
        return { ok: true, json: async () => ({}) } as Response;
      }
      throw new Error(`unexpected fetch: ${url} ${method}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.confirm();
    });

    const attachCalls = calls.filter((c) => c.url.includes('/tags/tag-1'));
    expect(attachCalls.map((c) => c.url).sort()).toEqual(
      ['/api/brain/links/l1/tags/tag-1', '/api/brain/links/l2/tags/tag-1'].sort(),
    );
  });

  it('confirm skips unchecked folders', async () => {
    const calls: string[] = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? 'GET'} ${url}`);
      if (url.endsWith('/link-topics')) {
        return {
          ok: true,
          json: async () => [{ topic: 'rust', link_ids: ['l1'], count: 1 }],
        } as Response;
      }
      return { ok: true, json: async () => ({ id: 'tag-1' }) } as Response;
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    act(() => {
      result.current.toggle('rust');
    });
    await act(async () => {
      await result.current.confirm();
    });

    expect(calls.some((c) => c.includes('/api/controls/tags'))).toBe(false);
  });

  it('confirm reuses an existing tag on a 409 name collision instead of failing', async () => {
    const calls: string[] = [];
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      calls.push(`${method} ${url}`);
      if (url.endsWith('/link-topics')) {
        return {
          ok: true,
          json: async () => [{ topic: 'rust', link_ids: ['l1'], count: 1 }],
        } as Response;
      }
      if (url === '/api/controls/tags' && method === 'POST') {
        return { ok: false, status: 409, json: async () => ({ detail: 'exists' }) } as Response;
      }
      if (url === '/api/controls/tags' && method === 'GET') {
        return {
          ok: true,
          json: async () => [{ id: 'existing-tag', name: 'rust' }],
        } as Response;
      }
      if (url.includes('/tags/existing-tag')) {
        return { ok: true, json: async () => ({}) } as Response;
      }
      throw new Error(`unexpected fetch: ${url} ${method}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.confirm();
    });

    expect(calls).toContain('POST /api/brain/links/l1/tags/existing-tag');
  });

  it('surfaces (never silently drops) a folder whose tag creation failed', async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? 'GET';
      if (url.endsWith('/link-topics')) {
        return {
          ok: true,
          json: async () => [{ topic: 'a'.repeat(90), link_ids: ['l1'], count: 1 }],
        } as Response;
      }
      if (url === '/api/controls/tags' && method === 'POST') {
        // The backend's 80-char tag-name limit — a 422, not a 409.
        return { ok: false, status: 422, json: async () => ({ detail: 'too long' }) } as Response;
      }
      throw new Error(`unexpected fetch: ${url} ${method}`);
    });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    let ok = true;
    await act(async () => {
      ok = await result.current.confirm();
    });

    expect(ok).toBe(false);
    expect(result.current.error).toContain('a'.repeat(90));
  });

  it('dismissing (never calling confirm) issues no writes', async () => {
    const fetchMock = mockTopics([{ topic: 'rust', link_ids: ['l1'], count: 1 }]);
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });

    expect(fetchMock).toHaveBeenCalledTimes(1); // only the GET
  });
});
