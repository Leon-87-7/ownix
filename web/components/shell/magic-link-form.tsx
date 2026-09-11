'use client';

import { useId, useState } from 'react';
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
      {/* Input and submit are one joined control, not two stacked rows: the
        pair costs a single 44px row on a plate that already carries Telegram,
        GitHub and Google above it. */}
      <div className="flex h-11 items-center overflow-hidden rounded-md border border-line bg-canvas transition-ui hover:border-line-strong focus-within:border-signal">
        <input
          id={inputId}
          type="email"
          required
          maxLength={254}
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          className="h-full min-w-0 flex-1 bg-transparent px-3 text-sm text-ink placeholder-muted focus:outline-none"
        />
        <button
          type="submit"
          disabled={sending}
          className="h-full shrink-0 whitespace-nowrap border-l border-line bg-raised px-3 text-sm font-medium text-ink transition-ui hover:bg-selected focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-signal disabled:cursor-not-allowed disabled:opacity-50"
        >
          {sending ? 'Sending…' : 'Send link'}
        </button>
      </div>
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
