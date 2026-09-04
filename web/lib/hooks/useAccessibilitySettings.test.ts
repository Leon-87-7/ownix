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

  it('includes voice_uri in the fallback shape before any load or save', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null })),
    ));
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    expect(result.current).toEqual({
      visual_motion: true,
      haptic_motion: true,
      voice_uri: null,
      loaded: false,
    });
  });

  it('round-trips a saved voice_uri', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: 'Daniel' })),
    ));
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    expect(result.current.voice_uri).toBe('Daniel');
  });

  it('saveAccessibilitySetting sends and accepts a string value for voice_uri', async () => {
    // Regression guard: once 'voice_uri' joined keyof AccessibilitySettings,
    // a value param hardcoded to `boolean` would let
    // saveAccessibilitySetting('voice_uri', true) type-check and corrupt the
    // field — this only compiles at all once the signature is generic. Also
    // asserts the actual PUT body, not just the round-tripped response, so a
    // silently-dropped or coerced field would be caught here.
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: 'Daniel' })),
    ));
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(result.current.loaded).toBe(true));
    await act(async () => {
      await settingsModule.saveAccessibilitySetting('voice_uri', 'Daniel');
    });
    expect(result.current.voice_uri).toBe('Daniel');
    const putCall = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(JSON.parse(putCall![1].body as string)).toMatchObject({ voice_uri: 'Daniel' });
  });

  it('ignores an older overlapping save response', async () => {
    const first = deferredResponse();
    const second = deferredResponse();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
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
        voice_uri: null,
      })));
      await newer;
      first.resolve(new Response(JSON.stringify({
        visual_motion: false,
        haptic_motion: true,
        voice_uri: null,
      })));
      await older;
    });

    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: false,
      voice_uri: null,
      loaded: true,
    });
  });

  it('does not let a slow initial load overwrite a save that completed first', async () => {
    const load = deferredResponse();
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(load.promise)
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ visual_motion: false, haptic_motion: true, voice_uri: null }),
        ),
      );
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await act(async () => {
      await settingsModule.saveAccessibilitySetting('visual_motion', false);
    });
    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: true,
      voice_uri: null,
      loaded: true,
    });

    await act(async () => {
      load.resolve(
        new Response(
          JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null }),
        ),
      );
      await load.promise;
    });

    expect(result.current).toEqual({
      visual_motion: false,
      haptic_motion: true,
      voice_uri: null,
      loaded: true,
    });
  });

  it('an external write invalidates a slower in-flight load so it cannot overwrite a fresher value', async () => {
    const load = deferredResponse();
    const fetchMock = vi.fn().mockReturnValueOnce(load.promise);
    vi.stubGlobal('fetch', fetchMock);
    const settingsModule = await import('./useAccessibilitySettings');
    const { result } = renderHook(() => settingsModule.useAccessibilitySettings());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    // Simulates AccessibilitySection's own GET/PUT cycle publishing a value
    // it obtained independently, while the shared load() above is still
    // in flight.
    act(() => {
      settingsModule.publishAccessibilitySettingsFromExternalWrite({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: 'Daniel',
      });
    });
    expect(result.current.voice_uri).toBe('Daniel');

    await act(async () => {
      load.resolve(new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
      })));
      await load.promise;
    });

    // The stale load() response must not have clobbered the external write.
    expect(result.current.voice_uri).toBe('Daniel');
  });
});
