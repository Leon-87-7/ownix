import type React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { OnboardingMinigame } from './onboarding-minigame';

vi.mock('next/dynamic', () => ({
  default: () => () => <div data-testid="rive-minigame" />,
}));

vi.mock('@/app/ownix-logo.svg', () => ({
  default: (props: React.SVGProps<SVGSVGElement>) => <svg {...props} />,
}));

let observerCallback: IntersectionObserverCallback;
class MockIntersectionObserver {
  constructor(callback: IntersectionObserverCallback) {
    observerCallback = callback;
  }
  observe = vi.fn();
  disconnect = vi.fn();
}

function setReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockReturnValue({
    matches,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
}

function enterViewport() {
  act(() => {
    observerCallback([{ intersectionRatio: 0.7 } as IntersectionObserverEntry], {} as IntersectionObserver);
  });
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('IntersectionObserver', MockIntersectionObserver);
  setReducedMotion(false);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe('OnboardingMinigame', () => {
  it('degrades to the static end screen and zoo map for reduced motion', () => {
    setReducedMotion(true);
    render(<OnboardingMinigame />);

    expect(screen.queryByTestId('rive-minigame')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reusable' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Searchable' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Stored' })).toBeInTheDocument();
    expect(screen.getByText('AI pass')).toBeInTheDocument();
  });

  it('reveals each explanation when its end-screen button is clicked', () => {
    setReducedMotion(true);
    render(<OnboardingMinigame />);

    fireEvent.click(screen.getByRole('button', { name: 'Stored' }));
    expect(screen.getByText(/Google Drive as markdown/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Searchable' }));
    expect(screen.getByText(/ask your Second Brain/)).toBeInTheDocument();
    expect(screen.queryByText(/Google Drive as markdown/)).not.toBeInTheDocument();
  });

  it('renders the game canvas with the zoo map as loading poster', () => {
    render(<OnboardingMinigame />);

    expect(screen.getByTestId('rive-minigame')).toBeInTheDocument();
    expect(screen.getByText('AI pass')).toBeInTheDocument();
    expect(screen.getByLabelText(/Ownix mini-game/)).toBeInTheDocument();
  });

  it('shows the end screen via the safety timeout when the state machine stays silent', () => {
    render(<OnboardingMinigame />);
    enterViewport();

    expect(screen.queryByRole('button', { name: 'Reusable' })).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(25_000);
    });
    expect(screen.getByRole('button', { name: 'Reusable' })).toBeInTheDocument();
  });

  it('does not arm the safety timeout before the game scrolls into view', () => {
    render(<OnboardingMinigame />);

    act(() => {
      vi.advanceTimersByTime(25_000);
    });
    expect(screen.queryByRole('button', { name: 'Reusable' })).not.toBeInTheDocument();
  });
});
