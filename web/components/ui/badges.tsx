// The Two-Dialect Badge Rule (DESIGN.md): content types are OUTLINED
// (transparent + hairline + hue text), statuses are FILLED (tint + hue text).
// Single source of truth — import these everywhere a badge renders.

const CONTENT_TYPE_COLORS: Record<string, string> = {
  short: "text-type-short",
  long: "text-type-long",
  article: "text-type-article",
  repo: "text-type-repo",
};

const STATUS_COLORS: Record<string, string> = {
  done: "bg-status-done-tint text-status-done",
  pending: "bg-status-pending-tint text-status-pending",
  queued: "bg-status-pending-tint text-status-pending",
  processing: "bg-status-processing-tint text-status-processing",
  enriching: "bg-status-enriching-tint text-status-enriching",
  transcript_done: "bg-status-enriching-tint text-status-enriching",
  error: "bg-status-error-tint text-status-error",
  cancelled: "bg-status-cancelled-tint text-status-cancelled",
  // Digest-candidate statuses. Without these all three fell through to the
  // neutral "cancelled" gray, so a successfully promoted candidate looked
  // identical to a dismissed one — against DESIGN.md's rule that badge colour
  // reinforces meaning. Promoted reuses `done` because it IS the terminal
  // success here; promoting reuses the in-flight `processing` hue.
  promoting: "bg-status-processing-tint text-status-processing",
  promoted: "bg-status-done-tint text-status-done",
  dismissed: "bg-status-cancelled-tint text-status-cancelled",
};

const badgeBase = "inline-block rounded px-1.5 py-0.5 font-mono text-mono-label font-medium tracking-wider";

export function TypeBadge({ label }: { label: string }) {
  const hue = CONTENT_TYPE_COLORS[label] ?? "text-body";
  return <span className={`${badgeBase} border border-line ${hue}`}>{label}</span>;
}

export function StatusBadge({ label }: { label: string }) {
  const colors = STATUS_COLORS[label] ?? "bg-status-cancelled-tint text-status-cancelled";
  return <span className={`${badgeBase} capitalize ${colors}`}>{label.replace(/_/g, " ")}</span>;
}
