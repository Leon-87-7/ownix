'use client';

/* @ds
name: IntakeActions
purpose: Renders an intake response's plain action buttons — the dashboard's equivalent of Telegram's inline keyboards.
when-not: create_tag actions are filtered out before reaching this component and rendered as IntakeTagOffer instead — don't route them here.
notes: All buttons disable together while any one action_id is pending (single in-flight action per card, not per-button).
status: inferred
*/

import type { IntakeActionShape } from '@/lib/hooks/useIntake';

/** Real dashboard buttons standing in for Telegram inline keyboards (issue #475). */
export function IntakeActions({
  actions,
  onAction,
  pendingActionId,
}: {
  actions: IntakeActionShape[];
  onAction: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
}) {
  if (actions.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {actions.map((action) => (
        <button
          key={action.action_id}
          type="button"
          disabled={Boolean(pendingActionId)}
          onClick={() => onAction(action)}
          className="h-8 rounded-md border border-line bg-raised px-3 text-sm font-medium text-ink transition-ui hover:border-signal hover:text-signal disabled:opacity-50"
        >
          {pendingActionId === action.action_id ? 'Applying…' : (action.label ?? action.kind)}
        </button>
      ))}
    </div>
  );
}
