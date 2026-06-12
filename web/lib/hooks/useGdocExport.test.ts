// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useGdocExport } from './useGdocExport';

afterEach(() => vi.unstubAllGlobals());

describe('useGdocExport', () => {
  it('stores the result url on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ url: 'https://docs.google.com/d/1' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.resultUrl).toBe('https://docs.google.com/d/1');
  });

  it('maps drive_not_configured to a friendly error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, json: async () => ({ error: 'drive_not_configured' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toContain('Google Drive is not configured');
  });

  it('surfaces the server detail on other failures', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, json: async () => ({ detail: 'boom' }) }) as Response));

    const { result } = renderHook(() => useGdocExport('s1'));
    act(() => { void result.current.trigger(); });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error).toBe('boom');
  });
});
