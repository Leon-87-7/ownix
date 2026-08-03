// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { IntakeStateBanner } from './intake-state-banner';

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('IntakeStateBanner', () => {
  it('renders nothing when there is no pending state', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse({ pending: null }));
    const { container } = render(<IntakeStateBanner />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('shows the pending mode and job id', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({
        pending: { mode: 'awaiting_intent', job_id: 'job_abcd', expires_at: '2099-01-01T00:00:00Z' },
      }),
    );
    render(<IntakeStateBanner />);
    await waitFor(() =>
      expect(screen.getByText(/waiting for your intent text/i)).toBeInTheDocument(),
    );
    expect(screen.getByText(/job_abcd/)).toBeInTheDocument();
  });

  it('cancel clears the banner only when the DELETE actually succeeds', async () => {
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (init?.method === 'DELETE') return new Response(null, { status: 500 });
      return jsonResponse({
        pending: { mode: 'awaiting_freestyle', job_id: 'job_wxyz', expires_at: '2099-01-01T00:00:00Z' },
      });
    });

    render(<IntakeStateBanner />);
    await screen.findByRole('button', { name: /cancel/i });
    await user.click(screen.getByRole('button', { name: /cancel/i }));

    // A failed DELETE must not optimistically clear the banner.
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent(/couldn.t cancel/i),
    );
    expect(screen.getByText(/waiting for your freestyle prompt/i)).toBeInTheDocument();
  });

  it('cancel clears the banner on a successful DELETE', async () => {
    const user = userEvent.setup();
    let cancelled = false;
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      if (init?.method === 'DELETE') {
        cancelled = true;
        return jsonResponse({ cleared: true });
      }
      return jsonResponse({
        pending: cancelled
          ? null
          : { mode: 'awaiting_intent', job_id: 'job_abcd', expires_at: '2099-01-01T00:00:00Z' },
      });
    });

    render(<IntakeStateBanner />);
    await screen.findByRole('button', { name: /cancel/i });
    await user.click(screen.getByRole('button', { name: /cancel/i }));

    await waitFor(() =>
      expect(screen.queryByText(/waiting for your intent text/i)).not.toBeInTheDocument(),
    );
  });
});
