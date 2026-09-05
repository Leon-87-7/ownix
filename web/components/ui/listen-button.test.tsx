// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ListenButton } from './listen-button';
import { resetAccessibilitySettingsForTests } from '@/lib/hooks/useAccessibilitySettings';

class MockUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  voice: SpeechSynthesisVoice | null = null;
  constructor(public text: string) {}
}

function installSpeech() {
  const synthesis = {
    cancel: vi.fn(),
    speak: vi.fn((utterance: MockUtterance) => utterance.onstart?.()),
    getVoices: vi.fn(() => [] as SpeechSynthesisVoice[]),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
  resetAccessibilitySettingsForTests();
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ visual_motion: true, haptic_motion: true, voice_uri: null })),
  ));
});

describe('ListenButton', () => {
  it('renders nothing when speech synthesis is unsupported', () => {
    const { container } = render(<ListenButton text="Hello" ariaLabel="Listen" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders nothing for blank text', () => {
    installSpeech();
    const { container } = render(<ListenButton text="   " ariaLabel="Listen" />);
    expect(container).toBeEmptyDOMElement();
  });

  it('speaks and changes its label to Stop', () => {
    const synthesis = installSpeech();
    render(<ListenButton text="Hello" ariaLabel="Listen to greeting" />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to greeting' }));
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Stop' })).toBeInTheDocument();
  });

  it('stops and restores its label on a second click', () => {
    const synthesis = installSpeech();
    render(<ListenButton text="Hello" ariaLabel="Listen to greeting" />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to greeting' }));
    act(() => fireEvent.click(screen.getByRole('button', { name: 'Stop' })));
    expect(synthesis.cancel).toHaveBeenCalledTimes(2);
    expect(synthesis.speak).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: 'Listen to greeting' })).toBeInTheDocument();
  });

  it('speaks with the voice named by the voiceURI prop', () => {
    const synthesis = installSpeech();
    const pickedVoice = { voiceURI: 'picked', name: 'Picked', lang: 'en-US' } as SpeechSynthesisVoice;
    synthesis.getVoices.mockReturnValue([pickedVoice]);
    render(<ListenButton text="Hello" ariaLabel="Preview voice" voiceURI="picked" />);
    fireEvent.click(screen.getByRole('button', { name: 'Preview voice' }));
    expect(synthesis.speak.mock.calls[0][0].voice).toBe(pickedVoice);
  });
});
