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
import { TagForm } from '@/components/ui/tag-form';

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
export const TAG_ICON_NAMES = Object.keys(TAG_ICONS);

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

/** Create-tag modal — reuses the same editor as the Controls page and Intake console. */
function CreateTagModal({
  onCreate,
  onClose,
}: {
  onCreate: (values: TagFormState) => Promise<void>;
  onClose: () => void;
}) {
  return (
    <Dialog
      open
      onOpenChange={(open) => !open && onClose()}
    >
      <DialogContent>
        <DialogTitle>Create tag</DialogTitle>
        <div className="mt-4">
          <TagForm
            initial={{ name: '', meaning: '', color: DEFAULT_COLOR }}
            onSubmit={async (values) => {
              await onCreate(values);
              onClose();
            }}
            onCancel={onClose}
            submitLabel="Create"
          />
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** Attached tags rendered as removable colored chips.
 *
 * `compact` (feed cards on phones): keep the icon, but clamp the name to its
 * first 3 characters on mobile; the full name returns at the `sm` breakpoint.
 * The meaning tooltip still carries the full name for the truncated case.
 */
export function TagChips({
  jobTags,
  onRemove,
  compact = false,
}: {
  jobTags: TagSummary[];
  onRemove: (tagId: string) => void;
  compact?: boolean;
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
            {compact ? (
              <>
                <span
                  className="sm:hidden"
                  aria-hidden="true"
                >
                  {tag.name.slice(0, 3)}
                </span>
                <span className="hidden sm:inline" aria-hidden="true">
                  {tag.name}
                </span>
                <span className="sr-only">{tag.name}</span>
              </>
            ) : (
              tag.name
            )}
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
