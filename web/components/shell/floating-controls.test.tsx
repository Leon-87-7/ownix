import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { FloatingControls } from './floating-controls';

vi.mock('./view-as-switch', () => ({
  default: () => <button type="button">View as member</button>,
}));
vi.mock('./scroll-to-top', () => ({
  ScrollToTop: () => <button type="button">Scroll to top</button>,
}));

describe('FloatingControls', () => {
  it('stacks the view-as control above the scroll-to-top control', () => {
    const { container } = render(<FloatingControls />);
    const stack = container.firstElementChild;
    const viewAs = screen.getByRole('button', { name: 'View as member' });
    const scrollToTop = screen.getByRole('button', { name: 'Scroll to top' });

    expect(stack).toHaveClass('fixed', 'bottom-6', 'right-6', 'flex-col', 'gap-2');
    expect(
      viewAs.compareDocumentPosition(scrollToTop) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
