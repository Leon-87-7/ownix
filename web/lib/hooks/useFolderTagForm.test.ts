// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { useFolderTagForm } from './useFolderTagForm';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
});
afterAll(() => server.close());

function topicsHandler(topics: { topic: string; link_ids: string[]; count: number }[]) {
  return http.get('/api/jobs/:jobId/link-topics', () => HttpResponse.json(topics));
}

describe('useFolderTagForm', () => {
  it('loads topics, all checked by default, with distinct pre-assigned colors', async () => {
    server.use(
      topicsHandler([
        { topic: 'rust', link_ids: ['l1'], count: 1 },
        { topic: 'screeners', link_ids: ['l2', 'l3'], count: 2 },
      ]),
    );

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });

    expect(result.current.assignments).toHaveLength(2);
    expect(result.current.assignments.every((a) => a.checked)).toBe(true);
    expect(result.current.assignments.map((a) => a.topic)).toEqual(['rust', 'screeners']);
    const { PRESET_COLORS } = await import('@/components/ui/tag-picker');
    for (const a of result.current.assignments) {
      expect(PRESET_COLORS).toContain(a.color);
    }
    expect(new Set(result.current.assignments.map((a) => a.color)).size).toBe(2);
  });

  it('toggle flips only the targeted folder', async () => {
    server.use(
      topicsHandler([
        { topic: 'rust', link_ids: ['l1'], count: 1 },
        { topic: 'screeners', link_ids: ['l2'], count: 1 },
      ]),
    );

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
    server.use(
      topicsHandler([{ topic: 'rust', link_ids: ['l1', 'l2'], count: 2 }]),
      http.post('/api/controls/tags', async ({ request }) => {
        calls.push({
          url: new URL(request.url).pathname,
          method: request.method,
          body: await request.json(),
        });
        return HttpResponse.json({ id: 'tag-1' }, { status: 201 });
      }),
      http.post('/api/brain/links/:linkId/tags/:tagId', ({ request }) => {
        calls.push({ url: new URL(request.url).pathname, method: request.method });
        return new HttpResponse(null, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    await act(async () => {
      await result.current.confirm();
    });

    expect(calls.find((c) => c.url === '/api/controls/tags')?.body).toMatchObject({
      name: 'rust',
    });
    expect(calls.filter((c) => c.url.includes('/tags/tag-1')).map((c) => c.url).sort()).toEqual(
      ['/api/brain/links/l1/tags/tag-1', '/api/brain/links/l2/tags/tag-1'].sort(),
    );
  });

  it('confirm skips unchecked folders', async () => {
    const calls: string[] = [];
    server.use(
      topicsHandler([{ topic: 'rust', link_ids: ['l1'], count: 1 }]),
      http.post('/api/controls/tags', ({ request }) => {
        calls.push(`${request.method} ${new URL(request.url).pathname}`);
        return HttpResponse.json({ id: 'tag-1' }, { status: 201 });
      }),
    );

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

    expect(calls).toEqual([]);
  });

  it('confirm reuses an existing tag on a 409 name collision instead of failing', async () => {
    const calls: string[] = [];
    server.use(
      topicsHandler([{ topic: 'rust', link_ids: ['l1'], count: 1 }]),
      http.post('/api/controls/tags', ({ request }) => {
        calls.push(`${request.method} ${new URL(request.url).pathname}`);
        return HttpResponse.json({ detail: 'exists' }, { status: 409 });
      }),
      http.get('/api/controls/tags', ({ request }) => {
        calls.push(`${request.method} ${new URL(request.url).pathname}`);
        return HttpResponse.json([{ id: 'existing-tag', name: 'rust' }]);
      }),
      http.post('/api/brain/links/:linkId/tags/:tagId', ({ request }) => {
        calls.push(`${request.method} ${new URL(request.url).pathname}`);
        return new HttpResponse(null, { status: 201 });
      }),
    );

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
    server.use(
      topicsHandler([{ topic: 'a'.repeat(90), link_ids: ['l1'], count: 1 }]),
      http.post('/api/controls/tags', () =>
        HttpResponse.json({ detail: 'too long' }, { status: 422 }),
      ),
    );

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

  it('surfaces a folder whose tag attachment failed', async () => {
    server.use(
      topicsHandler([{ topic: 'rust', link_ids: ['l1'], count: 1 }]),
      http.post('/api/controls/tags', () => HttpResponse.json({ id: 'tag-1' }, { status: 201 })),
      http.post('/api/brain/links/:linkId/tags/:tagId', () =>
        HttpResponse.json({ detail: 'boom' }, { status: 500 }),
      ),
    );

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });
    let ok = true;
    await act(async () => {
      ok = await result.current.confirm();
    });

    expect(ok).toBe(false);
    expect(result.current.error).toContain('rust');
  });

  it('dismissing (never calling confirm) issues no writes', async () => {
    const calls: string[] = [];
    server.use(
      topicsHandler([{ topic: 'rust', link_ids: ['l1'], count: 1 }]),
      http.post('/api/controls/tags', ({ request }) => {
        calls.push(`${request.method} ${new URL(request.url).pathname}`);
        return HttpResponse.json({ id: 'tag-1' }, { status: 201 });
      }),
    );

    const { result } = renderHook(() => useFolderTagForm('job1'));
    await act(async () => {
      await result.current.load();
    });

    expect(calls).toEqual([]);
  });
});
