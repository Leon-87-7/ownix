'use client';

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
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
import { useSubmitJob } from '@/components/submit-job';
import { FileCode2, Link2, Plus } from 'lucide-react';
import type { JobSummary } from '@/components/job-card';
import { LinksTable } from '@/components/links-table';

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
  const {
    setOpen: setSubmitOpen,
    openDocs,
    lastAccepted,
    registerFeedSearch,
  } = useSubmitJob();
  const [feedView, setFeedView] = useState<'jobs' | 'links'>(
    searchParams.get('view') === 'links' ? 'links' : 'jobs',
  );
  const [optimisticJobs, setOptimisticJobs] = useState<JobSummary[]>(
    [],
  );
  const mergedJobs = useMemo(() => {
    const feedIds = new Set(jobs.map((job) => job.id));
    return [
      ...optimisticJobs.filter((job) => !feedIds.has(job.id)),
      ...jobs,
    ];
  }, [optimisticJobs, jobs]);
  const { query, setQuery, displayedJobs } =
    useFuseSearch(mergedJobs);
  const { connected: googleConnected } = useGoogleStatus();
  // Poll on mergedJobs, not jobs: an accepted submission held as an optimistic
  // row keeps the poll hot, so a failed post-submit refresh retries until the
  // feed actually carries the job.
  useInFlightPolling(mergedJobs, reload);

  // Drop optimistic rows once the refreshed feed carries the same job id.
  useEffect(() => {
    setOptimisticJobs((current) => {
      if (current.length === 0) return current;
      const feedIds = new Set(jobs.map((job) => job.id));
      const next = current.filter((job) => !feedIds.has(job.id));
      return next.length === current.length ? current : next;
    });
  }, [jobs]);
  useBackgroundFreshness(reload);

  // One URL-cleanup effect for the two transient params: capture the one-time
  // ?google= OAuth result into state (CONTEXT.md `Account affordance`) and drop
  // an unsupported ?type=, in a single replace so the two never race each other
  // back into the address bar.
  const [oauthResult, setOauthResult] = useState<
    'connected' | 'denied' | null
  >(null);
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
    router.replace(qs ? `${pathname}?${qs}` : pathname, {
      scroll: false,
    });
  }, [searchParams, pathname, router, setCtFilter]);

  const refreshFeed = useCallback(async () => {
    await reload();
  }, [reload]);

  useEffect(() => {
    setCtFilter(urlContentType);
  }, [urlContentType, setCtFilter]);

  useEffect(() => {
    setFeedView(
      searchParams.get('view') === 'links' ? 'links' : 'jobs',
    );
  }, [searchParams]);

  const setContentType = useCallback(
    (value: string) => {
      const params = new URLSearchParams(searchParams.toString());
      params.delete('view');
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

  const switchToLinks = useCallback(() => {
    const params = new URLSearchParams(searchParams.toString());
    params.delete('type');
    params.set('view', 'links');
    router.replace(`${pathname}?${params}`, { scroll: false });
    setFeedView('links');
  }, [pathname, router, searchParams]);

  // Expose the Feed search focus to the command launcher. focusLinkSearch
  // switches to Links first, then focuses LinksTable's own search input — not
  // #feed-search, which drives the Jobs query and would leave a stale filter.
  // LinksTable mounts only after the view switch, so retry across frames until
  // its input exists.
  useEffect(() => {
    registerFeedSearch({
      focusSearch: () =>
        document.getElementById('feed-search')?.focus(),
      focusLinkSearch: () => {
        switchToLinks();
        let attempts = 0;
        const focusLinks = () => {
          const input = document.getElementById('links-search');
          if (input) {
            input.focus();
          } else if (attempts++ < 10) {
            requestAnimationFrame(focusLinks);
          }
        };
        requestAnimationFrame(focusLinks);
      },
    });
    return () => registerFeedSearch(null);
  }, [registerFeedSearch, switchToLinks]);

  const contentTypeCounts = useMemo(
    () => stats?.by_content_type ?? {},
    [stats],
  );
  const totalCount = useMemo(
    () => Object.values(contentTypeCounts).reduce((a, b) => a + b, 0),
    [contentTypeCounts],
  );
  const contentTypeTabs = useMemo(
    () => [
      ...CONTENT_TYPE_FILTERS.map(({ label, value }, i) => ({
        label,
        value,
        count: value ? (contentTypeCounts[value] ?? 0) : totalCount,
        dividerBefore: i > 0,
      })),
      {
        label: 'Links',
        value: 'links',
        dividerBefore: true,
        icon: Link2,
      },
    ],
    [contentTypeCounts, totalCount],
  );
  const firstLoad = loading && jobs.length === 0 && !error;
  const showingLinks = feedView === 'links';
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

  // The global dialog (SubmitJobProvider) owns the mutation; the Feed only
  // reacts to an accepted job — insert an optimistic row so the submission is
  // visible immediately, and refresh. The row stays until the feed carries the
  // same id (the reconcile effect on `jobs`), and in-flight polling keeps
  // retrying the refresh for as long as it reads as pending.
  useEffect(() => {
    if (!lastAccepted) return;
    const { id, url, title, content_type, status } = lastAccepted;
    if (id) {
      setOptimisticJobs((current) =>
        current.some((job) => job.id === id)
          ? current
          : [
              {
                id,
                url,
                title,
                content_type,
                status,
                created_at: new Date().toISOString(),
              },
              ...current,
            ],
      );
    }
    void reload();
  }, [lastAccepted, reload]);

  const clearAll = () => {
    setFeedView('jobs');
    setContentType('');
    setStFilter('');
    setQuery('');
  };

  return (
    <PageShell>
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
              <p className="text-xs uppercase tracking-widest text-muted">
                Google export
              </p>
              <h2 className="mt-1 text-lg font-semibold text-ink">
                Connect Google
              </h2>
              <p className="mt-1 max-w-2xl text-sm text-body">
                Authorize Drive + Sheets so your jobs export into a
                vig-owned /vig folder in your own Google Drive.
              </p>
            </div>
            <a
              href="/api/google/connect"
              className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
            >
              Connect Google
            </a>
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
        tabValue={showingLinks ? 'links' : ctFilter}
        onTabChange={(value) => {
          if (value === 'links') {
            switchToLinks();
            return;
          }
          setFeedView('jobs');
          setContentType(value);
        }}
        query={query}
        setQuery={setQuery}
        searchInputId="feed-search"
        searchPlaceholder="Search by title or URL…"
        searchLabel="Search by title or URL"
        statusValue={stFilter}
        onStatusChange={setStFilter}
        recoveryPanel={
          <RecoveryPanel
            contentType={ctFilter}
            onRecovered={refreshFeed}
            active={!showingLinks}
          />
        }
        actionSlot={
          <>
            {/* Mobile-only (<sm): Submit + Docs stack in the grid's first column
             (Submit top, Docs bottom) via explicit col/row placement; the six
             content-type tabs then auto-flow into columns 2–4 across both rows.
             Signal underline + signal text mark them as the row's actions without
             matching the active chip's full signal fill (The Signal Rule). They
             open the same dialogs as the sm+ header triggers. */}
            <button
              type="button"
              onClick={() => setSubmitOpen(true)}
              aria-label="Submit URL"
              aria-haspopup="dialog"
              aria-keyshortcuts="N"
              className="col-start-1 row-start-1 inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-line border-b-2 border-b-signal bg-surface px-1.5 text-[13px] font-medium text-signal transition-ui hover:bg-raised active:scale-[0.96] motion-reduce:active:scale-100 sm:hidden"
            >
              <Plus
                aria-hidden="true"
                className="h-4 w-4"
              />
              Submit
            </button>
            <button
              type="button"
              onClick={openDocs}
              aria-label="Ingest docs"
              aria-haspopup="dialog"
              aria-keyshortcuts="D"
              className="col-start-1 row-start-2 inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-line border-b-2 border-b-signal bg-surface px-1.5 text-[13px] font-medium text-signal transition-ui hover:bg-raised active:scale-[0.96] motion-reduce:active:scale-100 sm:hidden"
            >
              <span className="flex items-center gap-2.5">
                <FileCode2
                  aria-hidden="true"
                  className="h-4 w-4"
                />
                <span>Docs</span>
              </span>
            </button>
          </>
        }
      />

      {showingLinks ? (
        <LinksTable />
      ) : (
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
              <PreviewGrid
                jobs={displayedJobs}
                contentType={ctFilter}
                status={stFilter}
              />
            ) : (
              <div className="space-y-2">
                {displayedJobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    contentType={ctFilter}
                    status={stFilter}
                  />
                ))}
              </div>
            ))}
        </section>
      )}
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
