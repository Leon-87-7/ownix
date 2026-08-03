/** Client for `/api/extension/*` (issue #479) — pairing + token list/revoke. */

export interface ExtensionToken {
  id: string;
  created_at: number;
  last_used_at: number | null;
  label: string | null;
}

export async function createPairingCode(): Promise<{ code: string; expires_in: number }> {
  const res = await fetch('/api/extension/pair', { method: 'POST' });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as { detail?: string }).detail ?? `Pairing failed (${res.status})`);
  }
  return res.json();
}

export async function listExtensionTokens(): Promise<ExtensionToken[]> {
  const res = await fetch('/api/extension/tokens');
  if (!res.ok) throw new Error(`Failed to load extension tokens (${res.status})`);
  return res.json();
}

export async function revokeExtensionToken(tokenId: string): Promise<void> {
  const res = await fetch(`/api/extension/tokens/${encodeURIComponent(tokenId)}`, {
    method: 'DELETE',
  });
  if (!res.ok && res.status !== 404) {
    throw new Error(`Failed to revoke token (${res.status})`);
  }
}
