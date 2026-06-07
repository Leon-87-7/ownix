"use client";

import { useFeedData } from "@/lib/hooks/useFeedData";
import { useFuseSearch } from "@/lib/hooks/useFuseSearch";
import { useInFlightPolling } from "@/lib/hooks/useInFlightPolling";
import { JobCard } from "@/components/job-card";
import { StatCard } from "@/components/stat-card";

const CONTENT_TYPE_FILTERS = [
  { label: "All", value: "" },
  { label: "Short", value: "short" },
  { label: "Long", value: "long" },
  { label: "Article", value: "article" },
  { label: "Repo", value: "repo" },
];

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Done", value: "done" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Error", value: "error" },
];

function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white"
      }`}
    >
      {label}
    </button>
  );
}

export default function FeedPage() {
  const { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload } = useFeedData();
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  useInFlightPolling(jobs, reload);

  return (
    <div className="space-y-6">
      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-white">Overview</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total" value={stats.total} />
            <StatCard label="Done" value={stats.by_status.done ?? 0} />
            <StatCard label="Pending" value={stats.by_status.pending ?? 0} />
            <StatCard label="Error" value={stats.by_status.error ?? 0} />
            <StatCard
              label="Processing"
              value={(stats.by_status.processing ?? 0) + (stats.by_status.enriching ?? 0) + (stats.by_status.transcript_done ?? 0)}
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Short" value={stats.by_content_type.short ?? 0} />
            <StatCard label="Long" value={stats.by_content_type.long ?? 0} />
            <StatCard label="Article" value={stats.by_content_type.article ?? 0} />
            <StatCard label="Repo" value={stats.by_content_type.repo ?? 0} />
          </div>
        </section>
      )}

      <section>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by title or URL…"
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
        />
      </section>

      <section>
        <p className="mb-2 text-xs uppercase tracking-wide text-gray-500">Content type</p>
        <div className="flex flex-wrap gap-2">
          {CONTENT_TYPE_FILTERS.map(({ label, value }) => (
            <FilterButton key={value} label={label} active={ctFilter === value} onClick={() => setCtFilter(value)} />
          ))}
        </div>
      </section>

      <section>
        <p className="mb-2 text-xs uppercase tracking-wide text-gray-500">Status</p>
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map(({ label, value }) => (
            <FilterButton key={value} label={label} active={stFilter === value} onClick={() => setStFilter(value)} />
          ))}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">
            {query.trim()
              ? `${displayedJobs.length} result${displayedJobs.length === 1 ? "" : "s"}`
              : `${total} job${total === 1 ? "" : "s"}`}
          </h3>
          {loading && <span className="animate-pulse text-xs text-gray-500">Loading…</span>}
        </div>

        {error && (
          <p className="rounded-md bg-red-900/40 px-4 py-3 text-sm text-red-300">{error}</p>
        )}

        {!loading && !error && displayedJobs.length === 0 && (
          <p className="text-sm text-gray-500">No jobs found.</p>
        )}

        <div className="space-y-2">
          {displayedJobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      </section>
    </div>
  );
}
