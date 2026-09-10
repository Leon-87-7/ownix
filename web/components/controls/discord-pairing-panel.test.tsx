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
