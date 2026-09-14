'use client';

import { useCallback, useEffect, useState } from 'react';

import { CopyButton } from '@/components/ui/copy-button';
import { DateTime } from '@/components/ui/date-time';
import { describeError } from '@/lib/fetch-utils';
import {
  createMcpPairingCode,
  listMcpTokens,
  revokeMcpToken,
  type McpToken,
} from '@/lib/hooks/useMcpTokens';

/** MCP agent pairing + active-token management (issue #632). */
export function McpTokensPanel() {
  const [tokens, setTokens] = useState<McpToken[]>([]);
  const [loading, setLoading] = useState(true);
  const [pairingCode, setPairingCode] = useState<string | null>(null);
  const [pairingDeadline, setPairingDeadline] = useState<number | null>(null);
  const [pairingRemaining, setPairingRemaining] = useState(0);
  const [pairing, setPairing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revokingId, setRevokingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setTokens(await listMcpTokens());
    } catch (err) {
      setError(describeError(err, 'Failed to load tokens.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // The code is single-use server-side, but nothing clears it from the
  // screen once it's expired — count down and drop it so a user can't copy
  // a code that will just 401. Ticks off an absolute deadline (not a
  // decrementing counter) so a throttled background tab still shows the
  // correct remaining time, and expires promptly, once it wakes up.
  useEffect(() => {
    if (pairingDeadline == null) return;
    const tick = () => {
      const remaining = Math.max(0, Math.ceil((pairingDeadline - Date.now()) / 1000));
      setPairingRemaining(remaining);
      if (remaining <= 0) {
        setPairingCode(null);
        setPairingDeadline(null);
      }
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [pairingDeadline]);

  const handlePair = async () => {
    setPairing(true);
    setError(null);
    try {
      const { code, expires_in } = await createMcpPairingCode();
      setPairingCode(code);
      setPairingDeadline(Date.now() + expires_in * 1000);
    } catch (err) {
      setError(describeError(err, 'Failed to create a pairing code.'));
    } finally {
      setPairing(false);
    }
  };

  const handleRevoke = async (tokenId: string) => {
    setRevokingId(tokenId);
    setError(null);
    try {
      await revokeMcpToken(tokenId);
      setTokens((prev) => prev.filter((t) => t.id !== tokenId));
    } catch (err) {
      setError(describeError(err, 'Failed to revoke token.'));
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-copy text-body">
          Connect an MCP client by generating a one-time pairing code here, then
          redeeming it for a private bearer token in your client.
          The code expires in 5 minutes and works once.
        </p>
        <button
          type="button"
          onClick={handlePair}
          disabled={pairing}
          className="mt-3 h-9 rounded-md bg-signal px-4 text-copy font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:opacity-50"
        >
          {pairing ? 'Generating…' : 'Generate pairing code'}
        </button>
        {pairingCode && (
          <div className="mt-2 flex items-center justify-between gap-3 rounded-md border border-line bg-raised px-3 py-2 font-mono text-label text-ink">
            <span className="break-all">{pairingCode}</span>
            <span className="flex shrink-0 items-center gap-3">
              <span className="font-sans text-label text-muted">
                Expires in {pairingRemaining}s
              </span>
              <CopyButton value={pairingCode} ariaLabel="Copy pairing code" />
            </span>
          </div>
        )}
      </div>

      {error && (
        <p
          role="alert"
          className="rounded-md border border-status-error/40 bg-status-error-tint px-3 py-2 text-copy text-status-error"
        >
          {error}
        </p>
      )}

      <div>
        <h4 className="mb-2 text-label font-semibold text-muted">
          Connected MCP clients
        </h4>
        {loading && <p className="text-copy text-muted">Loading…</p>}
        {!loading && tokens.length === 0 && (
          <p className="text-copy text-muted">No paired MCP clients yet.</p>
        )}
        {!loading && tokens.length > 0 && (
          <ul className="space-y-2">
            {tokens.map((token) => (
              <li
                key={token.id}
                className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3 py-2 text-copy"
              >
                <span className="text-body">
                  {token.label ?? 'Unnamed device'}, last used:{' '}
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
                  className="h-7 rounded-md border border-line px-2 text-label font-medium text-body transition-ui hover:border-status-error hover:text-status-error disabled:opacity-50"
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
