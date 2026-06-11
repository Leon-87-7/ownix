import { StatCard } from "@/components/stat-card";

export interface FeedStats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
}

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
      <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard label="Short" value={stats.by_content_type.short ?? 0} />
        <StatCard label="Long" value={stats.by_content_type.long ?? 0} />
        <StatCard label="Article" value={stats.by_content_type.article ?? 0} />
        <StatCard label="Repo" value={stats.by_content_type.repo ?? 0} />
      </div>
    </section>
  );
}
