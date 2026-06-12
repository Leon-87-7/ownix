// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useTagList } from './useTagList';

const TAGS = [{ id: 't1', name: 'alpha', meaning: '', color: '#fff' }];

/** Stub fetch: requests with `method` get `resp`; everything else gets the tag list. */
function stubMethodFetch(method: string, resp: { ok: boolean; status: number; body?: unknown }) {
  vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
    init?.method === method
      ? ({ ok: resp.ok, status: resp.status, json: async () => resp.body ?? {} }) as Response
      : ({ ok: true, status: 200, json: async () => TAGS }) as Response));
}

afterEach(() => vi.unstubAllGlobals());

/** Render the hook and wait for the initial tag list to load. */
async function renderLoadedTags() {
  const { result } = renderHook(() => useTagList());
  await waitFor(() => expect(result.current.loading).toBe(false));
  return result;
}

describe('useTagList', () => {
  it('loads tags on mount', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const result = await renderLoadedTags();
    expect(result.current.tags).toHaveLength(1);
  });

  it('createTag throws the 409 message on name collision', async () => {
    stubMethodFetch('POST', { ok: false, status: 409, body: { detail: 'dup' } });
    const result = await renderLoadedTags();

    await expect(
      act(() => result.current.createTag({ name: 'alpha', meaning: '', color: '#fff' })),
    ).rejects.toThrow('Tag name already exists');
  });

  it('updateTag merges the server row into state', async () => {
    const updated = { id: 't1', name: 'beta', meaning: 'm', color: '#000' };
    stubMethodFetch('PUT', { ok: true, status: 200, body: updated });
    const result = await renderLoadedTags();

    await act(() => result.current.updateTag('t1', { name: 'beta', meaning: 'm', color: '#000' }));
    expect(result.current.tags[0].name).toBe('beta');
  });

  it('deleteTag removes the tag on 204', async () => {
    stubMethodFetch('DELETE', { ok: true, status: 204 });
    const result = await renderLoadedTags();

    await act(() => result.current.deleteTag('t1'));
    expect(result.current.tags).toHaveLength(0);
  });
});
