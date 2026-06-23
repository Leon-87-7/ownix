"use client";

import { Suspense, useCallback, useEffect, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useFeedData } from "@/lib/hooks/useFeedData";
import { useFuseSearch } from "@/lib/hooks/useFuseSearch";
import { useInFlightPolling } from "@/lib/hooks/useInFlightPolling";
import { useBackgroundFreshness } from "@/lib/hooks/useBackgroundFreshness";
import { JobCard } from "@/components/job-card";
import { StatsOverview } from "@/components/feed/stats-overview";
import { FilterBar } from "@/components/feed/filter-bar";
import { SkeletonGrid, SkeletonList, ErrorBanner, EmptyState } from "@/components/feed/feed-states";
import { PreviewGrid } from "@/components/feed/preview-grid";
import { RecoveryPanel } from "@/components/feed/recovery-panel";

const CONTENT_TYPES = new Set(["short", "long", "article", "repo"]);

function jobCountLabel(firstLoad: boolean, loading: boolean, query: string, shown: number, total: number): string {
  if (firstLoad) return "loading…";
  if (loading) return "syncing…";
  if (query.trim()) return `${shown} result${shown === 1 ? "" : "s"}`;
  return `${total} job${total === 1 ? "" : "s"}`;
}

function normalizeContentType(value: string | null): string {
  return value && CONTENT_TYPES.has(value) ? value : "";
}

function FeedPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlContentType = normalizeContentType(searchParams.get("type"));
  const { ctFilter, setCtFilter, stFilter, setStFilter, stats, jobs, total, loading, error, reload } = useFeedData(urlContentType);
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  useInFlightPolling(jobs, reload);
  useBackgroundFreshness(reload);

  const refreshFeed = useCallback(async () => {
    await reload();
  }, [reload]);

  useEffect(() => {
    setCtFilter(urlContentType);
  }, [urlContentType, setCtFilter]);

  const setContentType = useCallback((value: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (value) {
      params.set("type", value);
    } else {
      params.delete("type");
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    setCtFilter(value);
  }, [pathname, router, searchParams, setCtFilter]);

  const contentTypeCounts = useMemo(() => stats?.by_content_type ?? {}, [stats]);
  const firstLoad = loading && jobs.length === 0 && !error;
  const showPreviewGrid = Boolean(ctFilter);
  const hasFilters = Boolean(ctFilter || stFilter || query.trim());
  const empty = !loading && !error && displayedJobs.length === 0;

  const countLabel = jobCountLabel(firstLoad, loading, query, displayedJobs.length, total);

  const clearAll = () => {
    setContentType("");
    setStFilter("");
    setQuery("");
  };

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-semibold tracking-tight text-ink">Feed</h1>

      {stats && <StatsOverview stats={stats} contentType={ctFilter} />}

      <FilterBar
        query={query} setQuery={setQuery}
        ctFilter={ctFilter} setCtFilter={setContentType}
        contentTypeCounts={contentTypeCounts} totalCount={Object.values(contentTypeCounts).reduce((a, b) => a + b, 0)}
        stFilter={stFilter} setStFilter={setStFilter}
        recoveryPanel={<RecoveryPanel contentType={ctFilter} onRecovered={refreshFeed} />}
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
        {firstLoad && (showPreviewGrid ? <SkeletonGrid /> : <SkeletonList />)}
        {empty && <EmptyState hasFilters={hasFilters} onClear={clearAll} />}

        {!firstLoad && (
          showPreviewGrid ? (
            <PreviewGrid jobs={displayedJobs} />
          ) : (
            <div className="space-y-2">
              {displayedJobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          )
        )}
      </section>
    </div>
  );
}

export default function FeedPage() {
  return (
    <Suspense fallback={null}>
      <FeedPageContent />
    </Suspense>
  );
}
