'use client';

import { useState, useEffect } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { CornerDownLeft } from 'lucide-react';
import type { TagFormState } from '@/lib/hooks/useTagList';

interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
}

// Two-row preset palette (vibrant row + soft row) — no free-form color picker.
export const PRESET_COLORS = [
  '#9ca3af',
  '#7f1d1d',
  '#ef4444',
  '#f97316',
  '#eab308',
  '#22c55e',
  '#38bdf8',
  '#3b82f6',
  '#6366f1',
  '#d1d5db',
  '#a16207',
  '#ec4899',
  '#fbcfe8',
  '#fcd34d',
  '#fef3c7',
  '#a3e635',
  '#bae6fd',
  '#c7d2fe',
];
const DEFAULT_COLOR = '#6366f1';

function Check({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

/**
 * Dropdown checkbox menu of all tags (Radix — the panel is portaled to <body>,
 * so it escapes feed-card stacking contexts instead of bleeding behind siblings).
 * A checkmark marks each attached tag; clicking a row toggles attach/detach and
 * keeps the menu open. "New tag…" opens the create modal.
 */
export function TagMenu({
  jobTags,
  allTags,
  onToggle,
  onCreate,
}: {
  jobTags: TagSummary[];
  allTags: TagSummary[];
  onToggle: (tagId: string, attached: boolean) => void;
  onCreate: (values: TagFormState) => Promise<void>;
}) {
  const [creating, setCreating] = useState(false);
  const attached = new Set(jobTags.map((t) => t.id));

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label="Tags"
            className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas data-[state=open]:border-line-strong data-[state=open]:text-ink"
          >
            Tags
            {jobTags.length > 0 && (
              <span className="font-mono text-signal">{jobTags.length}</span>
            )}
            <CornerDownLeft className="h-3 w-3" />
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            align="end"
            sideOffset={4}
            className="z-50 w-52 overflow-hidden rounded-md border border-line bg-surface shadow-lg"
          >
            <div className="max-h-60 overflow-auto p-1">
              {allTags.length === 0 && (
                <p className="px-2 py-1.5 text-xs text-muted">
                  No tags yet.
                </p>
              )}
              {allTags.map((tag) => {
                const isOn = attached.has(tag.id);
                return (
                  <DropdownMenu.CheckboxItem
                    key={tag.id}
                    checked={isOn}
                    onCheckedChange={() => onToggle(tag.id, isOn)}
                    onSelect={(e) => e.preventDefault()}
                    title={tag.meaning || undefined}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-xs text-body outline-none transition-ui data-[highlighted]:bg-raised data-[highlighted]:text-ink"
                  >
                    <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center text-signal">
                      {isOn && <Check className="h-3.5 w-3.5" />}
                    </span>
                    <span
                      className="inline-block h-2 w-2 shrink-0 rounded-full"
                      style={{ backgroundColor: tag.color }}
                    />
                    <span className="truncate">{tag.name}</span>
                  </DropdownMenu.CheckboxItem>
                );
              })}
            </div>
            <DropdownMenu.Item
              onSelect={() => setCreating(true)}
              className="flex cursor-pointer items-center gap-2 border-t border-line px-3 py-2 text-xs font-medium text-body outline-none transition-ui data-[highlighted]:bg-raised data-[highlighted]:text-ink"
            >
              <span
                aria-hidden="true"
                className="text-sm leading-none"
              >
                +
              </span>{' '}
              New tag…
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      {creating && (
        <CreateTagModal
          onCreate={onCreate}
          onClose={() => setCreating(false)}
        />
      )}
    </>
  );
}

/** Dense create-tag modal with a preset-swatch color picker. */
function CreateTagModal({
  onCreate,
  onClose,
}: {
  onCreate: (values: TagFormState) => Promise<void>;
  onClose: () => void;
}) {
  const [name, setName] = useState('');
  const [meaning, setMeaning] = useState('');
  const [color, setColor] = useState(DEFAULT_COLOR);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(undefined);
    try {
      await onCreate({ name, meaning, color });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  const inputCls =
    'w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Create tag"
        className="relative z-10 w-full max-w-md rounded-lg border border-line bg-surface p-5 shadow-xl"
      >
        <h2 className="mb-4 text-sm font-semibold text-ink">
          Create tag
        </h2>
        <form
          onSubmit={handleSubmit}
          className="space-y-3"
        >
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="flex flex-1 flex-col gap-1">
              <label className="text-xs font-medium text-body">
                Name
              </label>
              {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
              <input
                autoFocus
                type="text"
                required
                maxLength={80}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Tag name"
                className={inputCls}
              />
            </div>
            <div className="flex flex-[1.4] flex-col gap-1">
              <label className="text-xs font-medium text-body">
                Meaning
              </label>
              <input
                type="text"
                maxLength={500}
                value={meaning}
                onChange={(e) => setMeaning(e.target.value)}
                placeholder="What this tag means…"
                className={inputCls}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-body">
              Color
            </label>
            <div className="mx-auto grid w-fit grid-cols-6 gap-2 p-2 sm:grid-cols-9">
              {PRESET_COLORS.map((c) => {
                const selected = c === color;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    aria-label={`Color ${c}`}
                    aria-pressed={selected}
                    className={`h-6 w-6 rounded-full transition-ui ${selected ? 'ring-2 ring-signal ring-offset-2 ring-offset-surface' : 'hover:scale-110'}`}
                    style={{ backgroundColor: c }}
                  />
                );
              })}
            </div>
          </div>
          {error && (
            <p className="text-xs text-status-error">{error}</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="h-8 rounded-md px-3.5 text-[13px] font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
            >
              {submitting ? 'Creating…' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/** Attached tags rendered as removable colored chips. */
export function TagChips({
  jobTags,
  onRemove,
}: {
  jobTags: TagSummary[];
  onRemove: (tagId: string) => void;
}) {
  // Bare flex items (no wrapper) so chips align inline with a sibling dropdown.
  return (
    <>
      {jobTags.map((tag) => (
        <span
          key={tag.id}
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-xs font-medium text-ink"
          title={tag.meaning || undefined}
        >
          <span
            className="inline-block h-2 w-2 shrink-0 rounded-full"
            style={{ backgroundColor: tag.color }}
          />
          {tag.name}
          <button
            type="button"
            onClick={() => onRemove(tag.id)}
            className="ml-0.5 rounded-full text-muted transition-ui hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-1 focus-visible:ring-offset-canvas"
            aria-label={`Remove tag ${tag.name}`}
          >
            &times;
          </button>
        </span>
      ))}
    </>
  );
}
