// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { SubmitJobProvider, useSubmitJob } from './submit-job';

function ShortcutProbe() {
  const { open } = useSubmitJob();
  return <span>{open ? 'submit open' : 'submit closed'}</span>;
}

function LastAcceptedProbe() {
  const { lastAccepted } = useSubmitJob();
  return <span>{lastAccepted?.content_type ?? 'no accepted job'}</span>;
}

function OpenSubmitButton() {
  const { setOpen } = useSubmitJob();
  return (
    <button type="button" onClick={() => setOpen(true)}>
      Open submit
    </button>
  );
}

describe('SubmitJobProvider', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('opens Submit URL with the N shortcut', () => {
    render(
      <SubmitJobProvider>
        <ShortcutProbe />
      </SubmitJobProvider>,
    );

    expect(screen.getByText('submit closed')).toBeTruthy();

    fireEvent.keyDown(window, { key: 'n' });

    expect(screen.getByText('submit open')).toBeTruthy();
  });

  it('does not open Submit URL while typing in a field', () => {
    render(
      <SubmitJobProvider>
        <input aria-label="Notes" />
        <ShortcutProbe />
      </SubmitJobProvider>,
    );

    const notes = screen.getByLabelText('Notes');
    notes.focus();
    fireEvent.keyDown(notes, { key: 'n' });

    expect(screen.getByText('submit closed')).toBeTruthy();
  });

  it('does not open Submit URL while focus is inside another dialog', () => {
    render(
      <SubmitJobProvider>
        <div role="dialog">
          <button type="button">Dialog action</button>
        </div>
        <ShortcutProbe />
      </SubmitJobProvider>,
    );

    const action = screen.getByRole('button', { name: 'Dialog action' });
    action.focus();
    fireEvent.keyDown(action, { key: 'n' });

    expect(screen.getByText('submit closed')).toBeTruthy();
  });

  it('does not open Submit URL while another dialog is visible and focus is outside it', () => {
    render(
      <SubmitJobProvider>
        <button type="button">Outside opener</button>
        <div role="dialog">
          <button type="button">Dialog action</button>
        </div>
        <ShortcutProbe />
      </SubmitJobProvider>,
    );

    const opener = screen.getByRole('button', { name: 'Outside opener' });
    opener.focus();
    fireEvent.keyDown(opener, { key: 'n' });

    expect(screen.getByText('submit closed')).toBeTruthy();
  });

  it('infers an optimistic article type when the accepted response omits content_type', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            id: 'job-article',
            status: 'pending',
          }),
        ),
      ),
    );

    render(
      <SubmitJobProvider>
        <OpenSubmitButton />
        <LastAcceptedProbe />
      </SubmitJobProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open submit' }));
    const input = screen.getByPlaceholderText('Paste a video, article, or repo URL…');
    fireEvent.change(input, {
      target: { value: 'https://example.com/deep-dive' },
    });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => expect(screen.getByText('article')).toBeTruthy());
  });

  it('infers an optimistic repo type for www.github.com when the accepted response omits content_type', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            id: 'job-repo',
            status: 'pending',
          }),
        ),
      ),
    );

    render(
      <SubmitJobProvider>
        <OpenSubmitButton />
        <LastAcceptedProbe />
      </SubmitJobProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open submit' }));
    const input = screen.getByPlaceholderText('Paste a video, article, or repo URL…');
    fireEvent.change(input, {
      target: { value: 'https://www.github.com/Leon-87-7/vig' },
    });
    fireEvent.submit(input.closest('form')!);

    await waitFor(() => expect(screen.getByText('repo')).toBeTruthy());
  });
});
