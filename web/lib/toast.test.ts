// @vitest-environment jsdom
import { act, cleanup, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { toast, useToasts } from './toast';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('toast', () => {
  it('notifies subscribers and auto-dismisses after the timeout', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToasts());
    expect(result.current).toEqual([]);

    act(() => toast('Job deleted'));
    expect(result.current).toEqual([{ id: expect.any(Number), text: 'Job deleted', variant: 'success' }]);

    act(() => vi.advanceTimersByTime(3000));
    expect(result.current).toEqual([]);
  });

  it('defaults to the success variant and accepts error', () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useToasts());
    act(() => toast('Could not delete', 'error'));
    expect(result.current[0]).toMatchObject({ text: 'Could not delete', variant: 'error' });
  });
});
