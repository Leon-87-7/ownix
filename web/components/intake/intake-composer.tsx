'use client';

/* @ds
name: IntakeComposer
purpose: The one intake input — paste a URL, type a slash command, or write a note — fixed-height (no autogrow) so repeated submits never reflow the page.
when-not: Not for the dashboard's Submit URL flow (that's SubmitJobProvider) — this is the Intake console's own free-text/command entry point.
notes: Only clears its input on a true return from onSubmit, so a failed send never loses what was typed. Typing / at the start opens the command palette (IntakeCommandPalette).
status: inferred
*/

import { useId, useState, type FormEvent, type KeyboardEvent } from 'react';

import {
  IntakeCommandPalette,
  commandQuery,
  matchCommands,
  useIntakeCommands,
} from '@/components/intake/intake-command-palette';

/**
 * The one intake input: paste a URL, type a command, or write a note. Fixed
 * height (no autogrow) so repeated submits don't reflow the page around the
 * composer — DESIGN.md's "stable composer height" requirement.
 *
 * Typing `/` at the start opens the command palette (issue #484).
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
  const [activeIndex, setActiveIndex] = useState(0);
  const [paletteDismissed, setPaletteDismissed] = useState(false);
  const commands = useIntakeCommands();
  const listId = useId();
  const activeOptionId = useId();

  const query = commandQuery(value);
  const matches = query === null ? [] : matchCommands(commands, query);
  const paletteOpen = !paletteDismissed && matches.length > 0;

  const complete = (name: string) => {
    // Trailing space puts the cursor where the arguments go.
    setValue(`${name} `);
    setActiveIndex(0);
  };

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

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (!paletteOpen) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % matches.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i - 1 + matches.length) % matches.length);
    } else if (e.key === 'Enter' || e.key === 'Tab') {
      // Enter completes the command rather than submitting a half-typed one.
      e.preventDefault();
      complete(matches[Math.min(activeIndex, matches.length - 1)].name);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setPaletteDismissed(true);
    }
  };

  const busy = disabled || submitting;

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-3"
    >
      {paletteOpen && (
        <IntakeCommandPalette
          commands={matches}
          activeIndex={Math.min(activeIndex, matches.length - 1)}
          onSelect={(c) => complete(c.name)}
          listId={listId}
          activeOptionId={activeOptionId}
        />
      )}
      <textarea
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          setActiveIndex(0);
          setPaletteDismissed(false);
        }}
        onKeyDown={handleKeyDown}
        placeholder="Paste a URL, type a command like /help, or write a note…"
        rows={4}
        disabled={busy}
        aria-label="Intake composer"
        role="combobox"
        aria-expanded={paletteOpen}
        aria-controls={paletteOpen ? listId : undefined}
        aria-activedescendant={paletteOpen ? activeOptionId : undefined}
        aria-autocomplete="list"
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
