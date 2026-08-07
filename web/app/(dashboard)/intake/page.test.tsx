// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import IntakePage from './page';

vi.mock('next/navigation', () => ({
  useSearchParams: () => new URLSearchParams(),
}));

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
  // jsdom's sessionStorage persists across tests in a file, and the thread now
  // hydrates from it (#488) — without this, cards leak between test cases.
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe('IntakePage', () => {
  it('shows an empty thread before anything is submitted', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ pending: null }));

    render(<IntakePage />);

    await waitFor(() =>
      expect(screen.getByText(/nothing submitted yet this session/i)).toBeInTheDocument(),
    );
  });

  it('submitting a supported URL renders a job_created response card', async () => {
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/intake/state')) return jsonResponse({ pending: null });
      if (url.includes('/api/jobs')) return jsonResponse({ items: [], total: 0, page: 1, limit: 20 });
      if (url.includes('/api/intake/message') && init?.method === 'POST') {
        return jsonResponse({
          schema_version: 1,
          kind: 'job_created',
          text: 'Received — job_abcd (short).',
          job_id: 'j1',
          job_url: '/jobs/j1',
          actions: [],
          artifacts: [],
          retryable: false,
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(<IntakePage />);

    const composer = await screen.findByLabelText(/intake composer/i);
    await user.type(composer, 'https://youtube.com/shorts/abc123');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText(/received — job_abcd/i)).toBeInTheDocument(),
    );
    expect(screen.getByRole('link', { name: /view job/i })).toHaveAttribute(
      'href',
      '/jobs/j1',
    );
  });

  it('shows an error banner when the submit request fails', async () => {
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/intake/state')) return jsonResponse({ pending: null });
      if (url.includes('/api/jobs')) return jsonResponse({ items: [], total: 0, page: 1, limit: 20 });
      if (url.includes('/api/intake/message') && init?.method === 'POST') {
        return jsonResponse({ detail: 'Rate limit exceeded' }, { status: 429 });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(<IntakePage />);

    const composer = await screen.findByLabelText(/intake composer/i);
    await user.type(composer, '/help');
    await user.click(screen.getByRole('button', { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/rate limit exceeded/i),
    );
  });

  it('restores the thread after a reload and re-derives status from the job', async () => {
    const user = userEvent.setup();
    let jobStatus = 'processing';
    const mockFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/intake/state')) return jsonResponse({ pending: null });
      if (url.includes('/api/jobs')) {
        return jsonResponse({
          items: [
            {
              id: 'j1',
              title: 'A restored video',
              url: 'https://youtube.com/shorts/abc123',
              content_type: 'short',
              status: jobStatus,
              created_at: '2026-08-06T10:00:00Z',
            },
          ],
          total: 1,
          page: 1,
          limit: 20,
        });
      }
      if (url.includes('/api/intake/message') && init?.method === 'POST') {
        return jsonResponse({
          schema_version: 1,
          kind: 'job_created',
          text: 'Received — job_abcd (short).',
          job_id: 'j1',
          job_url: '/jobs/j1',
          actions: [],
          artifacts: [],
          retryable: false,
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    };
    vi.spyOn(global, 'fetch').mockImplementation(mockFetch);

    const first = render(<IntakePage />);
    const composer = await screen.findByLabelText(/intake composer/i);
    await user.type(composer, 'https://youtube.com/shorts/abc123');
    await user.click(screen.getByRole('button', { name: /send/i }));
    await waitFor(() => expect(screen.getByText(/received — job_abcd/i)).toBeInTheDocument());

    // Simulate a reload: the component goes away, sessionStorage does not.
    first.unmount();

    // The job finished while the tab was closed — the restored card must show
    // the real state, not the "processing" it was persisted with.
    jobStatus = 'done';
    render(<IntakePage />);

    await waitFor(() => expect(screen.getByText(/received — job_abcd/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText('A restored video')).toBeInTheDocument());
    expect(screen.queryByText(/processing/i)).not.toBeInTheDocument();
  });

  it('starts empty when the browser session had nothing stored', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ pending: null }));
    sessionStorage.setItem('ownix.intake.thread', 'not json at all');

    render(<IntakePage />);

    await waitFor(() =>
      expect(screen.getByText(/nothing submitted yet this session/i)).toBeInTheDocument(),
    );
  });

  it('shows the pending-state banner with a working cancel button', async () => {
    const user = userEvent.setup();
    let cancelled = false;
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/intake/state') && init?.method === 'DELETE') {
        cancelled = true;
        return jsonResponse({ cleared: true });
      }
      if (url.includes('/api/jobs')) return jsonResponse({ items: [], total: 0, page: 1, limit: 20 });
      if (url.includes('/api/intake/state')) {
        return jsonResponse({
          pending: cancelled
            ? null
            : { mode: 'awaiting_freestyle', job_id: 'job_pending', expires_at: '2099-01-01T00:00:00Z' },
        });
      }
      throw new Error(`Unexpected fetch: ${url}`);
    });

    render(<IntakePage />);

    await waitFor(() =>
      expect(screen.getByText(/waiting for your freestyle prompt/i)).toBeInTheDocument(),
    );
    await user.click(screen.getByRole('button', { name: /cancel/i }));
    await waitFor(() => expect(cancelled).toBe(true));
  });
});
