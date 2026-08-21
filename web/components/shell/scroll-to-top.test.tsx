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

  it('dims and disables pointer events when it overlaps an interactive element', () => {
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

    const overlapping = {
      left: 0,
      top: 0,
      right: 40,
      bottom: 40,
      width: 40,
      height: 40,
    } as DOMRect;
    const elsewhere = {
      left: 500,
      top: 500,
      right: 540,
      bottom: 540,
      width: 40,
      height: 40,
    } as DOMRect;

    button.getBoundingClientRect = vi.fn().mockReturnValue(overlapping);
    underneath.getBoundingClientRect = vi.fn().mockReturnValue(overlapping);
    fireEvent.scroll(scroller);

    expect(button.className).toContain('opacity-60');
    expect(button.className).toContain('pointer-events-none');

    underneath.getBoundingClientRect = vi.fn().mockReturnValue(elsewhere);
    fireEvent.scroll(scroller);
    expect(button.className).toContain('opacity-100');
    expect(button.className).not.toContain('pointer-events-none');
  });
});
