import { StatCard } from "@/components/stat-card";
import type { FeedStats } from "@/lib/hooks/useFeedData";

export function StatsOverview({ stats }: { stats: FeedStats }) {
  return (
    <section className="mt-6">
      <h2 className="mb-3 text-base font-semibold text-ink">Overview</h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard label="Total" value={stats.total} />
        <StatCard label="Done" value={stats.by_status.done ?? 0} valueClass="text-status-done" />
        <StatCard label="Pending" value={stats.by_status.pending ?? 0} valueClass="text-status-pending" />
        <StatCard label="Error" value={stats.by_status.error ?? 0} valueClass="text-status-error" />
        <StatCard
          label="Processing"
          value={(stats.by_status.processing ?? 0) + (stats.by_status.enriching ?? 0) + (stats.by_status.transcript_done ?? 0)}
          valueClass="text-status-processing"
        />
      </div>
    </section>
  );
}
