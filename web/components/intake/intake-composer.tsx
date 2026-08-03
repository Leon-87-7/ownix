'use client';

import { useState, type FormEvent } from 'react';

/**
 * The one intake input: paste a URL, type a command, or write a note. Fixed
 * height (no autogrow) so repeated submits don't reflow the page around the
 * composer — DESIGN.md's "stable composer height" requirement.
 */
export function IntakeComposer({
  onSubmit,
  disabled,
  initialValue = '',
}: {
  /** Returns whether the submit succeeded — the composer only clears input on true, so a failed send never loses what the user typed. */
  onSubmit: (value: string) => Promise<boolean>;
  disabled?: boolean;
  /** Prefill from `/intake/share` (issue #476) — one-time initial value, not synced on change. */
  initialValue?: string;
}) {
  const [value, setValue] = useState(initialValue);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      const ok = await onSubmit(trimmed);
      if (ok) setValue('');
    } finally {
      setSubmitting(false);
    }
  };

  const busy = disabled || submitting;

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3"
    >
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Paste a URL, type a command like /help, or write a note…"
        rows={4}
        disabled={busy}
        aria-label="Intake composer"
        className="h-[104px] w-full resize-none rounded-md border border-line bg-surface p-3 font-sans text-sm text-ink placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-signal disabled:opacity-50"
      />
      <div className="flex items-center justify-end">
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="h-9 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:opacity-50"
        >
          {submitting ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  );
}
