"use client";

import { useFeedData } from "@/lib/hooks/useFeedData";
import { useFuseSearch } from "@/lib/hooks/useFuseSearch";
import { useInFlightPolling } from "@/lib/hooks/useInFlightPolling";
import { JobCard } from "@/components/job-card";
import { StatsOverview } from "@/components/feed/stats-overview";
import { FilterBar } from "@/components/feed/filter-bar";
import { SkeletonList, ErrorBanner, EmptyState } from "@/components/feed/feed-states";

function jobCountLabel(firstLoad: boolean, loading: boolean, query: string, shown: number, total: number): string {
  if (firstLoad) return "loading…";
  if (loading) return "syncing…";
  if (query.trim()) return `${shown} result${shown === 1 ? "" : "s"}`;
  return `${total} job${total === 1 ? "" : "s"}`;
}

export default function FeedPage() {
  const { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload } = useFeedData();
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  useInFlightPolling(jobs, reload);

  const firstLoad = loading && jobs.length === 0 && !error;
  const hasFilters = Boolean(ctFilter || stFilter || query.trim());
  const empty = !loading && !error && displayedJobs.length === 0;

  const countLabel = jobCountLabel(firstLoad, loading, query, displayedJobs.length, total);

  const clearAll = () => {
    setCtFilter("");
    setStFilter("");
    setQuery("");
  };

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Feed</h1>

      {stats && <StatsOverview stats={stats} />}

      <FilterBar
        query={query} setQuery={setQuery}
        ctFilter={ctFilter} setCtFilter={setCtFilter}
        stFilter={stFilter} setStFilter={setStFilter}
      />

      <section className="mt-8">
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-base font-semibold text-ink">Jobs</h2>
          <span
            className="inline-flex items-center rounded border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-muted"
            aria-live="polite"
          >
            {countLabel}
          </span>
        </div>

        {error && <ErrorBanner message={error} onRetry={() => reload()} />}
        {firstLoad && <SkeletonList />}
        {empty && <EmptyState hasFilters={hasFilters} onClear={clearAll} />}

        {!firstLoad && (
          <div className="space-y-2">
            {displayedJobs.map((job) => (
              <JobCard key={job.id} job={job} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
