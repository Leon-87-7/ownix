// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { DiscordPairingPanel } from './discord-pairing-panel';

function jsonResponse(body: unknown, init?: ResponseInit): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('DiscordPairingPanel', () => {
  it('shows the minted code and its countdown', async () => {
    const fetchMock = vi
      .spyOn(global, 'fetch')
      .mockResolvedValue(jsonResponse({ code: 'abc123', expires_in: 300 }));

    render(<DiscordPairingPanel />);
    await userEvent.click(screen.getByRole('button', { name: /generate pairing code/i }));

    expect(await screen.findByText('abc123')).toBeInTheDocument();
    expect(screen.getByText(/expires in 300s/i)).toBeInTheDocument();
    expect(
      fetchMock.mock.calls.some(([url]) => url === '/api/auth/discord/pair'),
    ).toBe(true);
  });

  it('hides a code the server has already expired, even if the tab was suspended', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({ code: 'abc123', expires_in: 300 }),
    );
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    try {
      render(<DiscordPairingPanel />);
      await user.click(screen.getByRole('button', { name: /generate pairing code/i }));
      expect(await screen.findByText('abc123')).toBeInTheDocument();

      // Jump the wall clock past the deadline WITHOUT firing the ~300 ticks a
      // foreground tab would have run — that's what a suspended tab does. One
      // tick after resuming has to show the code as expired; decrementing a
      // second per tick would still claim ~299s left.
      vi.setSystemTime(Date.now() + 301_000);
      await vi.advanceTimersByTimeAsync(1_000);

      await waitFor(() => expect(screen.queryByText('abc123')).not.toBeInTheDocument());
    } finally {
      vi.useRealTimers();
    }
  });

  it("surfaces the server's detail on failure", async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse({ detail: 'Not signed in' }, { status: 401 }),
    );

    render(<DiscordPairingPanel />);
    await userEvent.click(screen.getByRole('button', { name: /generate pairing code/i }));

    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Not signed in'),
    );
  });
});
