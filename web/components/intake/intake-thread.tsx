import { IntakeResponseCard } from '@/components/intake/intake-response-card';
import type { IntakeThreadItem } from '@/lib/hooks/useIntakeThread';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';

export type { IntakeThreadItem };

/**
 * Submit history for the current browser session. Persisted in
 * `sessionStorage` by `useIntakeThread` (issue #488) — there is still no
 * `/api/intake/history` endpoint, and deliberately so: this is a session
 * scratchpad, the Feed is the durable view.
 */
export function IntakeThread({
  items,
  onAction,
  pendingActionId,
  openOfferId,
  onOpenOffer,
  onSaveOffer,
}: {
  items: IntakeThreadItem[];
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
  openOfferId?: string | null;
  onOpenOffer?: (actionId: string | null) => void;
  onSaveOffer?: (action: IntakeActionShape) => Promise<void>;
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
            item={item}
            onAction={onAction}
            pendingActionId={pendingActionId}
            openOfferId={openOfferId}
            onOpenOffer={onOpenOffer}
            onSaveOffer={onSaveOffer}
          />
        ))
      )}
    </div>
  );
}
