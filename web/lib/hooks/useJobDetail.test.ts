// @vitest-environment jsdom
import { renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useJobDetail } from './useJobDetail';

afterEach(() => vi.unstubAllGlobals());

describe('useJobDetail', () => {
  it('returns the job and ok state on 200', async () => {
    const job = { id: 'j1', url: 'https://x', status: 'done' };
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, status: 200, json: async () => job }) as Response));

    const { result } = renderHook(() => useJobDetail('j1'));
    await waitFor(() => expect(result.current.fetchState).toBe('ok'));
    expect(result.current.job).toMatchObject({ id: 'j1' });
  });

  it.each([
    [404, 'not_found'],
    [403, 'forbidden'],
    [500, 'error'],
  ])('maps HTTP %i to fetchState %s', async (status, expected) => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useJobDetail('j1'));
    await waitFor(() => expect(result.current.fetchState).toBe(expected));
    expect(result.current.job).toBeNull();
  });
});
