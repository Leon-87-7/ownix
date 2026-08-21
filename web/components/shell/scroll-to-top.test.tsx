// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScrollToTop } from './scroll-to-top';

describe('ScrollToTop', () => {
  it('listens to the dashboard scroll region and scrolls it back to top', () => {
    const scrollTo = vi.fn();
    const { container } = render(
      <div>
        <main />
        <div data-dashboard-scroll>
          <ScrollToTop />
        </div>
      </div>,
    );
    const scroller = container.querySelector<HTMLElement>(
      '[data-dashboard-scroll]',
    );
    if (!scroller) throw new Error('Missing dashboard scroller');
    Object.defineProperty(scroller, 'scrollTo', { value: scrollTo });

    Object.defineProperty(scroller, 'scrollTop', {
      value: 240,
      configurable: true,
    });
    fireEvent.scroll(scroller);

    const button = screen.getByRole('button', { name: /scroll to top/i });
    expect(button).toHaveAttribute('aria-hidden', 'false');

    fireEvent.click(button);

    expect(scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
  });

  it('dims and disables pointer events when it blocks an interactive element beneath it', () => {
    const { container } = render(
      <div>
        <main />
        <div data-dashboard-scroll>
          <ScrollToTop />
          <button>underneath</button>
        </div>
      </div>,
    );
    const scroller = container.querySelector<HTMLElement>(
      '[data-dashboard-scroll]',
    );
    if (!scroller) throw new Error('Missing dashboard scroller');
    Object.defineProperty(scroller, 'scrollTop', {
      value: 240,
      configurable: true,
    });
    fireEvent.scroll(scroller);

    const button = screen.getByRole('button', { name: /scroll to top/i });
    const underneath = screen.getByText('underneath');

    // The button is genuinely on top (elementFromPoint returns it while
    // visible); hiding it via pointerEvents reveals the button beneath.
    document.elementFromPoint = vi.fn(() =>
      button.style.pointerEvents === 'none' ? underneath : button,
    );
    fireEvent.scroll(scroller);

    expect(button.className).toContain('opacity-60');
    expect(button.className).toContain('pointer-events-none');
  });

  it('stays clickable when a higher-stacked element already covers it', () => {
    const { container } = render(
      <div>
        <main />
        <div data-dashboard-scroll>
          <ScrollToTop />
          <a href="/other" className="fixed z-50">
            above
          </a>
        </div>
      </div>,
    );
    const scroller = container.querySelector<HTMLElement>(
      '[data-dashboard-scroll]',
    );
    if (!scroller) throw new Error('Missing dashboard scroller');
    Object.defineProperty(scroller, 'scrollTop', {
      value: 240,
      configurable: true,
    });

    const above = screen.getByText('above');
    // A higher z-index element already renders on top everywhere the button
    // sits — elementFromPoint never returns the button itself.
    document.elementFromPoint = vi.fn(() => above);
    fireEvent.scroll(scroller);

    const button = screen.getByRole('button', { name: /scroll to top/i });
    expect(button.className).toContain('opacity-100');
    expect(button.className).not.toContain('pointer-events-none');
  });
});
