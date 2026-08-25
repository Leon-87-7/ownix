'use client';

import { useCallback, useEffect, useState } from 'react';

import { CopyButton } from '@/components/ui/copy-button';
import { DateTime } from '@/components/ui/date-time';
import {
  createPairingCode,
  listExtensionTokens,
  revokeExtensionToken,
  type ExtensionToken,
} from '@/lib/hooks/useExtensionTokens';

/** Chrome extension pairing + active-token management (issue #479). */
export function ExtensionTokensPanel() {
  const [tokens, setTokens] = useState<ExtensionToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingExpiresIn, setPairingExpiresIn] = useState<number | null>(null);
  const [pairing, setPairing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTokens(await listExtensionTokens());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tokens.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The code is single-use server-side, but nothing clears it from the
  // screen once it's expired — count down and drop it so a user can't copy
  // a code that will just 401.
  useEffect(() => {
    if (pairingExpiresIn == null) return;
    if (pairingExpiresIn <= 0) {
      setPairingCode(null);
      setPairingExpiresIn(null);
      return;
    }
    const timeout = setTimeout(() => setPairingExpiresIn((s) => (s ?? 1) - 1), 1000);
    return () => clearTimeout(timeout);
  }, [pairingExpiresIn]);

  const handlePair = async () => {
    setPairing(true);
    setError(null);
    try {
      const { code, expires_in } = await createPairingCode();
      setPairingCode(code);
      setPairingExpiresIn(expires_in);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create a pairing code.');
    } finally {
      setPairing(false);
    }
  };

  const handleRevoke = async (tokenId: string) => {
    setRevokingId(tokenId);
    setError(null);
    try {
      await revokeExtensionToken(tokenId);
      setTokens((prev) => prev.filter((t) => t.id !== tokenId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to revoke token.');
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-sm text-body">
          Connect the Ownix Chrome extension by generating a one-time pairing
          code here, then pasting it into the extension&apos;s options page.
          The code expires in 5 minutes and works once.
        </p>
        <button
          type="button"
          onClick={handlePair}
          disabled={pairing}
          className="mt-3 h-9 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:opacity-50"
        >
          {pairing ? 'Generating…' : 'Generate pairing code'}
        </button>
        {pairingCode && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-md border border-line bg-raised px-3 py-2 font-mono text-sm text-ink">
            <span className="break-all">{pairingCode}</span>
            <span className="flex shrink-0 items-center gap-3">
              <span className="font-sans text-label text-muted">
                Expires in {pairingExpiresIn}s
              </span>
              <CopyButton value={pairingCode} ariaLabel="Copy pairing code" />
            </span>
          </div>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-status-error/40 bg-status-error-tint px-3 py-2 text-sm text-status-error"
        >
          {error}
        </p>
      )}

      <div>
        <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
          Connected extensions
        </h4>
        {loading && <p className="text-sm text-muted">Loading…</p>}
        {!loading && tokens.length === 0 && (
          <p className="text-sm text-muted">No paired extensions yet.</p>
        )}
        {!loading && tokens.length > 0 && (
          <ul className="space-y-2">
            {tokens.map((token) => (
              <li
                key={token.id}
                className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2 text-sm"
              >
                <span className="text-body">
                  {token.label ?? 'Unnamed device'} — last used:{' '}
                  {token.last_used_at == null ? (
                    'Never'
                  ) : (
                    <DateTime iso={new Date(token.last_used_at * 1000).toISOString()} />
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => handleRevoke(token.id)}
                  disabled={revokingId === token.id}
                  className="h-7 rounded-md border border-line px-2 text-xs font-medium text-body transition-ui hover:border-status-error hover:text-status-error disabled:opacity-50"
                >
                  {revokingId === token.id ? 'Revoking…' : 'Revoke'}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
