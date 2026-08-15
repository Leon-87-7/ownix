'use client';

/* @ds
name: TagForm
purpose: The standalone tag create/edit form — name, meaning, color, icon — used inline on the Controls page and in the Intake console's inline tag offer.
when-not: For the compact attach/detach dropdown with its own inline create step, use TagMenu (tag-picker.tsx) instead.
notes: Shares PRESET_COLORS + IconPicker with tag-picker.tsx but is a separate form implementation from TagMenu's CreateTagModal — a known duplication, not unified here (DRIFT-BACKLOG.md).
status: inferred
*/

/**
 * The tag editor. Lifted out of the Controls page (issue #489) so the Intake
 * console can render the same form inline in a card when a `#tag` token names
 * a tag that doesn't exist yet — one editor, two surfaces, no fork.
 */

import { useState } from 'react';

import { PRESET_COLORS, IconPicker } from '@/components/ui/tag-picker';
import { TagX } from 'lucide-react';
import type { TagFormState } from '@/lib/hooks/useTagList';

export const DEFAULT_COLOR = '#8b5cf6';

export function TagForm({
  initial,
  onSubmit,
  onCancel,
  submitLabel,
  onDelete,
}: {
  initial: TagFormState;
  onSubmit: (values: TagFormState) => Promise<void>;
  onCancel?: () => void;
  submitLabel: string;
  onDelete?: () => void;
}) {
  const [values, setValues] = useState<TagFormState>(initial);
  const [submitting, setSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | undefined>();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setLocalError(undefined);
    try {
      await onSubmit(values);
    } catch (err: unknown) {
      setLocalError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  const inputCls =
    'w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none';

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
    >
      {localError && (
        <p className="text-xs text-status-error">{localError}</p>
      )}
      {/* ponytail: 2 cols on desktop, stacked on mobile. Left = Name+Meaning
          grouped tight; right = Color with the buttons sharing the swatch row. */}
      <div className="grid gap-4 sm:grid-cols-2 sm:gap-8">
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-body">
              Name
            </span>
            <input
              type="text"
              required
              autoFocus={Boolean(onCancel)}
              maxLength={80}
              value={values.name}
              onChange={(e) =>
                setValues((v) => ({ ...v, name: e.target.value }))
              }
              placeholder="Tag name"
              className={`${inputCls} min-w-0 flex-1`}
            />
          </label>
          <label className="flex items-center gap-2">
            <span className="w-16 shrink-0 text-xs font-medium text-body">
              Meaning
            </span>
            <input
              type="text"
              maxLength={500}
              value={values.meaning}
              onChange={(e) =>
                setValues((v) => ({ ...v, meaning: e.target.value }))
              }
              placeholder="What this tag means…"
              className={`${inputCls} min-w-0 flex-1`}
            />
          </label>
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="text-xs font-medium text-body">
            Color
          </label>
          <div className="grid w-fit grid-cols-6 gap-2 sm:grid-cols-9">
            {PRESET_COLORS.map((c) => {
              const selected = c === values.color;
              return (
                <button
                  key={c}
                  type="button"
                  onClick={() =>
                    setValues((v) => ({ ...v, color: c }))
                  }
                  aria-label={`Color ${c}`}
                  aria-pressed={selected}
                  className={`h-6 w-6 rounded-full transition-ui ${selected ? 'ring-2 ring-signal ring-offset-2 ring-offset-surface' : 'hover:scale-110'}`}
                  style={{ backgroundColor: c }}
                />
              );
            })}
          </div>
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <label className="text-xs font-medium text-body">
          Icon (optional)
        </label>
        <IconPicker
          value={values.icon}
          color={values.color}
          onSelect={(icon) => setValues((v) => ({ ...v, icon }))}
        />
      </div>
      <div className="flex items-center justify-end gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
        >
          {submitting ? 'Saving…' : submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="h-8 rounded-md px-3.5 text-button font-medium text-muted transition-ui hover:bg-raised hover:text-ink"
          >
            Cancel
          </button>
        )}
        {onDelete && (
          <button
            type="button"
            onClick={onDelete}
            aria-label={`Delete ${values.name}`}
            className="rounded p-1.5 text-status-error transition-ui hover:bg-raised"
          >
            <TagX
              className="h-4 w-4"
              aria-hidden="true"
            />
          </button>
        )}
      </div>
    </form>
  );
}

