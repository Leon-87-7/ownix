// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
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

describe('IntakeComposer — command palette (#484)', () => {
  const commands = [
    { name: '/help', args: '', summary: 'this message', usage: '/help' },
    { name: '/cancel', args: '', summary: 'cancel the current pending prompt', usage: '/cancel' },
  ];

  beforeEach(() => {
    vi.spyOn(global, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/intake/commands')) {
        return new Response(JSON.stringify({ commands }), {
          headers: { 'Content-Type': 'application/json' },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });
  });

  it('opens on a leading slash and filters as you type', async () => {
    const user = userEvent.setup();
    render(<IntakeComposer onSubmit={vi.fn().mockResolvedValue(true)} />);

    const composer = screen.getByLabelText(/intake composer/i);
    await user.type(composer, '/');
    await waitFor(() => expect(screen.getByRole('listbox')).toBeInTheDocument());
    expect(screen.getAllByRole('option')).toHaveLength(2);

    await user.type(composer, 'ca');
    await waitFor(() => expect(screen.getAllByRole('option')).toHaveLength(1));
    expect(screen.getByRole('option')).toHaveTextContent('/cancel');
  });

  it('does not open for a slash inside a pasted URL', async () => {
    const user = userEvent.setup();
    render(<IntakeComposer onSubmit={vi.fn().mockResolvedValue(true)} />);

    await user.type(screen.getByLabelText(/intake composer/i), 'https://youtube.com/shorts/abc');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('completes with Enter instead of submitting a half-typed command', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(true);
    render(<IntakeComposer onSubmit={onSubmit} />);

    const composer = screen.getByLabelText(/intake composer/i);
    await user.type(composer, '/ca');
    await waitFor(() => expect(screen.getByRole('listbox')).toBeInTheDocument());
    await user.keyboard('{Enter}');

    expect(onSubmit).not.toHaveBeenCalled();
    expect(composer).toHaveValue('/cancel ');
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });

  it('is navigable by arrow keys', async () => {
    const user = userEvent.setup();
    render(<IntakeComposer onSubmit={vi.fn().mockResolvedValue(true)} />);

    const composer = screen.getByLabelText(/intake composer/i);
    await user.type(composer, '/');
    await waitFor(() => expect(screen.getByRole('listbox')).toBeInTheDocument());
    await user.keyboard('{ArrowDown}{Enter}');

    expect(composer).toHaveValue('/cancel ');
  });

  it('closes on Escape', async () => {
    const user = userEvent.setup();
    render(<IntakeComposer onSubmit={vi.fn().mockResolvedValue(true)} />);

    const composer = screen.getByLabelText(/intake composer/i);
    await user.type(composer, '/');
    await waitFor(() => expect(screen.getByRole('listbox')).toBeInTheDocument());
    await user.keyboard('{Escape}');

    expect(screen.queryByRole('listbox')).not.toBeInTheDocument();
  });
});
