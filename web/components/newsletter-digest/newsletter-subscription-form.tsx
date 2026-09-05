'use client';

import { useState } from 'react';
import type { FormEvent } from 'react';
import { MailPlus } from 'lucide-react';

export function NewsletterSubscriptionForm({
  onSubmit,
  submitting = false,
  error,
}: {
  onSubmit: (input: { name: string; sender_email: string }) => Promise<void> | void;
  submitting?: boolean;
  error?: string | null;
}) {
  const [name, setName] = useState('');
  const [sender, setSender] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await onSubmit({ name: name.trim(), sender_email: sender.trim().toLowerCase() });
    setName('');
    setSender('');
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-line bg-surface p-4"
    >
      <div className="flex items-center gap-2">
        <MailPlus className="h-5 w-5 text-signal" aria-hidden="true" />
        <h2 className="text-title font-semibold text-ink">Add newsletter</h2>
      </div>
      <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1.2fr_auto] sm:items-end">
        <div>
          <label className="mb-1 block text-label font-medium text-body" htmlFor="newsletter-name">
            Name
          </label>
          <input
            id="newsletter-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-copy text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            placeholder="Morning briefing"
          />
        </div>
        <div>
          <label className="mb-1 block text-label font-medium text-body" htmlFor="newsletter-sender">
            Sender email
          </label>
          <input
            id="newsletter-sender"
            required
            type="email"
            value={sender}
            onChange={(event) => setSender(event.target.value)}
            className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-copy text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            placeholder="editor@example.com"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="h-9 rounded-md bg-signal px-4 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] active:bg-signal-deep disabled:bg-surface disabled:text-muted"
        >
          {submitting ? 'Adding...' : 'Add'}
        </button>
      </div>
      {error && (
        <p role="alert" className="mt-3 text-sm text-status-error">
          {error}
        </p>
      )}
    </form>
  );
}
