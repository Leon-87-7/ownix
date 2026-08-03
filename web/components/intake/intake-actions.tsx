'use client';

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
