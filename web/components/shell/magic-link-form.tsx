'use client';

import { useId, useState } from 'react';
import { GhostButton } from '@/components/ui/ghost-button';
import { apiPost, describeError } from '@/lib/fetch-utils';

const FALLBACK = 'Could not send the link. Try again.';

/** Email sign-in: posts to the magic-link endpoint and renders whatever it
 * answers. The success copy is deliberately the server's own ("if that address
 * can receive email…") — it never confirms whether an account exists. */
export function MagicLinkForm({ className = '' }: { className?: string }) {
  const [email, setEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const inputId = useId();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true);
    setMessage(null);
    try {
      const res = await apiPost<{ message: string }>(
        '/api/auth/email/request',
        { email },
        FALLBACK,
      );
      setFailed(!res.ok);
      setMessage(res.ok ? res.data.message : res.detail);
    } catch (err: unknown) {
      setFailed(true);
      setMessage(describeError(err, FALLBACK));
    } finally {
      setSending(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className={`flex flex-col gap-2 ${className}`.trim()}
    >
      <label
        className="sr-only"
        htmlFor={inputId}
      >
        Email address
      </label>
      <input
        id={inputId}
        type="email"
        required
        maxLength={254}
        autoComplete="email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        className="h-11 w-full rounded-md border border-line bg-canvas px-3 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
      />
      <GhostButton
        type="submit"
        disabled={sending}
        accent="contrasignal"
        className="h-11 w-full text-sm font-medium text-ink"
      >
        {sending ? 'Sending…' : 'Email me a sign-in link'}
      </GhostButton>
      {message && (
        <p
          role="status"
          className={`text-xs leading-5 ${failed ? 'text-status-error' : 'text-muted'}`}
        >
          {message}
        </p>
      )}
    </form>
  );
}
