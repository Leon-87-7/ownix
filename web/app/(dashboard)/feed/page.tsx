'use client';

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
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
import { useLinksTable } from '@/lib/hooks/useLinksTable';
import { JobCard } from '@/components/feed/job-card';
import { StatsOverview } from '@/components/feed/stats-overview';
import { FilterBar, type FilterTab } from '@/components/ui/filter-bar';
import {
  SkeletonGrid,
  SkeletonList,
  ErrorBanner,
  EmptyState,
} from '@/components/feed/feed-states';
import { PreviewGrid } from '@/components/feed/preview-grid';
import { RecoveryPanel } from '@/components/feed/recovery-panel';
import { PageShell } from '@/components/shell/page-shell';
import { useGoogleStatus } from '@/components/shell/google-status';
import { useSubmitJob } from '@/components/feed/submit-job';
import { LayoutDashboard, Link2, List } from 'lucide-react';
import { OwnixAddIcon } from '@/components/svg/ownix-add-icon';
import { GoogleIcon } from '@/components/svg/google-icon';
import type { JobSummary } from '@/components/feed/job-card';
import { LinksSearchBar, LinksTable } from '@/components/feed/links-table';
import { useRestrictedMode } from '@/lib/restricted/context';
import { extractSharedUrl } from '@/lib/share-target';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';

const CONTENT_TYPES = new Set(['short', 'long', 'article', 'repo']);

const LAYOUT_KEY = 'ownix.feed.layout';

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

const INTRO_SEEN_COOKIE = 'ownix_preview_intro_seen';

function RestrictedIntroModal() {
  const router = useRouter();
  const { restricted } = useRestrictedMode();
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!restricted) return;
    // Session cookie, not sessionStorage: "once per browser session" has to
    // hold across tabs, and sessionStorage is per-tab.
    if (
      document.cookie.split('; ').includes(`${INTRO_SEEN_COOKIE}=1`)
    )
      return;
    setShow(true);
  }, [restricted]);
  const dismiss = () => {
    document.cookie = `${INTRO_SEEN_COOKIE}=1; path=/; samesite=lax`;
    setShow(false);
  };
  return (
    <Dialog
      open={show}
      onOpenChange={(next) => {
        if (!next) dismiss();
      }}
    >
      <DialogContent className="max-w-lg">
        <DialogTitle>Restricted mode on</DialogTitle>
        <DialogDescription>
          This preview uses a read-only sample from Leon&apos;s Index,
          balanced across Feed tabs so you can see videos, articles,
          repos, and links. Actions are locked until you get access.
        </DialogDescription>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => {
              dismiss();
              router.push('/login?from=restricted');
            }}
            className="inline-flex h-9 items-center rounded-md border border-line border-b-2 border-b-signal bg-canvas px-3 text-sm font-medium text-signal hover:bg-raised"
          >
            Get access
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="inline-flex h-9 items-center rounded-md border border-line border-b-2 border-b-contrasignal-deep bg-canvas px-3 text-sm font-medium text-body hover:bg-raised"
          >
            Keep looking
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FeedPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const urlContentType = normalizeContentType(
    searchParams.get('type'),
  );
  const { restricted, showRestrictedToast } = useRestrictedMode();
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
  } = useFeedData(urlContentType, restricted);
  const {
    openIntake,
    openSubmitWith,
    lastAccepted,
    registerFeedSearch,
  } = useSubmitJob();
  const [feedView, setFeedView] = useState<'jobs' | 'links'>(
    !restricted && searchParams.get('view') === 'links' ? 'links' : 'jobs',
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

  // One URL-cleanup effect for transient params: capture the one-time
  // ?google= OAuth result into state (CONTEXT.md `Account affordance`), hand
  // share targets into the Submit URL dialog, and drop unsupported ?type= in a
  // single replace so the params never race each other back into the address bar.
  const [oauthResult, setOauthResult] = useState<
    'connected' | 'denied' | null
  >(null);
  useEffect(() => {
    const google = searchParams.get('google');
    const rawType = searchParams.get('type');
    const restrictedLinksView = restricted && searchParams.get('view') === 'links';
    const hasShareParams =
      searchParams.has('share_title') ||
      searchParams.has('share_text') ||
      searchParams.has('share_url');
    const sharedUrl = extractSharedUrl(
      searchParams.get('share_url'),
      searchParams.get('share_text'),
    );
    const oauthReturn = google === 'connected' || google === 'denied';
    const badType = Boolean(rawType && !CONTENT_TYPES.has(rawType));
    if (!oauthReturn && !badType && !restrictedLinksView && !hasShareParams) return;
    if (oauthReturn) setOauthResult(google as 'connected' | 'denied');
    if (sharedUrl) openSubmitWith(sharedUrl);
    const params = new URLSearchParams(searchParams.toString());
    params.delete('google');
    params.delete('share_title');
    params.delete('share_text');
    params.delete('share_url');
    if (restrictedLinksView) params.delete('view');
    if (badType) {
      params.delete('type');
      setCtFilter('');
    }
    const qs = params.toString();
    router.replace(qs ? `${pathname}?${qs}` : pathname, {
      scroll: false,
    });
  }, [
    searchParams,
    pathname,
    router,
    setCtFilter,
    restricted,
    openSubmitWith,
    setOauthResult,
  ]);

  const refreshFeed = useCallback(async () => {
    await reload();
  }, [reload]);

  useEffect(() => {
    setCtFilter(urlContentType);
  }, [urlContentType, setCtFilter]);

  useEffect(() => {
    setFeedView(
      !restricted && searchParams.get('view') === 'links' ? 'links' : 'jobs',
    );
  }, [searchParams, restricted]);

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
    if (restricted) {
      showRestrictedToast('Links are available after sign-in.');
      setFeedView('jobs');
      return;
    }
    const params = new URLSearchParams(searchParams.toString());
    params.delete('type');
    params.set('view', 'links');
    router.replace(`${pathname}?${params}`, { scroll: false });
    setFeedView('links');
  }, [pathname, router, searchParams, restricted, showRestrictedToast]);

  // Expose the Feed search focus to the command launcher. focusLinkSearch
  // switches to Links first, then focuses LinksTable's own search input — not
  // #feed-search, which drives the Jobs query and would leave a stale filter.
  // focusSearch does the reverse: #feed-search is unmounted while Links is
  // active (FilterBar hides it there), so hitting `/` on that tab backs out
  // to the All tab first, then retries the focus across frames until the
  // input remounts. Both read showingLinksRef instead of `showingLinks`
  // directly so this effect doesn't need to re-register on every tab switch.
  useEffect(() => {
    registerFeedSearch({
      focusSearch: () => {
        if (!showingLinksRef.current) {
          document.getElementById('feed-search')?.focus();
          return;
        }
        setContentType('');
        let attempts = 0;
        const focusJobsSearch = () => {
          const input = document.getElementById('feed-search');
          if (input) {
            input.focus();
          } else if (attempts++ < 10) {
            requestAnimationFrame(focusJobsSearch);
          }
        };
        requestAnimationFrame(focusJobsSearch);
      },
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
  }, [registerFeedSearch, switchToLinks, setContentType]);

  const contentTypeCounts = useMemo(
    () => stats?.by_content_type ?? {},
    [stats],
  );
  const totalCount = useMemo(
    () => Object.values(contentTypeCounts).reduce((a, b) => a + b, 0),
    [contentTypeCounts],
  );
  const contentTypeTabs = useMemo(() => {
    const tabs: FilterTab[] = CONTENT_TYPE_FILTERS.map(({ label, value }, i) => ({
      label,
      value,
      count: value ? (contentTypeCounts[value] ?? 0) : totalCount,
      dividerBefore: i > 0,
    }));
    if (!restricted) {
      tabs.push({
        label: 'Links',
        value: 'links',
        dividerBefore: true,
        icon: Link2,
      });
    }
    return tabs;
  }, [contentTypeCounts, totalCount, restricted]);
  const firstLoad = loading && jobs.length === 0 && !error;
  const showingLinks = feedView === 'links';
  // Read inside the focusSearch closure below without re-registering it on
  // every tab switch (registerFeedSearch only re-runs on identity changes).
  const showingLinksRef = useRef(showingLinks);
  showingLinksRef.current = showingLinks;
  // Gated by `enabled` so Links data only fetches while its tab is actually
  // active — mirrors how the Jobs feed already fetches regardless of tab,
  // except Links has no reason to poll while parked on Jobs.
  const linksData = useLinksTable({ enabled: showingLinks && !restricted });
  // CONTEXT.md `Feed layout toggle`: All-tab-only grid↔list switch, grid
  // default, persisted. Hydrated in an effect so SSR/first paint stay 'grid'.
  const [allLayout, setAllLayout] = useState<'grid' | 'list'>('grid');
  useEffect(() => {
    try {
      if (window.localStorage.getItem(LAYOUT_KEY) === 'list') {
        setAllLayout('list');
      }
    } catch {
      // storage unavailable (private mode) — stay on the grid default
    }
  }, []);
  const switchLayout = (mode: 'grid' | 'list') => {
    setAllLayout(mode);
    try {
      window.localStorage.setItem(LAYOUT_KEY, mode);
    } catch {
      // non-persistent session is fine
    }
  };
  const showPreviewGrid = Boolean(ctFilter) || allLayout === 'grid';
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
      <RestrictedIntroModal />
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
      {!restricted && googleConnected === false && (
        <section className="rounded-lg border border-line bg-surface p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-[11px] font-medium text-muted">
                Connected service
              </p>
              <h2 className="mt-1 text-lg font-semibold text-ink">
                Connect Google
              </h2>
              <p className="mt-1 max-w-2xl text-sm text-body">
                Authorize Drive + Sheets so saved items export into
                your Ownix folder in Drive.
              </p>
            </div>
            <a
              href="/api/google/connect"
              aria-label="Connect Google"
              className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
            >
              Connect to <GoogleIcon className="ml-2 h-4 w-4" />
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
        hideSearchAndFilters={showingLinks}
        searchSlot={
          showingLinks ? (
            <LinksSearchBar linksData={linksData} />
          ) : undefined
        }
        recoveryPanel={
          <RecoveryPanel
            contentType={ctFilter}
            onRecovered={refreshFeed}
            active={!showingLinks}
          />
        }
        actionSlot={
          <>
            {/* Mobile-only (<sm): one non-floating intake launcher occupies the
             two-row footprint formerly used by Submit + Docs. The content tabs
             continue flowing into columns 2-4. */}
            <button
              type="button"
              onClick={openIntake}
              aria-label="Add to your Index"
              aria-haspopup="dialog"
              className="col-start-1 row-start-1 row-span-2 inline-flex min-h-9 items-center justify-center rounded-md border border-line border-b-2 border-b-signal bg-surface px-1.5 text-body transition-ui hover:bg-raised hover:text-ink active:scale-[0.96] motion-reduce:active:scale-100 sm:hidden"
            >
              <OwnixAddIcon
                aria-hidden="true"
                className="h-10 w-10"
              />
            </button>
            {restricted && (
              <span
                aria-hidden="true"
                className="col-start-4 row-start-2 block sm:hidden"
              />
            )}
          </>
        }
      />

      {showingLinks ? (
        <LinksTable linksData={linksData} />
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
            {/* CONTEXT.md `Feed layout toggle` — All tab only; typed tabs keep
                their fixed layouts. */}
            {!ctFilter && (
              <div
                role="group"
                aria-label="Layout"
                className="ml-auto flex items-center gap-0.5 rounded-lg border border-line bg-surface p-0.5"
              >
                <button
                  type="button"
                  aria-pressed={allLayout === 'grid'}
                  aria-label="Grid layout"
                  onClick={() => switchLayout('grid')}
                  className={`inline-flex h-7 w-8 items-center justify-center rounded-md transition-ui ${
                    allLayout === 'grid'
                      ? 'bg-signal text-onsignal'
                      : 'text-muted hover:bg-raised hover:text-ink'
                  }`}
                >
                  <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  aria-pressed={allLayout === 'list'}
                  aria-label="List layout"
                  onClick={() => switchLayout('list')}
                  className={`inline-flex h-7 w-8 items-center justify-center rounded-md transition-ui ${
                    allLayout === 'list'
                      ? 'bg-signal text-onsignal'
                      : 'text-muted hover:bg-raised hover:text-ink'
                  }`}
                >
                  <List className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )}
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
                variant={
                  ctFilter === 'short'
                    ? 'shorts'
                    : ctFilter
                      ? 'uniform'
                      : 'bento'
                }
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
