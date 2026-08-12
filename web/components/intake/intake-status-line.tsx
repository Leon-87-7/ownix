import { StatusBadge } from '@/components/ui/badges';

/** Statuses that mean "still working" — mirrors `useIntakeThread`. */
const IN_FLIGHT = new Set([
  'pending',
  'queued',
  'processing',
  'transcript_done',
  'enriching',
]);

const STATUS_LABEL: Record<string, string> = {
  pending: 'Queued',
  queued: 'Queued',
  processing: 'Processing',
  transcript_done: 'Transcript ready',
  enriching: 'Enriching',
  done: 'Done',
  error: 'Failed',
  cancelled: 'Cancelled',
};

/**
 * The in-flight line on an intake card (issue #481). Two independent channels,
 * so neither has to encode both facts: the shimmer says *alive*, the
 * `StatusBadge` beside it says *where*.
 *
 * No stepper and no percentage — nothing in the system measures progress, and
 * the stage count differs per content type (short/article/document skip the
 * intermediate states), so a bar would render fiction as fact. See CONTEXT.md
 * "Intake console".
 */
export function IntakeStatusLine({ status }: { status: string }) {
  const inFlight = IN_FLIGHT.has(status);
  const label = STATUS_LABEL[status] ?? status.replace(/_/g, ' ');

  return (
    <div className="mt-2 flex items-center gap-2">
      <span
        // `text-body` is the reduced-motion fallback: `.ownix-shimmer` only
        // takes effect under `prefers-reduced-motion: no-preference`.
        className={`font-mono text-label text-body ${inFlight ? 'ownix-shimmer' : ''}`}
      >
        {label}
        {inFlight ? '…' : ''}
      </span>
      <StatusBadge label={status} />
    </div>
  );
}
