'use client';

/* @ds
name: IntakeCommandPalette
purpose: The slash-command autocomplete dropdown for IntakeComposer — arrow-key/Tab/Enter navigable listbox of matching commands.
when-not: Only opens for a leading / with no whitespace yet typed (commandQuery) — never triggers on a / that appears inside a pasted URL.
notes: The command list is server-fetched from /api/intake/commands (derived from SHARED_COMMANDS), not hardcoded — a fetch failure just means the palette doesn't open, typing the command still works.
status: inferred
*/

import { useEffect, useState } from 'react';

export interface IntakeCommand {
  name: string;
  args: string;
  summary: string;
  usage: string;
}

/**
 * Slash-command palette for the composer (issue #484).
 *
 * The list is fetched from `GET /api/intake/commands`, which derives it from
 * `SHARED_COMMANDS` — deliberately not a hardcoded array, so each command
 * migration lights up its own entry by landing rather than by someone
 * remembering to edit a second list.
 */
export function useIntakeCommands(): IntakeCommand[] {
  const [commands, setCommands] = useState<IntakeCommand[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch('/api/intake/commands');
        if (!res.ok) return;
        const data = (await res.json()) as { commands?: IntakeCommand[] };
        if (!cancelled) setCommands(data.commands ?? []);
      } catch {
        // Palette is an affordance, not a dependency — typing the command still works.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return commands;
}

/** Only a `/` that starts the composer opens the palette — never one inside a URL. */
export function commandQuery(value: string): string | null {
  if (!value.startsWith('/')) return null;
  if (/\s/.test(value)) return null;
  return value;
}

export function matchCommands(commands: IntakeCommand[], query: string): IntakeCommand[] {
  const q = query.toLowerCase();
  return commands.filter((c) => c.name.toLowerCase().startsWith(q));
}

export function IntakeCommandPalette({
  commands,
  activeIndex,
  onSelect,
  listId,
  activeOptionId,
}: {
  commands: IntakeCommand[];
  activeIndex: number;
  onSelect: (command: IntakeCommand) => void;
  listId: string;
  activeOptionId: string;
}) {
  if (commands.length === 0) return null;

  return (
    <ul
      id={listId}
      role="listbox"
      aria-label="Commands"
      className="mb-2 overflow-hidden rounded-md border border-line bg-raised"
    >
      {commands.map((command, i) => {
        const active = i === activeIndex;
        return (
          <li key={command.name}>
            <button
              type="button"
              id={active ? activeOptionId : undefined}
              role="option"
              aria-selected={active}
              // Keep focus in the textarea so typing continues uninterrupted.
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onSelect(command)}
              className={`flex w-full items-baseline gap-2 px-3 py-1.5 text-left transition-ui ${
                active ? 'bg-surface-selected' : 'hover:bg-surface'
              }`}
            >
              <span className="font-mono text-sm text-ink">{command.name}</span>
              {command.args && (
                <span className="font-mono text-label text-signal">{command.args}</span>
              )}
              <span className="ml-auto truncate text-label text-muted">{command.summary}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
