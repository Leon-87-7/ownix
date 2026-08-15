'use client';

/* @ds
name: FolderTagForm
purpose: A Dialog listing folders detected in a Bookmark import, letting the operator turn each into a link tag (with color/icon) applied across every link from that folder.
when-not: Bookmark-import-specific — not a general tag-creation surface (use TagForm/TagMenu for that). Non-blocking: dismissing writes nothing, since the source folder names already persisted at import time.
notes: Reuses IconPicker/PRESET_COLORS from tag-picker.tsx rather than duplicating the swatch UI.
status: inferred
*/

import { useEffect, useState } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { IconPicker, PRESET_COLORS, TagMark } from '@/components/ui/tag-picker';
import { useFolderTagForm } from '@/lib/hooks/useFolderTagForm';

/**
 * #497: shown after a Bookmark import's links are already visible, never
 * blocking them — the trigger lives on the job detail page, opened whenever
 * the operator wants. Dismissing writes nothing; the underlying `topic`
 * column already persisted every folder name at import, so this is safe to
 * re-open any time from the same trigger (CONTEXT.md "Bookmark import").
 */
export function FolderTagForm({
  jobId,
  open,
  onOpenChange,
}: {
  jobId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { assignments, loading, error, submitting, load, toggle, setColor, setIcon, confirm } =
    useFolderTagForm(jobId);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setExpanded(null);
      void load();
    }
  }, [open, load]);

  const checkedCount = assignments.filter((a) => a.checked).length;

  async function handleConfirm() {
    const ok = await confirm();
    if (ok) onOpenChange(false);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
    >
        <DialogContent className="max-w-lg">
          <DialogTitle>Create tags from folders</DialogTitle>
        {!loading && (
          <p className="mt-1 text-sm text-body">
            {assignments.length} folder{assignments.length === 1 ? '' : 's'} found
            in this import. Each becomes a link tag, applied to every link in
            that folder.
          </p>
        )}

        {loading && (
          <p className="mt-4 text-sm text-muted">Loading folders…</p>
        )}

        {!loading && assignments.length === 0 && !error && (
          <p className="mt-4 text-sm text-muted">
            No folders on these links.
          </p>
        )}

        {error && (
          <p
            role="alert"
            className="mt-4 text-sm text-status-error"
          >
            {error}
          </p>
        )}

        {!loading && assignments.length > 0 && (
          <ul className="mt-4 max-h-96 space-y-1 overflow-y-auto">
            {assignments.map((a) => {
              const isExpanded = expanded === a.topic;
              return (
                <li
                  key={a.topic}
                  className="rounded-md border border-line bg-canvas px-3 py-2"
                >
                  <div className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={a.checked}
                      onChange={() => toggle(a.topic)}
                      aria-label={`Include ${a.topic}`}
                      className="shrink-0"
                    />
                    <span className="min-w-0 flex-1 truncate text-sm text-ink">
                      {a.topic}
                    </span>
                    <span className="shrink-0 font-mono text-xs text-muted">
                      {a.count}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setExpanded(isExpanded ? null : a.topic)
                      }
                      aria-expanded={isExpanded}
                      aria-label={`Change color and icon for ${a.topic}`}
                      className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line transition-ui hover:border-line-strong"
                      style={{ backgroundColor: `${a.color}22` }}
                    >
                      <TagMark
                        tag={{
                          id: '',
                          name: a.topic,
                          color: a.color,
                          meaning: '',
                          icon: a.icon,
                        }}
                        className="h-3.5 w-3.5"
                      />
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 space-y-3 border-t border-line pt-3">
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-body">
                          Color
                        </p>
                        <div className="grid w-fit grid-cols-6 gap-2 sm:grid-cols-9">
                          {PRESET_COLORS.map((c) => {
                            const selected = c === a.color;
                            return (
                              <button
                                key={c}
                                type="button"
                                onClick={() => setColor(a.topic, c)}
                                aria-label={`Color ${c}`}
                                aria-pressed={selected}
                                className={`h-6 w-6 rounded-full transition-ui ${selected ? 'ring-2 ring-signal ring-offset-2 ring-offset-canvas' : 'motion-safe:hover:scale-110'}`}
                                style={{ backgroundColor: c }}
                              />
                            );
                          })}
                        </div>
                      </div>
                      <div>
                        <p className="mb-1.5 text-xs font-medium text-body">
                          Icon
                        </p>
                        <IconPicker
                          value={a.icon || null}
                          color={a.color}
                          onSelect={(icon) => setIcon(a.topic, icon)}
                        />
                      </div>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}

        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised"
          >
            Skip
          </button>
          <button
            type="button"
            disabled={submitting || checkedCount === 0}
            onClick={handleConfirm}
            className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:cursor-not-allowed disabled:bg-surface disabled:text-muted"
          >
            {submitting
              ? 'Creating…'
              : `Create ${checkedCount || ''} Tag${checkedCount === 1 ? '' : 's'}`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
