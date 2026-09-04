// @vitest-environment jsdom
import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeech } from './useSpeech';

class MockUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

function installSpeech() {
  let current: MockUtterance | null = null;
  const synthesis = {
    cancel: vi.fn(() => {
      current?.onend?.();
      current = null;
    }),
    speak: vi.fn((utterance: MockUtterance) => {
      current = utterance;
      utterance.onstart?.();
    }),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

function installPendingSpeech() {
  let current: MockUtterance | null = null;
  const synthesis = {
    cancel: vi.fn(() => {
      current = null;
    }),
    // Does not call onstart synchronously - simulates real TTS engines where
    // speak() queues the utterance and onstart fires later (or never, if
    // canceled first).
    speak: vi.fn((utterance: MockUtterance) => {
      current = utterance;
    }),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
});

describe('useSpeech', () => {
  it('reports unsupported when speech synthesis is unavailable', () => {
    const { result } = renderHook(() => useSpeech('Hello'));
    expect(result.current.supported).toBe(false);
  });

  it('reports supported when speech synthesis is available', () => {
    installSpeech();
    const { result } = renderHook(() => useSpeech('Hello'));
    expect(result.current.supported).toBe(true);
  });

  it('cancels the queue before speaking on the first toggle', () => {
    const synthesis = installSpeech();
    const { result } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    expect(synthesis.cancel).toHaveBeenCalledOnce();
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(synthesis.cancel.mock.invocationCallOrder[0]).toBeLessThan(synthesis.speak.mock.invocationCallOrder[0]);
    expect(synthesis.speak.mock.calls[0][0].text).toBe('Hello');
    expect(result.current.speaking).toBe(true);
  });

  it('stops rather than restarting on the second toggle', () => {
    const synthesis = installSpeech();
    const { result } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(result.current.speaking).toBe(false);
  });

  it('does nothing when unsupported', () => {
    const { result } = renderHook(() => useSpeech('Hello'));
    expect(() => act(() => result.current.toggle())).not.toThrow();
    expect(result.current.speaking).toBe(false);
  });

  it('cancels speech when the owning component unmounts mid-speech', () => {
    const synthesis = installSpeech();
    const { result, unmount } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    expect(result.current.speaking).toBe(true);
    unmount();
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
  });

  it('does not call cancel on unmount when nothing is speaking', () => {
    const synthesis = installSpeech();
    const { unmount } = renderHook(() => useSpeech('Hello'));
    unmount();
    expect(synthesis.cancel).not.toHaveBeenCalled();
  });

  it('interrupts speech from another hook instance', () => {
    const synthesis = installSpeech();
    const first = renderHook(() => useSpeech('First'));
    const second = renderHook(() => useSpeech('Second'));
    act(() => first.result.current.toggle());
    act(() => second.result.current.toggle());
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
    expect(synthesis.speak).toHaveBeenCalledTimes(2);
    expect(first.result.current.speaking).toBe(false);
    expect(second.result.current.speaking).toBe(true);
  });

  it('treats a queued utterance as speaking before onstart fires', () => {
    installPendingSpeech();
    const { result } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    expect(result.current.speaking).toBe(true);
  });

  it('stops instead of restarting on a second toggle before onstart fires', () => {
    const synthesis = installPendingSpeech();
    const { result } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(result.current.speaking).toBe(false);
  });

  it('cancels a queued utterance on unmount before onstart fires', () => {
    const synthesis = installPendingSpeech();
    const { result, unmount } = renderHook(() => useSpeech('Hello'));
    act(() => result.current.toggle());
    unmount();
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
  });
});
