// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useTagList } from './useTagList';

const TAGS = [{ id: 't1', name: 'alpha', meaning: '', color: '#fff' }];

afterEach(() => vi.unstubAllGlobals());

describe('useTagList', () => {
  it('loads tags on mount', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.tags).toHaveLength(1);
  });

  it('createTag throws the 409 message on name collision', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'POST'
        ? ({ ok: false, status: 409, json: async () => ({ detail: 'dup' }) }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await expect(
      act(() => result.current.createTag({ name: 'alpha', meaning: '', color: '#fff' })),
    ).rejects.toThrow('Tag name already exists');
  });

  it('updateTag merges the server row into state', async () => {
    const updated = { id: 't1', name: 'beta', meaning: 'm', color: '#000' };
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'PUT'
        ? ({ ok: true, status: 200, json: async () => updated }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.updateTag('t1', { name: 'beta', meaning: 'm', color: '#000' }));
    expect(result.current.tags[0].name).toBe('beta');
  });

  it('deleteTag removes the tag on 204', async () => {
    vi.stubGlobal('fetch', vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
      init?.method === 'DELETE'
        ? ({ ok: true, status: 204, json: async () => ({}) }) as Response
        : ({ ok: true, status: 200, json: async () => TAGS }) as Response));

    const { result } = renderHook(() => useTagList());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(() => result.current.deleteTag('t1'));
    expect(result.current.tags).toHaveLength(0);
  });
});
