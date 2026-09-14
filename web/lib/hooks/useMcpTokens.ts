/** Client for MCP pairing and token list/revoke (issue #632). */

export interface McpToken {
  id: string;
  created_at: number;
  last_used_at: number | null;
  label: string | null;
}

export async function createMcpPairingCode(): Promise<{ code: string; expires_in: number }> {
  const res = await fetch('/api/mcp/pair', { method: 'POST' });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as { detail?: string }).detail ?? `Pairing failed (${res.status})`);
  }
  return res.json();
}

export async function listMcpTokens(): Promise<McpToken[]> {
  const res = await fetch('/api/mcp/tokens');
  if (!res.ok) throw new Error(`Failed to load MCP tokens (${res.status})`);
  return res.json();
}

export async function revokeMcpToken(tokenId: string): Promise<void> {
  const res = await fetch(`/api/mcp/tokens/${encodeURIComponent(tokenId)}`, { method: 'DELETE' });
  if (!res.ok && res.status !== 404) throw new Error(`Failed to revoke token (${res.status})`);
}
