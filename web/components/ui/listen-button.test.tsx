// @vitest-environment jsdom
import { act, fireEvent, render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ListenButton } from './listen-button';

class MockUtterance {
  onstart: (() => void) | null = null;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

function installSpeech() {
  const synthesis = {
    cancel: vi.fn(),
    speak: vi.fn((utterance: MockUtterance) => utterance.onstart?.()),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', MockUtterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return synthesis;
}

beforeEach(() => {
  vi.unstubAllGlobals();
  delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
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
});
