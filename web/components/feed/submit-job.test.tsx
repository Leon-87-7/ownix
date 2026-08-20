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

    expect(screen.getByRole('button', { name: /Submit URL\s*N/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Ingest Docs\s*D/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Ingest Link\s*U/i })).toBeTruthy();
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
    fireEvent.click(screen.getByRole('button', { name: /Ingest Link\s*Save a link/i }));

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

describe('Ingest Link — batch paste (#494)', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function openIngestLink() {
    render(
      <SubmitJobProvider>
        <LastAcceptedProbe />
      </SubmitJobProvider>,
    );
    fireEvent.keyDown(window, { key: 'u' });
    return screen.getByPlaceholderText(/example\.com/i);
  }

  it('posts one job per pasted URL, in a paste with a label and a duplicate', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'job-1', content_type: 'link', status: 'pending' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const textarea = openIngestLink();
    fireEvent.change(textarea, {
      target: {
        value:
          'Design Systems — https://land-book.com\nhttps://godly.website\nhttps://land-book.com',
      },
    });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    const urls = (fetchMock.mock.calls as [string, RequestInit][]).map(
      ([, init]) => JSON.parse(init.body as string).url,
    );
    expect(urls.sort()).toEqual(
      ['https://godly.website', 'https://land-book.com'].sort(),
    );
  });

  it('the screenshot bug: a whitespace-joined blob becomes N jobs, not one', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'j1', content_type: 'link', status: 'pending' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    const textarea = openIngestLink();
    fireEvent.change(textarea, {
      target: {
        value:
          'https://land-book.com https://godly.website https://mobbin.com',
      },
    });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it('bounds concurrent link submissions while preserving the full batch', async () => {
    let active = 0;
    let maxActive = 0;
    const release: Array<() => void> = [];
    const fetchMock = vi.fn(
      () =>
        new Promise<Response>((resolve) => {
          active += 1;
          maxActive = Math.max(maxActive, active);
          release.push(() => {
            active -= 1;
            resolve(
              new Response(
                JSON.stringify({ id: 'j1', content_type: 'link', status: 'pending' }),
              ),
            );
          });
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const textarea = openIngestLink();
    fireEvent.change(textarea, {
      target: {
        value: Array.from({ length: 8 }, (_, i) => `https://site-${i}.example`).join('\n'),
      },
    });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(6));
    expect(maxActive).toBe(6);

    release.splice(0).forEach((done) => done());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(8));
    release.splice(0).forEach((done) => done());
    await waitFor(() => expect(maxActive).toBe(6));
  });

  it('a failure keeps the dialog open and renders an inline error row', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init: RequestInit) => {
      const { url } = JSON.parse(init.body as string);
      if (url === 'https://bad.example') {
        return Promise.resolve({
          ok: false,
          json: async () => ({ detail: 'Add Link needs a valid HTTP(S) URL or bare domain' }),
        });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({ id: 'j1', content_type: 'link', status: 'pending' }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const textarea = openIngestLink();
    fireEvent.change(textarea, {
      target: { value: 'https://good.example\nhttps://bad.example' },
    });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() =>
      expect(
        screen.getByText('Add Link needs a valid HTTP(S) URL or bare domain'),
      ).toBeTruthy(),
    );
    // Dialog stays open on partial failure — the textarea is still mounted.
    expect(screen.getByDisplayValue(/bad\.example/)).toBeTruthy();
  });

  it('lastAccepted fires once per successful job, progressively', async () => {
    let calls = 0;
    const fetchMock = vi.fn().mockImplementation(() => {
      calls += 1;
      return Promise.resolve({
        ok: true,
        json: async () => ({
          id: `job-${calls}`,
          content_type: 'link',
          status: 'pending',
        }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    const textarea = openIngestLink();
    fireEvent.change(textarea, {
      target: { value: 'https://a.example\nhttps://b.example' },
    });
    fireEvent.submit(textarea.closest('form')!);

    await waitFor(() => expect(screen.getByText('link')).toBeTruthy());
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it('opens GoTo with the G then T chord', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ items: [] }))));

    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { key: 'g' });
    fireEvent.keyDown(window, { key: 't' });

    expect(screen.getByRole('dialog', { name: 'GoTo' })).toBeTruthy();
  });

  it('does not open GoTo on a lone G', () => {
    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { key: 'g' });

    expect(screen.queryByRole('dialog', { name: 'GoTo' })).toBeNull();
  });

  it('does not open GoTo when a modified key interrupts the chord', () => {
    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { key: 'g' });
    fireEvent.keyDown(window, { key: 'c', ctrlKey: true });
    fireEvent.keyDown(window, { key: 't' });

    expect(screen.queryByRole('dialog', { name: 'GoTo' })).toBeNull();
  });

  it('does not open GoTo when a keystroke inside a field interrupts the chord', () => {
    render(
      <SubmitJobProvider>
        <input aria-label="Notes" />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { key: 'g' });
    fireEvent.keyDown(screen.getByLabelText('Notes'), { key: 'x' });
    fireEvent.keyDown(window, { key: 't' });

    expect(screen.queryByRole('dialog', { name: 'GoTo' })).toBeNull();
  });

  it('does not open GoTo once the chord window has elapsed', () => {
    vi.useFakeTimers();
    try {
      render(
        <SubmitJobProvider>
          <span />
        </SubmitJobProvider>,
      );

      fireEvent.keyDown(window, { key: 'g' });
      vi.advanceTimersByTime(700);
      fireEvent.keyDown(window, { key: 't' });

      expect(screen.queryByRole('dialog', { name: 'GoTo' })).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it('lists GoTo Links in the launcher Navigate group with its G T shortcut', () => {
    render(
      <SubmitJobProvider>
        <span />
      </SubmitJobProvider>,
    );

    fireEvent.keyDown(window, { ctrlKey: true, key: 'K', shiftKey: true });

    expect(
      screen.getByRole('button', { name: /GoTo Links\s*G\s*T/i }),
    ).toBeTruthy();
  });
});
