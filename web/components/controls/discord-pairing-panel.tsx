'use client';

import { useEffect, useState } from 'react';

import { CopyButton } from '@/components/ui/copy-button';
import { apiPost, describeError } from '@/lib/fetch-utils';

const FALLBACK = 'Failed to create a pairing code.';

/** Binds a Discord account to this one. The bot can't tell who you are from a
 * DM, so the proof runs the other way: mint a short-lived code in this
 * (authenticated) session and carry it into the DM you want paired. */
export function DiscordPairingPanel() {
  const [code, setCode] = useState<string | null>(null);
  const [deadline, setDeadline] = useState<number | null>(null);
  const [expiresIn, setExpiresIn] = useState<number | null>(null);
  const [pairing, setPairing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The code dies server-side on its own; tick it down here and stop
  // rendering it at zero so nobody DMs a code that's already dead.
  const live = code !== null && expiresIn !== null && expiresIn > 0;

  // Counted off an absolute deadline, not by subtracting a second per tick —
  // a backgrounded tab stops firing timers, and a decrementing counter would
  // resume showing time left on a code the server already expired.
  useEffect(() => {
    if (deadline === null) return;
    const tick = () =>
      setExpiresIn(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [deadline]);

  const handlePair = async () => {
    setPairing(true);
    setError(null);
    try {
      const res = await apiPost<{ code: string; expires_in: number }>(
        '/api/auth/discord/pair',
        {},
        FALLBACK,
      );
      if (!res.ok) {
        setError(res.detail);
        return;
      }
      setCode(res.data.code);
      setDeadline(Date.now() + res.data.expires_in * 1000);
    } catch (err) {
      setError(describeError(err, FALLBACK));
    } finally {
      setPairing(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-body">
        Send links from Discord: generate a one-time code here, then DM it to
        the Ownix bot. The code expires in 5 minutes and works once. After
        that, anything you DM the bot lands in your Index.
      </p>
      <button
        type="button"
        onClick={handlePair}
        disabled={pairing}
        className="h-9 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:opacity-50"
      >
        {pairing ? 'Generating…' : 'Generate pairing code'}
      </button>
      {code && live && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-raised px-3 py-2 font-mono text-sm text-ink">
          <span className="break-all">{code}</span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="font-sans text-label text-muted">
              Expires in {expiresIn}s
            </span>
            <CopyButton
              value={code}
              ariaLabel="Copy Discord pairing code"
            />
          </span>
        </div>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-md border border-status-error/40 bg-status-error-tint px-3 py-2 text-sm text-status-error"
        >
          {error}
        </p>
      )}
    </div>
  );
}
