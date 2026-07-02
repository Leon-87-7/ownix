// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import GlobalError from './error';

describe('GlobalError', () => {
  it('renders the fallback and calls reset on click', () => {
    const reset = vi.fn();
    render(<GlobalError error={new Error('boom')} reset={reset} />);

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
