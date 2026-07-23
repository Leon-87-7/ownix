// @vitest-environment jsdom
import { renderHook, act } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { useVisualViewport } from './useVisualViewport';

// Minimal stand-in for window.visualViewport — jsdom doesn't implement it, so
// we install a fake that records listeners and can be resized/scrolled.
interface FakeVisualViewport {
  offsetTop: number;
  height: number;
  listeners: Record<string, Set<() => void>>;
  addEventListener: (type: string, cb: () => void) => void;
  removeEventListener: (type: string, cb: () => void) => void;
  dispatch: (type: string) => void;
}

function installVisualViewport(
  offsetTop = 0,
  height = 800,
): FakeVisualViewport {
  const listeners: Record<string, Set<() => void>> = {};
  const vv: FakeVisualViewport = {
    offsetTop,
    height,
    listeners,
    addEventListener: (type, cb) => {
      (listeners[type] ??= new Set()).add(cb);
    },
    removeEventListener: (type, cb) => {
      listeners[type]?.delete(cb);
    },
    dispatch: (type) => {
      listeners[type]?.forEach((cb) => cb());
    },
  };
  Object.defineProperty(window, 'visualViewport', {
    configurable: true,
    value: vv,
  });
  return vv;
}

function removeVisualViewport() {
  Object.defineProperty(window, 'visualViewport', {
    configurable: true,
    value: undefined,
  });
}

afterEach(removeVisualViewport);

describe('useVisualViewport', () => {
  it('measures the visible-band center and height on mount when active', () => {
    installVisualViewport(0, 800);
    const { result } = renderHook(() => useVisualViewport(true));
    expect(result.current).toEqual({ centerY: 400, height: 800 });
  });

  it('accounts for the visual-viewport offset (pinch-zoom / shift)', () => {
    installVisualViewport(100, 500);
    const { result } = renderHook(() => useVisualViewport(true));
    // offsetTop + height / 2 = 100 + 250
    expect(result.current).toEqual({ centerY: 350, height: 500 });
  });

  it('updates when the keyboard shrinks the viewport (resize)', () => {
    const vv = installVisualViewport(0, 800);
    const { result } = renderHook(() => useVisualViewport(true));
    expect(result.current.height).toBe(800);
    act(() => {
      vv.height = 360;
      vv.dispatch('resize');
    });
    expect(result.current).toEqual({ centerY: 180, height: 360 });
  });

  it('updates on scroll', () => {
    const vv = installVisualViewport(0, 600);
    const { result } = renderHook(() => useVisualViewport(true));
    act(() => {
      vv.offsetTop = 40;
      vv.dispatch('scroll');
    });
    expect(result.current).toEqual({ centerY: 340, height: 600 });
  });

  it('returns the null fallback when inactive', () => {
    installVisualViewport(0, 800);
    const { result } = renderHook(() => useVisualViewport(false));
    expect(result.current).toEqual({ centerY: null, height: null });
  });

  it('resets to the null fallback when active flips to false', () => {
    installVisualViewport(0, 800);
    const { result, rerender } = renderHook(
      ({ active }) => useVisualViewport(active),
      { initialProps: { active: true } },
    );
    expect(result.current.height).toBe(800);
    rerender({ active: false });
    expect(result.current).toEqual({ centerY: null, height: null });
  });

  it('falls back to null when the VisualViewport API is unavailable', () => {
    removeVisualViewport();
    const { result } = renderHook(() => useVisualViewport(true));
    expect(result.current).toEqual({ centerY: null, height: null });
  });

  it('removes its listeners on unmount', () => {
    const vv = installVisualViewport(0, 800);
    const { unmount } = renderHook(() => useVisualViewport(true));
    expect(vv.listeners.resize?.size).toBe(1);
    expect(vv.listeners.scroll?.size).toBe(1);
    unmount();
    expect(vv.listeners.resize?.size).toBe(0);
    expect(vv.listeners.scroll?.size).toBe(0);
  });
});
