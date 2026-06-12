// @vitest-environment jsdom
import { renderHook, waitFor, act } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { useSemanticSearch } from './useSemanticSearch';

afterEach(() => vi.unstubAllGlobals());

const RESULTS = [
  { title: 'Video 1', url: 'https://example.com/1', topic: 'AI', score: 0.95 },
  { title: 'Video 2', url: 'https://example.com/2', topic: 'ML', score: 0.88 },
];

describe('useSemanticSearch', () => {
  it('starts in idle state', () => {
    const { result } = renderHook(() => useSemanticSearch());
    expect(result.current.searchState).toBe('idle');
    expect(result.current.results).toHaveLength(0);
    expect(result.current.query).toBe('');
  });

  it('transitions through loading → results on success', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => RESULTS }) as Response));

    const { result } = renderHook(() => useSemanticSearch());

    act(() => { result.current.setQuery('machine learning'); });
    act(() => { void result.current.runSearch(); });

    await waitFor(() => expect(result.current.searchState).toBe('results'));
    expect(result.current.results).toHaveLength(2);
    expect(result.current.results[0].title).toBe('Video 1');
  });

  it('sets empty state when server returns empty array', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => [] }) as Response));

    const { result } = renderHook(() => useSemanticSearch());

    act(() => { result.current.setQuery('obscure query'); });
    act(() => { void result.current.runSearch(); });

    await waitFor(() => expect(result.current.searchState).toBe('empty'));
    expect(result.current.results).toHaveLength(0);
  });

  it('sets error state on HTTP failure with detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 500, json: async () => ({ detail: 'Internal error' }) }) as Response));

    const { result } = renderHook(() => useSemanticSearch());

    act(() => { result.current.setQuery('test'); });
    act(() => { void result.current.runSearch(); });

    await waitFor(() => expect(result.current.searchState).toBe('error'));
    expect(result.current.errorMessage).toBe('Internal error');
  });

  it('sets error state on HTTP failure without detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, status: 503, json: async () => ({}) }) as Response));

    const { result } = renderHook(() => useSemanticSearch());

    act(() => { result.current.setQuery('test'); });
    act(() => { void result.current.runSearch(); });

    await waitFor(() => expect(result.current.searchState).toBe('error'));
    expect(result.current.errorMessage).toContain('503');
  });

  it('sets error state on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('Network error'); }));

    const { result } = renderHook(() => useSemanticSearch());

    act(() => { result.current.setQuery('test'); });
    act(() => { void result.current.runSearch(); });

    await waitFor(() => expect(result.current.searchState).toBe('error'));
    expect(result.current.errorMessage).toBe('Network error');
  });
});
