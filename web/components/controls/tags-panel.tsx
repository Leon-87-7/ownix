'use client';

import { useEffect, useRef, useState } from 'react';
import { Pin, PinOff, TagPlus } from 'lucide-react';
import { TagMark } from '@/components/ui/tag-picker';
import { Tooltip } from '@/components/ui/tooltip';
import { TagForm, DEFAULT_COLOR } from '@/components/ui/tag-form';
import { describeError } from '@/lib/fetch-utils';
import { useTagList } from '@/lib/hooks/useTagList';
import type { Tag, TagFormState } from '@/lib/hooks/useTagList';

function TagPill({
  tag,
  count,
  editing,
  onClick,
  onTogglePin,
}: {
  tag: Tag;
  count?: number;
  editing: boolean;
  onClick: () => void;
  onTogglePin: () => void;
}) {
  return (
    <li
      className={`inline-flex items-center gap-0.5 rounded-full border bg-raised pr-1 text-xs font-medium text-ink transition-ui hover:border-line-strong ${editing ? 'border-line ring-1 ring-signal-deep' : 'border-line'}`}
    >
      <Tooltip content={tag.meaning || undefined}>
        <button
          type="button"
          onClick={onClick}
          aria-pressed={editing}
          aria-label={`Edit ${tag.name}`}
          className="inline-flex items-center gap-1.5 rounded-full py-1 pl-2.5 pr-1.5"
        >
          <TagMark tag={tag} className="h-3 w-3" />
          {tag.name}
        </button>
      </Tooltip>
      {count !== undefined && (
        <Tooltip content={`${count} ${count === 1 ? 'job' : 'jobs'} tagged`}>
          <span
            aria-label={`${count} ${count === 1 ? 'job' : 'jobs'} tagged`}
            className="font-mono text-mono-label tabular-nums text-muted"
          >
            {count}
          </span>
        </Tooltip>
      )}
      <Tooltip content={tag.pinned ? 'Unpin from GoTo' : 'Pin for GoTo'}>
        <button
          type="button"
          onClick={onTogglePin}
          aria-pressed={Boolean(tag.pinned)}
          aria-label={
            tag.pinned
              ? `Unpin ${tag.name} from GoTo`
              : `Pin ${tag.name} for GoTo`
          }
          className={`rounded-full p-1 transition-ui hover:bg-surface ${tag.pinned ? 'text-signal' : 'text-muted'}`}
        >
          {tag.pinned ? (
            <Pin className="h-3 w-3" aria-hidden="true" />
          ) : (
            <PinOff className="h-3 w-3" aria-hidden="true" />
          )}
        </button>
      </Tooltip>
    </li>
  );
}

export function TagsPanel() {
  const {
    tags,
    loading,
    fetchError,
    createTag,
    deleteTag,
    updateTag,
    toggleTagPinned,
  } = useTagList();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | undefined>();
  const [pinError, setPinError] = useState<string | undefined>();
  const [tagCounts, setTagCounts] = useState<Record<string, number>>({});
  const editingTag = tags.find((t) => t.id === editingId) ?? null;
  const editPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch('/api/jobs/stats')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { by_tag?: Record<string, number> } | null) => {
        if (data?.by_tag) setTagCounts(data.by_tag);
      })
      .catch(() => {});
  }, []);

  // Detached edit panel can render off-screen (fixed slot, not inline at the
  // clicked pill), so pull it into view whenever the edit target changes.
  useEffect(() => {
    if (editingTag) {
      // jsdom doesn't implement scrollIntoView (undefined in tests).
      editPanelRef.current?.scrollIntoView?.({
        behavior: 'smooth',
        block: 'nearest',
      });
    }
  }, [editingTag]);

  const selectForEdit = (tagId: string) => {
    setDeleteError(undefined);
    setEditingId((current) => (current === tagId ? null : tagId));
  };

  const handleSave = async (values: TagFormState) => {
    if (!editingTag) return;
    await updateTag(editingTag.id, values);
    setEditingId(null);
  };

  const handleDelete = async () => {
    if (!editingTag) return;
    if (!confirm(`Delete tag "${editingTag.name}"?`)) return;
    setDeleteError(undefined);
    try {
      await deleteTag(editingTag.id);
      setEditingId(null);
    } catch (err) {
      setDeleteError(describeError(err, 'Delete failed'));
    }
  };

  const handleTogglePin = async (tag: Tag) => {
    setPinError(undefined);
    try {
      await toggleTagPinned(tag.id, !tag.pinned);
    } catch (err) {
      setPinError(describeError(err, 'Pin failed'));
    }
  };

  return (
    <div className="space-y-4">
      {/* ponytail: native <details>, open by default. Mobile = collapsible
          "Create tag" disclosure; desktop hides the summary entirely → plain card. */}
      <details open className="group">
        <summary className="flex cursor-pointer list-none items-center justify-between p-4 text-sm font-semibold text-ink [&::-webkit-details-marker]:hidden sm:hidden">
          Create tag
          <TagPlus className="h-4 w-4 text-muted" aria-hidden="true" />
        </summary>
        <div className="border-t border-line p-4 sm:border-t-0">
          <TagForm
            initial={{ name: '', meaning: '', color: DEFAULT_COLOR }}
            onSubmit={createTag}
            submitLabel="Create"
          />
        </div>
      </details>
      {editingTag && (
        <div
          ref={editPanelRef}
          className="rounded-lg border border-line bg-surface px-4 py-3"
        >
          <TagForm
            key={editingTag.id}
            initial={{
              name: editingTag.name,
              meaning: editingTag.meaning,
              color: editingTag.color,
              // Carried through the form untouched so saving an edit doesn't NULL it.
              icon: editingTag.icon,
            }}
            onSubmit={handleSave}
            onCancel={() => setEditingId(null)}
            submitLabel="Save"
            onDelete={handleDelete}
          />
          {deleteError && (
            <p role="alert" className="mt-2 text-xs text-status-error">
              {deleteError}
            </p>
          )}
        </div>
      )}
      <div className="space-y-2">
        {loading && <p className="text-sm text-body">Loading tags…</p>}
        {fetchError && (
          <p role="alert" className="text-sm text-status-error">
            {fetchError}
          </p>
        )}
        {!loading && !fetchError && tags.length === 0 && (
          <p className="text-sm text-muted">No tags yet. Create one above.</p>
        )}
        <ul className="flex flex-wrap justify-center gap-2">
          {tags.map((tag) => (
            <TagPill
              key={tag.id}
              tag={tag}
              count={tagCounts[tag.id]}
              editing={tag.id === editingId}
              onClick={() => selectForEdit(tag.id)}
              onTogglePin={() => {
                void handleTogglePin(tag);
              }}
            />
          ))}
        </ul>
        {pinError && (
          <p role="alert" className="text-xs text-status-error">
            {pinError}
          </p>
        )}
      </div>
    </div>
  );
}
