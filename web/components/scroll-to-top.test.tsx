// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ScrollToTop } from '@/components/shell/scroll-to-top';

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

    const button = screen.getByRole('button', {
      name: /scroll to top/i,
    });
    expect(button).toHaveAttribute('aria-hidden', 'false');

    fireEvent.click(button);

    expect(scrollTo).toHaveBeenCalledWith({
      top: 0,
      behavior: 'smooth',
    });
  });
});
