'use client';

import { Suspense, useCallback, useEffect, useMemo } from 'react';
import {
  usePathname,
  useRouter,
  useSearchParams,
} from 'next/navigation';
import { useFeedData } from '@/lib/hooks/useFeedData';
import { useFuseSearch } from '@/lib/hooks/useFuseSearch';
import { useInFlightPolling } from '@/lib/hooks/useInFlightPolling';
import { useBackgroundFreshness } from '@/lib/hooks/useBackgroundFreshness';
import { JobCard } from '@/components/job-card';
import { StatsOverview } from '@/components/feed/stats-overview';
import { FilterBar } from '@/components/filter-bar';
import {
  SkeletonGrid,
  SkeletonList,
  ErrorBanner,
  EmptyState,
} from '@/components/feed/feed-states';
import { PreviewGrid } from '@/components/feed/preview-grid';
import { RecoveryPanel } from '@/components/feed/recovery-panel';
import { PageShell } from '@/components/page-shell';

const CONTENT_TYPES = new Set(['short', 'long', 'article', 'repo']);

const CONTENT_TYPE_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Short', value: 'short' },
  { label: 'Long', value: 'long' },
  { label: 'Article', value: 'article' },
  { label: 'Repo', value: 'repo' },
];

function jobCountLabel(
  firstLoad: boolean,
  loading: boolean,
  query: string,
  shown: number,
  total: number,
): string {
  if (firstLoad) return 'loading…';
  if (loading) return 'syncing…';
  if (query.trim()) return `${shown} result${shown === 1 ? '' : 's'}`;
  return `${total} job${total === 1 ? '' : 's'}`;
}

function normalizeContentType(value: string | null): string {
  return value && CONTENT_TYPES.has(value) ? value : '';
}

function FeedPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlContentType = normalizeContentType(
    searchParams.get('type'),
  );
  const {
    ctFilter,
    setCtFilter,
    stFilter,
    setStFilter,
    stats,
    jobs,
    total,
    loading,
    error,
    reload,
  } = useFeedData(urlContentType);
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  useInFlightPolling(jobs, reload);
  useBackgroundFreshness(reload);

  const refreshFeed = useCallback(async () => {
    await reload();
  }, [reload]);

  useEffect(() => {
    setCtFilter(urlContentType);
  }, [urlContentType, setCtFilter]);

  const setContentType = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      if (value) {
        params.set('type', value);
      } else {
        params.delete('type');
      }
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, {
        scroll: false,
      });
      setCtFilter(value);
    },
    [pathname, router, searchParams, setCtFilter],
  );

  // Drop an unsupported ?type= from the URL so deep links/bookmarks match the
  // actual ("All") view instead of advertising a filter that isn't applied.
  useEffect(() => {
    const raw = searchParams.get('type');
    if (raw && !CONTENT_TYPES.has(raw)) setContentType('');
  }, [searchParams, setContentType]);

  const contentTypeCounts = useMemo(
    () => stats?.by_content_type ?? {},
    [stats],
  );
  const totalCount = useMemo(
    () => Object.values(contentTypeCounts).reduce((a, b) => a + b, 0),
    [contentTypeCounts],
  );
  const contentTypeTabs = useMemo(
    () =>
      CONTENT_TYPE_FILTERS.map(({ label, value }, i) => ({
        label,
        value,
        count: value ? (contentTypeCounts[value] ?? 0) : totalCount,
        dividerBefore: i > 0,
      })),
    [contentTypeCounts, totalCount],
  );
  const firstLoad = loading && jobs.length === 0 && !error;
  const showPreviewGrid = Boolean(ctFilter);
  const hasFilters = Boolean(ctFilter || stFilter || query.trim());
  const empty = !loading && !error && displayedJobs.length === 0;

  const countLabel = jobCountLabel(
    firstLoad,
    loading,
    query,
    displayedJobs.length,
    total,
  );

  const clearAll = () => {
    setContentType('');
    setStFilter('');
    setQuery('');
  };

  return (
    <PageShell>
      <header className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <h1 className="text-5xl font-semibold leading-none tracking-tight text-ink">
          VIG
        </h1>
        <div
          aria-hidden="true"
          className="my-1 hidden w-px self-stretch bg-line-strong sm:block"
        />
        {/* Two voices: Inter italic motto over the machine's mono echo, each
            Latin word column-aligned above its English state. */}
        <div className="grid grid-cols-[repeat(3,auto)] gap-x-6 gap-y-1.5">
          <span className="text-sm font-medium italic text-body">Servavi.</span>
          <span className="text-sm font-medium italic text-body">Ditavi.</span>
          <span className="text-sm font-medium italic text-body">Inveni.</span>
          <span className="font-mono text-[11px] tracking-wide text-muted">Saved.</span>
          <span className="font-mono text-[11px] tracking-wide text-muted">Enriched.</span>
          <span className="font-mono text-[11px] tracking-wide text-muted">Found.</span>
        </div>
      </header>

      {stats && (
        <StatsOverview
          stats={stats}
          contentType={ctFilter}
        />
      )}

      <FilterBar
        tabs={contentTypeTabs}
        tabValue={ctFilter}
        onTabChange={setContentType}
        query={query}
        setQuery={setQuery}
        searchPlaceholder="Search by title or URL…"
        searchLabel="Search by title or URL"
        statusValue={stFilter}
        onStatusChange={setStFilter}
        recoveryPanel={
          <RecoveryPanel
            contentType={ctFilter}
            onRecovered={refreshFeed}
          />
        }
      />

      <section>
        <div className="mb-3 flex items-center gap-3">
          <h2 className="text-base font-semibold text-ink">Jobs</h2>
          <span
            className="inline-flex items-center rounded border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-muted"
            aria-live="polite"
          >
            {countLabel}
          </span>
        </div>

        {error && (
          <ErrorBanner
            message={error}
            onRetry={() => reload()}
          />
        )}
        {firstLoad &&
          (showPreviewGrid ? <SkeletonGrid /> : <SkeletonList />)}
        {empty && (
          <EmptyState
            hasFilters={hasFilters}
            onClear={clearAll}
          />
        )}

        {!firstLoad &&
          (showPreviewGrid ? (
            <PreviewGrid jobs={displayedJobs} />
          ) : (
            <div className="space-y-2">
              {displayedJobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                />
              ))}
            </div>
          ))}
      </section>
    </PageShell>
  );
}

export default function FeedPage() {
  return (
    <Suspense fallback={null}>
      <FeedPageContent />
    </Suspense>
  );
}
