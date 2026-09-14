// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { McpTokensPanel } from './mcp-tokens-panel';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.unstubAllGlobals();
});
afterAll(() => server.close());

function useTokens(tokens: unknown[] = []) {
  server.use(http.get('/api/mcp/tokens', () => HttpResponse.json(tokens)));
}

describe('McpTokensPanel', () => {
  it('shows "no paired MCP clients" when the token list is empty', async () => {
    useTokens([]);

    render(<McpTokensPanel />);

    await waitFor(() =>
      expect(screen.getByText(/no paired MCP clients yet/i)).toBeInTheDocument(),
    );
  });

  it('lists existing tokens with a revoke button', async () => {
    useTokens([{ id: 'hash1', created_at: 1000, last_used_at: null, label: null }]);

    render(<McpTokensPanel />);

    await waitFor(() =>
      expect(screen.getByRole('button', { name: /revoke/i })).toBeInTheDocument(),
    );
  });

  it('generating a pairing code displays it', async () => {
    const user = userEvent.setup();
    useTokens([]);
    server.use(
      http.post('/api/mcp/pair', () => HttpResponse.json({ code: 'ABC123', expires_in: 300 })),
    );

    render(<McpTokensPanel />);
    await user.click(screen.getByRole('button', { name: /generate pairing code/i }));

    await waitFor(() => expect(screen.getByText('ABC123')).toBeInTheDocument());
  });

  it('copies the pairing code to the clipboard', async () => {
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, 'writeText');
    useTokens([]);
    server.use(
      http.post('/api/mcp/pair', () => HttpResponse.json({ code: 'ABC123', expires_in: 300 })),
    );

    render(<McpTokensPanel />);
    await user.click(screen.getByRole('button', { name: /generate pairing code/i }));
    await screen.findByText('ABC123');

    await user.click(screen.getByRole('button', { name: /copy pairing code/i }));
    expect(writeText).toHaveBeenCalledWith('ABC123');
  });

  it('revoking a token removes it from the list', async () => {
    const user = userEvent.setup();
    useTokens([{ id: 'hash1', created_at: 1000, last_used_at: null, label: null }]);
    server.use(
      http.delete('/api/mcp/tokens/hash1', () => new HttpResponse(null, { status: 204 })),
    );

    render(<McpTokensPanel />);
    await screen.findByRole('button', { name: /revoke/i });
    await user.click(screen.getByRole('button', { name: /revoke/i }));

    await waitFor(() =>
      expect(screen.getByText(/no paired MCP clients yet/i)).toBeInTheDocument(),
    );
  });
});
