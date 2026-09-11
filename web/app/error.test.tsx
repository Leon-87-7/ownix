// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import AppError from './error';

describe('AppError', () => {
  it('renders the fallback and calls reset on click', () => {
    const reset = vi.fn();
    render(<AppError error={new Error('boom')} reset={reset} />);

    expect(screen.getByText(/this page didn.t load/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /try again/i }));
    expect(reset).toHaveBeenCalledOnce();
  });
});
