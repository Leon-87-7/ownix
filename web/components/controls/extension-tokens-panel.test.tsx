// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ExtensionTokensPanel } from './extension-tokens-panel';

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

describe('ExtensionTokensPanel', () => {
  it('shows "no paired extensions" when the token list is empty', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(jsonResponse([]));

    render(<ExtensionTokensPanel />);

    await waitFor(() =>
      expect(screen.getByText(/no paired extensions yet/i)).toBeInTheDocument(),
    );
  });

  it('lists existing tokens with a revoke button', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      jsonResponse([{ id: 'hash1', created_at: 1000, last_used_at: null, label: null }]),
    );

    render(<ExtensionTokensPanel />);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument(),
    );
  });

  it('generating a pairing code displays it', async () => {
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/extension/pair')) {
        return jsonResponse({ code: 'ABC123', expires_in: 300 });
      }
      return jsonResponse([]);
    });

    render(<ExtensionTokensPanel />);
    await user.click(screen.getByRole('button', { name: /generate pairing code/i }));

    await waitFor(() => expect(screen.getByText('ABC123')).toBeInTheDocument());
  });

  it('copies the pairing code to the clipboard', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText');
    vi.spyOn(global, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/extension/pair')) {
        return jsonResponse({ code: 'ABC123', expires_in: 300 });
      }
      return jsonResponse([]);
    });

    render(<ExtensionTokensPanel />);
    await user.click(screen.getByRole('button', { name: /generate pairing code/i }));
    await screen.findByText('ABC123');

    await user.click(screen.getByRole('button', { name: /copy pairing code/i }));
    expect(writeText).toHaveBeenCalledWith('ABC123');
  });

  it('revoking a token removes it from the list', async () => {
    const user = userEvent.setup();
    vi.spyOn(global, 'fetch').mockImplementation(async (input, init) => {
      const url = typeof input === 'string' ? input : (input as Request).url;
      if (url.includes('/api/extension/tokens/hash1') && init?.method === 'DELETE') {
        return new Response(null, { status: 204 });
      }
      return jsonResponse([{ id: 'hash1', created_at: 1000, last_used_at: null, label: null }]);
    });

    render(<ExtensionTokensPanel />);
    await screen.findByRole('button', { name: /revoke/i });
    await user.click(screen.getByRole('button', { name: /revoke/i }));

    await waitFor(() =>
      expect(screen.getByText(/no paired extensions yet/i)).toBeInTheDocument(),
    );
  });
});
