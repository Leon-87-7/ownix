// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function deferredResponse() {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((done) => { resolve = done; });
  return { promise, resolve };
}

describe('accessibility settings', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal('matchMedia', vi.fn(() => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })));
  });

  it('ignores an older overlapping save response', async () => {
    const first = deferredResponse();
    const second = deferredResponse();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
      })))
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise);
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await act(async () => { await Promise.resolve(); });

    let older!: Promise<void>;
    let newer!: Promise<void>;
    await act(async () => {
      older = settingsModule.saveAccessibilitySetting('visual_motion', false);
      newer = settingsModule.saveAccessibilitySetting('haptic_motion', false);
      second.resolve(new Response(JSON.stringify({
        visual_motion: false,
        haptic_motion: false,
      })));
      await newer;
      first.resolve(new Response(JSON.stringify({
        visual_motion: false,
        haptic_motion: true,
      })));
      await older;
    });

    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: false,
    });
  });
});
