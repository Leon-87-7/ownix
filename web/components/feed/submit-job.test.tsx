// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { INTAKE_ACTIONS, SubmitJobProvider, useSubmitJob } from './submit-job';

function ShortcutProbe() {
  const { open } = useSubmitJob();
  return <span>{open ? 'submit open' : 'submit closed'}</span>;
}

function LastAcceptedProbe() {
  const { lastAccepted } = useSubmitJob();
  return <span>{lastAccepted?.content_type ?? 'no accepted job'}</span>;
}


function OpenIntakeButton() {
  const { openIntake } = useSubmitJob();
  return (
    <button type="button" onClick={openIntake}>
      Open intake
    </button>
  );
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

  it('does not open the command launcher with Ctrl+K', () => {
    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { ctrlKey: true, key: 'k' });

    expect(screen.queryByText('Command launcher')).toBeNull();
  });

  it('opens the command launcher with Ctrl+Shift+K', () => {
    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { ctrlKey: true, key: 'K', shiftKey: true });

    expect(screen.getByText('Command launcher')).toBeTruthy();
  });



  it('drives the desktop launcher intake group from INTAKE_ACTIONS', () => {
    expect(INTAKE_ACTIONS.map((action) => action.label)).toEqual([
      'Submit URL',
      'Ingest Docs',
      'Ingest Link',
    ]);

    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { ctrlKey: true, key: 'K', shiftKey: true });

    expect(screen.getByRole('button', { name: /Submit URLN/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Ingest DocsD/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Ingest LinkU/i })).toBeTruthy();
  });

  it('opens the intake sheet with title and all action descriptions', () => {
    render(
      <SubmitJobProvider>
        <OpenIntakeButton />
      </SubmitJobProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open intake' }));

    expect(screen.getByText('Add to your Index')).toBeTruthy();
    for (const action of INTAKE_ACTIONS) {
      expect(screen.getByText(action.label)).toBeTruthy();
      expect(screen.getByText(action.description)).toBeTruthy();
    }
  });

  it('closes the intake sheet and opens the selected ingest dialog', async () => {
    render(
      <SubmitJobProvider>
        <OpenIntakeButton />
      </SubmitJobProvider>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open intake' }));
    fireEvent.click(screen.getByRole('button', { name: /Ingest LinkSave a link/i }));

    await waitFor(() =>
      expect(screen.getByRole('dialog', { name: 'Ingest Link' })).toBeTruthy(),
    );
    expect(screen.queryByText('Add to your Index')).toBeNull();
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
