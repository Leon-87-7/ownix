// @vitest-environment jsdom
import { renderHook } from '@testing-library/react';
import { act } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useSpeechVoices, groupVoicesByLanguage } from './useSpeechVoices';

function voice(overrides: Partial<SpeechSynthesisVoice>): SpeechSynthesisVoice {
  return {
    voiceURI: 'uri',
    name: 'name',
    lang: 'en-US',
    default: false,
    localService: true,
    ...overrides,
  } as SpeechSynthesisVoice;
}

function installSynthesis(initialVoices: SpeechSynthesisVoice[]) {
  const listeners: Array<() => void> = [];
  let current = initialVoices;
  const synthesis = {
    getVoices: vi.fn(() => current),
    addEventListener: vi.fn((_event: string, fn: () => void) => listeners.push(fn)),
    removeEventListener: vi.fn(),
  };
  vi.stubGlobal('speechSynthesis', synthesis);
  return {
    synthesis,
    setVoices: (next: SpeechSynthesisVoice[]) => {
      current = next;
      listeners.forEach((fn) => fn());
    },
  };
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
});

describe('useSpeechVoices', () => {
  it('reports unsupported when speech synthesis is unavailable', () => {
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current).toEqual({ supported: false, voices: [] });
  });

  it('returns the voices already available at mount', () => {
    installSynthesis([voice({ voiceURI: 'a' }), voice({ voiceURI: 'b' })]);
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current.supported).toBe(true);
    expect(result.current.voices.map((v) => v.voiceURI)).toEqual(['a', 'b']);
  });

  it('updates when voiceschanged fires later', () => {
    const { setVoices } = installSynthesis([]);
    const { result } = renderHook(() => useSpeechVoices());
    expect(result.current.voices).toEqual([]);
    act(() => setVoices([voice({ voiceURI: 'late' })]));
    expect(result.current.voices.map((v) => v.voiceURI)).toEqual(['late']);
  });
});

describe('groupVoicesByLanguage', () => {
  it('groups voices by language tag and sorts groups and voices by label/name', () => {
    const groups = groupVoicesByLanguage([
      voice({ voiceURI: 'b', name: 'Zeta', lang: 'en-US' }),
      voice({ voiceURI: 'a', name: 'Alpha', lang: 'en-US' }),
      voice({ voiceURI: 'c', name: 'Solo', lang: 'es-ES' }),
    ]);
    expect(groups.map((g) => g.lang)).toEqual(['en-US', 'es-ES']);
    expect(groups[0].voices.map((v) => v.name)).toEqual(['Alpha', 'Zeta']);
    expect(groups[0].label.length).toBeGreaterThan(0);
  });

  it('returns an empty array for no voices', () => {
    expect(groupVoicesByLanguage([])).toEqual([]);
  });

  it('falls back to the raw tag when Intl.DisplayNames throws on a malformed lang', () => {
    // Verified: new Intl.DisplayNames(['en'], {type:'language'}).of('not-a-real-lang-tag')
    // throws RangeError rather than returning a fallback string.
    const groups = groupVoicesByLanguage([voice({ voiceURI: 'z', name: 'Zed', lang: 'not-a-real-lang-tag' })]);
    expect(groups).toEqual([{ lang: 'not-a-real-lang-tag', label: 'not-a-real-lang-tag', voices: [expect.objectContaining({ voiceURI: 'z' })] }]);
  });
});
