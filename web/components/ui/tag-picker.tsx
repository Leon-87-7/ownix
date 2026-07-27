'use client';

import { useState, type ReactNode } from 'react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import {
  CornerDownLeft,
  Brain,
  Code2,
  Database,
  FileText,
  Globe,
  Lightbulb,
  Link2,
  type LucideIcon,
  Cog,
  HatGlasses,
  PawPrint,
  ChessPawn,
  Anvil,
  Brush,
  Paintbrush,
  Container,
  PackageOpen,
} from 'lucide-react';
import type { TagFormState } from '@/lib/hooks/useTagList';
import { Tooltip } from '@/components/ui/tooltip';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';

interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
  icon?: string | null;
}

// Hue-ordered global tag colors. All pass >=3:1 non-text contrast against
// #0d0e10, #16181c, and #202329.
export const PRESET_COLORS = [
  '#f87171', // red
  '#fb923c', // orange
  '#facc15', // yellow
  '#4ade80', // green
  '#2dd4bf', // cyan-green
  '#22d3ee', // cyan
  '#60a5fa', // blue
  '#8b5cf6', // purple
  '#c084fc', // violet
  '#f472b6', // pink
  '#a16207', // brown
  '#f4f1eb', // white
];
const DEFAULT_COLOR = '#8b5cf6';

const TAG_ICONS: Record<string, LucideIcon> = {
  Brain,
  Code2,
  Database,
  PackageOpen,
  FileText,
  Globe,
  Lightbulb,
  Link2,
  Cog,
  HatGlasses,
  PawPrint,
  Paintbrush,
  ChessPawn,
  Anvil,
  Brush,
  Container,
};
const TAG_ICON_NAMES = Object.keys(TAG_ICONS);

export function TagMark({
  tag,
  className = 'h-2 w-2',
}: {
  tag: TagSummary;
  className?: string;
}) {
  const Icon = tag.icon ? TAG_ICONS[tag.icon] : undefined;
  return Icon ? (
    <Icon
      className={className}
      style={{ color: tag.color }}
      aria-hidden="true"
    />
  ) : (
    <span
      className={`inline-block shrink-0 rounded-full ${className}`}
      style={{ backgroundColor: tag.color }}
    />
  );
}

/** Shared "None" + swatch-button icon grid used by every tag create/edit form. */
export function IconPicker({
  value,
  color,
  onSelect,
}: {
  value: string | null | undefined;
  color: string;
  onSelect: (icon: string | undefined) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button
        type="button"
        onClick={() => onSelect(undefined)}
        aria-pressed={!value}
        className={`rounded border px-2 py-1 text-xs ${!value ? 'border-signal text-ink' : 'border-line text-muted'}`}
      >
        None
      </button>
      {TAG_ICON_NAMES.map((name) => {
        const Icon = TAG_ICONS[name];
        return (
          <button
            key={name}
            type="button"
            onClick={() => onSelect(name)}
            aria-label={`Icon ${name}`}
            aria-pressed={value === name}
            className={`rounded border p-1.5 ${value === name ? 'border-signal' : 'border-line'}`}
          >
            <Icon
              className="h-4 w-4"
              style={{ color }}
            />
          </button>
        );
      })}
    </div>
  );
}

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
  trigger,
}: {
  jobTags: TagSummary[];
  allTags: TagSummary[];
  onToggle: (tagId: string, attached: boolean) => void;
  onCreate: (values: TagFormState) => Promise<void>;
  trigger?: ReactNode;
}) {
  const [creating, setCreating] = useState(false);
  const attached = new Set(jobTags.map((t) => t.id));

  return (
    <>
      {/* modal={false}: the create Dialog mounts while this menu unmounts; with
          both modal, Radix's body pointer-events lock can stick after close
          (page freezes on mobile). Non-modal menu → only the Dialog locks. */}
      <DropdownMenu.Root modal={false}>
        <DropdownMenu.Trigger asChild>
          {trigger ?? (
            <button
              type="button"
              aria-label="Tags"
              className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas data-[state=open]:border-line-strong data-[state=open]:text-ink"
            >
              Tags
              {jobTags.length > 0 && (
                <span className="font-mono text-signal">
                  {jobTags.length}
                </span>
              )}
              <CornerDownLeft className="h-3 w-3" />
            </button>
          )}
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
                    <TagMark
                      tag={tag}
                      className="h-3.5 w-3.5"
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
  const [icon, setIcon] = useState<string>('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | undefined>();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(undefined);
    try {
      await onCreate({
        name,
        meaning,
        color,
        icon: icon || undefined,
      });
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
      setSubmitting(false);
    }
  }

  const inputCls =
    'w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none';

  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent>
        <DialogTitle>Create tag</DialogTitle>
        <form
          onSubmit={handleSubmit}
          className="mt-4 space-y-3"
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
            <div className="mx-auto grid w-fit grid-cols-6 gap-1.5 p-2 sm:grid-cols-9">
              {PRESET_COLORS.map((c) => {
                const selected = c === color;
                return (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setColor(c)}
                    aria-label={`Color ${c}`}
                    aria-pressed={selected}
                    className={`h-5 w-5 rounded-full transition-ui ${selected ? 'ring-2 ring-signal ring-offset-1 ring-offset-surface' : 'hover:scale-110'}`}
                    style={{ backgroundColor: c }}
                  />
                );
              })}
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-body">
              Icon (optional)
            </label>
            <IconPicker
              value={icon}
              color={color}
              onSelect={(next) => setIcon(next ?? '')}
            />
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
      </DialogContent>
    </Dialog>
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
        <Tooltip
          key={tag.id}
          content={tag.meaning || undefined}
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-xs font-medium text-ink">
            <TagMark
              tag={tag}
              className="h-3 w-3"
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
        </Tooltip>
      ))}
    </>
  );
}
