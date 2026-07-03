'use client';

import { Suspense, useCallback, useEffect, useMemo, useState } from 'react';
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
import { useGoogleStatus } from '@/components/google-status';

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
  const { connected: googleConnected } = useGoogleStatus();
  useInFlightPolling(jobs, reload);
  useBackgroundFreshness(reload);

  // One URL-cleanup effect for the two transient params: capture the one-time
  // ?google= OAuth result into state (CONTEXT.md `Account affordance`) and drop
  // an unsupported ?type=, in a single replace so the two never race each other
  // back into the address bar.
  const [oauthResult, setOauthResult] = useState<'connected' | 'denied' | null>(null);
  useEffect(() => {
    const google = searchParams.get('google');
    const rawType = searchParams.get('type');
    const oauthReturn = google === 'connected' || google === 'denied';
    const badType = Boolean(rawType && !CONTENT_TYPES.has(rawType));
    if (!oauthReturn && !badType) return;
    if (oauthReturn) setOauthResult(google as 'connected' | 'denied');
    const params = new URLSearchParams(searchParams.toString());
    params.delete('google');
    if (badType) {
      params.delete('type');
      setCtFilter('');
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  }, [searchParams, pathname, router, setCtFilter]);

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

      {oauthResult && (
        <div
          role="status"
          className={`rounded-md border px-4 py-3 text-sm ${
            oauthResult === 'connected'
              ? 'border-status-done/40 bg-status-done-tint text-status-done'
              : 'border-status-error/40 bg-status-error-tint text-status-error'
          }`}
        >
          {oauthResult === 'connected'
            ? 'Google connected — exports will land in your Drive.'
            : 'Google connection was denied — you can try again anytime.'}
        </div>
      )}

      {/* Disconnected-only nudge (CONTEXT.md `Account affordance`) — the
          sidebar owns the persistent state; this panel disappears once connected. */}
      {googleConnected === false && (
        <section className="rounded-lg border border-line bg-surface p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs uppercase tracking-widest text-muted">Google export</p>
              <h2 className="mt-1 text-lg font-semibold text-ink">Connect Google</h2>
              <p className="mt-1 max-w-2xl text-sm text-body">Authorize Drive + Sheets so your jobs export into a vig-owned /vig folder in your own Google Drive.</p>
            </div>
            <a href="/api/google/connect" className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep">Connect Google</a>
          </div>
        </section>
      )}

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
