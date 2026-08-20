import { IntakeResponseCard } from '@/components/intake/intake-response-card';
import type { IntakeThreadItem } from '@/lib/hooks/useIntakeThread';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';

export type { IntakeThreadItem };

/**
 * Submit history across browser sessions. Persisted in `localStorage` by
 * `useIntakeThread` (issue #488) — there is still no `/api/intake/history`
 * endpoint, and deliberately so: this is a local log, the Feed is the
 * durable per-job view. Cleared only when the user asks, via `onClear`.
 */
export function IntakeThread({
  items,
  onAction,
  pendingActionId,
  openOfferId,
  onOpenOffer,
  onSaveOffer,
  onClear,
}: {
  items: IntakeThreadItem[];
  onAction?: (action: IntakeActionShape) => void;
  pendingActionId?: string | null;
  openOfferId?: string | null;
  onOpenOffer?: (actionId: string | null) => void;
  onSaveOffer?: (action: IntakeActionShape) => Promise<void>;
  onClear?: () => void;
}) {
  return (
    <div
      className="space-y-3"
      aria-live="polite"
    >
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing submitted yet.</p>
      ) : (
        <>
          {onClear && (
            <div className="flex justify-end">
              <button
                type="button"
                onClick={() => {
                  if (window.confirm("Clear your intake history? This can't be undone.")) onClear();
                }}
                className="text-sm font-medium text-muted transition-ui hover:text-status-error"
              >
                Clear history
              </button>
            </div>
          )}
          {items.map((item) => (
            <IntakeResponseCard
              key={item.id}
              item={item}
              onAction={onAction}
              pendingActionId={pendingActionId}
              openOfferId={openOfferId}
              onOpenOffer={onOpenOffer}
              onSaveOffer={onSaveOffer}
            />
          ))}
        </>
      )}
    </div>
  );
}
