import { IntakeResponseCard } from '@/components/intake/intake-response-card';
import type { IntakeActionShape, IntakeResponseShape } from '@/lib/hooks/useIntake';

export interface IntakeThreadItem {
  id: string;
  response: IntakeResponseShape;
}

/** In-session submit history — no `/api/intake/history` endpoint in this batch (see plan). */
export function IntakeThread({
  items,
  onAction,
  pendingActionId,
}: {
  items: IntakeThreadItem[];
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
}) {
  return (
    <div
      className="space-y-3"
      aria-live="polite"
    >
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing submitted yet this session.</p>
      ) : (
        items.map((item) => (
          <IntakeResponseCard
            key={item.id}
            response={item.response}
            onAction={onAction}
            pendingActionId={pendingActionId}
          />
        ))
      )}
    </div>
  );
}
