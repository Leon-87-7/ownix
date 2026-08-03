/**
 * Production-safe extension auth (issue #479): redeem a dashboard-minted
 * pairing code for an opaque bearer token, store only that token locally,
 * and never touch a raw dashboard session cookie.
 */

const TOKEN_STORAGE_KEY = 'ownixExtensionToken';

export async function getExtensionToken(): Promise<string | null> {
  const stored = await chrome.storage.local.get(TOKEN_STORAGE_KEY);
  return (stored[TOKEN_STORAGE_KEY] as string | undefined) ?? null;
}

export async function setExtensionToken(token: string): Promise<void> {
  await chrome.storage.local.set({ [TOKEN_STORAGE_KEY]: token });
}

export async function clearExtensionToken(): Promise<void> {
  await chrome.storage.local.remove(TOKEN_STORAGE_KEY);
}

/** Redeem a one-time pairing code (minted at `/settings/extensions/connect` in the dashboard) for a bearer token. */
export async function redeemPairingCode(host: string, code: string): Promise<void> {
  // `host` is the user's own configured Ownix instance (validated at the
  // point it's saved — see api.ts's setOwnixHost) — re-checked here too so
  // this fetch's target is never anything but a well-formed http(s) origin.
  const parsedHost = new URL(host);
  if (parsedHost.protocol !== 'https:' && parsedHost.protocol !== 'http:') {
    throw new Error('Ownix host must be a valid http(s) URL.');
  }
  const res = await fetch(`${parsedHost.origin}/api/extension/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `Pairing failed (${res.status})`);
  }
  const data = (await res.json()) as { token: string };
  await setExtensionToken(data.token);
}
