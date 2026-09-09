// @vitest-environment jsdom
import { act, cleanup, render, renderHook } from '@testing-library/react';
import { createElement, useEffect } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resetToastsForTests, toast, useToasts } from './toast';

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  resetToastsForTests();
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

  it('catches a toast fired between a subscriber mounting and its effect committing', () => {
    // Emitter is declared first, so React runs its mount effect (which
    // calls toast()) before Consumer's — reproducing a toast landing in
    // the gap between Consumer's useState(toasts) render snapshot and its
    // own subscribing effect. Without the post-subscribe resync, Consumer
    // would stay stuck on the empty snapshot it rendered with.
    function Emitter() {
      useEffect(() => {
        toast('Job deleted');
      }, []);
      return null;
    }
    function Consumer() {
      const items = useToasts();
      return createElement('div', { 'data-testid': 'toasts' }, items.map((t) => t.text).join(','));
    }

    const { getByTestId } = render(
      createElement('div', null, createElement(Emitter), createElement(Consumer)),
    );

    expect(getByTestId('toasts').textContent).toBe('Job deleted');
  });
});
