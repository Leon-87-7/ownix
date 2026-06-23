import { StatCard } from "@/components/stat-card";
import type { FeedStats } from "@/lib/hooks/useFeedData";

// Total card label reflects the active content-type tab ("" = All).
const TOTAL_LABELS: Record<string, string> = {
  short: "Total Shorts",
  long: "Total Long",
  article: "Total Articles",
  repo: "Total Repos",
};

export function StatsOverview({ stats, contentType = "" }: { stats: FeedStats; contentType?: string }) {
  const totalLabel = contentType ? (TOTAL_LABELS[contentType] ?? `Total ${contentType}`) : "Total";
  const done = stats.by_status.done ?? 0;
  const pending = stats.by_status.pending ?? 0;
  const error = stats.by_status.error ?? 0;
  const processing =
    (stats.by_status.processing ?? 0) +
    (stats.by_status.enriching ?? 0) +
    (stats.by_status.transcript_done ?? 0);

  return (
    <section className="mt-5" aria-label="Overview">
      {/* Mobile (#185): one compact inline row instead of the card grid (~100px shorter).
          The T/D/P/E letters are decorative — screen readers get the spoken summary. */}
      <div className="sm:hidden">
        <p className="sr-only">
          Total {stats.total}, done {done}, pending {pending}, error {error}
        </p>
        <div aria-hidden="true" className="flex items-center gap-3 font-mono text-[12px] tabular-nums">
          <span className="text-muted">T <span className="text-ink">{stats.total}</span></span>
          <span className="text-muted">D <span className="text-status-done">{done}</span></span>
          <span className="text-muted">P <span className="text-status-pending">{pending}</span></span>
          <span className="text-muted">E <span className="text-status-error">{error}</span></span>
        </div>
      </div>
      <div className="hidden grid-cols-2 gap-3 sm:grid sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label={totalLabel} value={stats.total} />
        <StatCard label="Done" value={done} valueClass="text-status-done" />
        <StatCard label="Pending" value={pending} valueClass="text-status-pending" />
        <StatCard label="Error" value={error} valueClass="text-status-error" />
        <StatCard label="Processing" value={processing} valueClass="text-status-processing" />
      </div>
    </section>
  );
}
