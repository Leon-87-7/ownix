'use client';

import { useEffect, useState } from 'react';
import type { Template } from '@/lib/hooks/useTemplateList';

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

/** Only a `-` that starts the composer opens custom recipe shortcuts. */
export function recipeQuery(value: string): string | null {
  if (!value.startsWith('-')) return null;
  if (/\s/.test(value)) return null;
  return value;
}

export function matchRecipes(templates: Template[], query: string): Template[] {
  const q = query.toLowerCase();
  return templates.filter(
    (template) =>
      !template.is_builtin && `-${template.name}`.toLowerCase().startsWith(q),
  );
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

export function IntakeRecipePalette({
  recipes,
  activeIndex,
  onSelect,
  listId,
  activeOptionId,
}: {
  recipes: Template[];
  activeIndex: number;
  onSelect: (recipe: Template) => void;
  listId: string;
  activeOptionId: string;
}) {
  if (recipes.length === 0) return null;

  return (
    <ul
      id={listId}
      role="listbox"
      aria-label="Recipes"
      className="mb-2 overflow-hidden rounded-md border border-line bg-raised"
    >
      {recipes.map((recipe, i) => {
        const active = i === activeIndex;
        return (
          <li key={recipe.id}>
            <button
              type="button"
              id={active ? activeOptionId : undefined}
              role="option"
              aria-selected={active}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => onSelect(recipe)}
              className={`flex w-full items-baseline gap-2 px-3 py-1.5 text-left transition-ui ${
                active ? 'bg-surface-selected' : 'hover:bg-surface'
              }`}
            >
              <span className="font-mono text-sm text-ink">-{recipe.name}</span>
              <span className="ml-auto truncate text-label text-muted">
                {recipe.description || 'Custom recipe'}
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
