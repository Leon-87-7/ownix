'use client';

/* @ds
name: IntakeTagOffer
purpose: The unknown-#tag follow-up inside an intake response — closed it's a "Create #tag" button, open it's TagForm rendered inline so the operator never leaves the thread.
when-not: Intake-specific; the underlying create form is TagForm (ui/), reused here rather than reimplemented.
notes: State lives entirely in the action's payload, not a server-side pending row (deliberate, ADR-0047) — don't add persistence assumptions here.
status: inferred
*/

import { TagForm, DEFAULT_COLOR } from '@/components/ui/tag-form';
import { PRESET_COLORS } from '@/components/ui/tag-picker';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';

/**
 * The unknown-`#tag` follow-up (issue #489). Closed it is a button; open it is
 * the same `TagForm` the Controls page uses, rendered inline in the card so you
 * never leave the thread.
 *
 * The offer's state is the action's `payload` — there is no server-side pending
 * row, deliberately (ADR-0047).
 */
export function IntakeTagOffer({
  action,
  open,
  onOpen,
  onCancel,
  onSave,
  index,
  total,
}: {
  action: IntakeActionShape;
  open: boolean;
  onOpen: () => void;
  onCancel: () => void;
  onSave: (values: { name: string; meaning: string; color: string; icon?: string | null }) => Promise<void>;
  /** Position among this card's offers, for the "1 more" hint. */
  index: number;
  total: number;
}) {
  const name = String(action.payload?.tag_name ?? '');
  const remaining = total - index - 1;

  if (!open) {
    return (
      <button
        type="button"
        onClick={onOpen}
        className="h-8 rounded-md border border-line bg-raised px-3 text-sm font-medium text-ink transition-ui hover:border-signal hover:text-signal"
      >
        {action.label ?? `Create #${name}`}
      </button>
    );
  }

  return (
    <div className="mt-3 w-full rounded-md border border-line bg-canvas p-3">
      <p className="mb-3 font-mono text-label text-muted">
        New tag <span className="text-ink">#{name}</span>
        {remaining > 0 && ` — ${remaining} more after this`}
      </p>
      <TagForm
        initial={{
          name,
          meaning: '',
          // Give each new tag its own hue rather than the schema default: tags
          // render as name-less colour dots, so repeated defaults are
          // indistinguishable (CONTEXT.md "Link tag").
          color: PRESET_COLORS[index % PRESET_COLORS.length] ?? DEFAULT_COLOR,
          icon: null,
        }}
        submitLabel="Create tag"
        onCancel={onCancel}
        onSubmit={onSave}
      />
    </div>
  );
}
