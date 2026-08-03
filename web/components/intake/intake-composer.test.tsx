// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { IntakeComposer } from './intake-composer';

describe('IntakeComposer', () => {
  it('clears the textarea after a successful submit', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(true);
    render(<IntakeComposer onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText(/intake composer/i);
    await user.type(textarea, 'https://example.com/a');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith('https://example.com/a'));
    await waitFor(() => expect(textarea).toHaveValue(''));
  });

  it('keeps the typed text when the submit fails, so the user does not retype it', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(false);
    render(<IntakeComposer onSubmit={onSubmit} />);

    const textarea = screen.getByLabelText(/intake composer/i);
    await user.type(textarea, 'https://example.com/b');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(textarea).toHaveValue('https://example.com/b');
  });

  it('prefills from initialValue (issue #476 share-target prefill)', () => {
    render(
      <IntakeComposer
        onSubmit={vi.fn()}
        initialValue="https://example.com/shared"
      />,
    );
    expect(screen.getByLabelText(/intake composer/i)).toHaveValue(
      'https://example.com/shared',
    );
  });

  it('disables the send button while empty or submitting', async () => {
    const user = userEvent.setup();
    let resolveSubmit: (v: boolean) => void;
    const onSubmit = vi.fn(
      () => new Promise<boolean>((resolve) => { resolveSubmit = resolve; }),
    );
    render(<IntakeComposer onSubmit={onSubmit} />);

    const button = screen.getByRole('button', { name: /send/i });
    expect(button).toBeDisabled();

    await user.type(screen.getByLabelText(/intake composer/i), 'hello');
    expect(button).toBeEnabled();

    await user.click(button);
    expect(button).toBeDisabled();
    resolveSubmit!(true);
  });
});
