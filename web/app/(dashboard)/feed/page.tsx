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
import { fetchVocabulary, type TagSummary } from '@/lib/hooks/useLinkTags';
import { useFuseFilter } from '@/lib/hooks/useFuseSearch';
import { useInFlightPolling } from '@/lib/hooks/useInFlightPolling';
import { useBackgroundFreshness } from '@/lib/hooks/useBackgroundFreshness';
import { useLinksTable } from '@/lib/hooks/useLinksTable';
import { JobCard } from '@/components/feed/job-card';
import { StatsOverview } from '@/components/feed/stats-overview';
import {
  FilterBar,
  FilterRow,
  FilterSearchInput,
  type FilterTab,
} from '@/components/ui/filter-bar';
import { GhostButton } from '@/components/ui/ghost-button';
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
import { BookmarkCheck, LayoutDashboard, Link2, List } from 'lucide-react';
import { GENERATED_MARK_PAINT } from '@/components/ui/generated-badge';
import { OwnixAddIcon } from '@/components/svg/ownix-add-icon';
import { GoogleIcon } from '@/components/svg/google-icon';
import type { JobSummary } from '@/components/feed/job-card';
import {
  LinksSearchBar,
  LinksTable,
} from '@/components/feed/links-table';
import { useRestrictedMode } from '@/lib/restricted/context';
import { extractSharedUrl } from '@/lib/share-target';
import {
  feedScopeQuery,
  parseFeedScope,
  type FeedScope,
} from '@/lib/feed-scope';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';

const LAYOUT_KEY = 'ownix.feed.layout';

/** Restricted mode has no Links table, so a `?view=links` deep link into it
 * resolves to the job list — and the URL projection then rewrites the address
 * bar to match, rather than leaving a param pointing at a view that isn't there. */
function clampScope(scope: FeedScope, restricted: boolean): FeedScope {
  return restricted ? { ...scope, view: 'jobs' } : scope;
}

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

/** Focuses an input that a state change is about to mount. Retries across
 * frames because the element doesn't exist yet at the moment of the call. */
function focusWhenMounted(id: string, attemptsLeft = 10): void {
  requestAnimationFrame(() => {
    const input = document.getElementById(id);
    if (input) input.focus();
    else if (attemptsLeft > 0) focusWhenMounted(id, attemptsLeft - 1);
  });
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
          <GhostButton
            type="button"
            accent="signal"
            onClick={() => {
              dismiss();
              router.push('/login?from=restricted');
            }}
            className="h-9 bg-canvas px-3 text-sm font-medium text-signal"
          >
            Get access
          </GhostButton>
          <GhostButton
            type="button"
            onClick={dismiss}
            className="h-9 bg-canvas px-3 text-sm font-medium text-body"
          >
            Keep looking
          </GhostButton>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function FeedPageContent() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { restricted, showRestrictedToast } = useRestrictedMode();

  // The Feed's one copy of "what is the user looking at". Seeded from the URL
  // at mount (a back-navigation is a fresh mount, which is exactly when this
  // has to seed) and projected back onto the URL by the single effect below.
  //
  // It used to be the other way around — the narrowing lived in useFeedData,
  // was mirrored into two refs, and was written to the address bar from three
  // places that each had to clone-and-advance a shared ref so they wouldn't
  // erase each other's pending change (CodeRabbit, PR #626). With one writer
  // whose input is React state, two changes made before App Router publishes
  // the first simply merge, the way any two setState calls do.
  const [scope, setScope] = useState<FeedScope>(() =>
    clampScope(parseFeedScope(searchParams), restricted),
  );
  const {
    tagCounts,
    stats,
    jobs,
    total,
    loading,
    error,
    reload,
    preloadIndexes,
  } = useFeedData(scope, restricted);
  const ctFilter = scope.contentType ?? '';
  const stFilter = scope.status ?? '';
  const checklistOnly = scope.checklistOnly ?? false;
  const tagFilter = useMemo(() => scope.tags ?? [], [scope.tags]);
  // Shared module-level vocabulary cache (also used by JobCardTags), so the
  // filter dropdown doesn't fire its own /api/controls/tags request in the
  // common case. Re-reads on every job-list refresh (background poll, manual
  // reload) rather than mount-only: a tag created via a card's "New tag…" menu
  // busts the shared cache from that card's own hook instance, and this is the
  // only way this component notices — the cache has no subscribe/broadcast,
  // just a swapped module-level promise. Re-fetching is a cache hit (no network
  // call) except right after such a bust, so the extra calls are free.
  const [allTags, setAllTags] = useState<TagSummary[]>([]);
  useEffect(() => {
    void fetchVocabulary().then(setAllTags);
  }, [jobs]);
  const {
    openIntake,
    openSubmitWith,
    lastAccepted,
    registerFeedSearch,
  } = useSubmitJob();
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
  // The search text is part of the scope like every other narrowing, and the
  // matching is a pure derivation over it — so typing is plain React state
  // (instant), while the URL projection below keeps `?q=` in step.
  const query = scope.query ?? '';
  const displayedJobs = useFuseFilter(mergedJobs, query);
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

  // Transient inbound params, consumed once on arrival: the ?google= OAuth
  // result (CONTEXT.md `Account affordance`) and a share-target handoff. They
  // are never written back — the projection effect below emits only scope
  // params, so reaching the canonical URL removes them by construction rather
  // than by a list of param deletes.
  const [oauthResult, setOauthResult] = useState<
    'connected' | 'denied' | null
  >(null);
  const consumedTransientRef = useRef(false);
  useEffect(() => {
    if (consumedTransientRef.current) return;
    consumedTransientRef.current = true;
    const google = searchParams.get('google');
    if (google === 'connected' || google === 'denied') setOauthResult(google);
    const sharedUrl = extractSharedUrl(
      searchParams.get('share_url'),
      searchParams.get('share_text'),
    );
    if (sharedUrl) openSubmitWith(sharedUrl);
  }, [searchParams, openSubmitWith]);

  // The Feed's only URL writer. The address bar is a projection of the scope,
  // so it always describes the list on screen — which is what makes a
  // back-navigation restore the user's working set instead of dumping them at
  // the top of an unfiltered feed. The equality guard keeps it idempotent: an
  // arrival whose URL is already canonical writes nothing.
  // `scope` is the whole view — search text included — so the address bar and
  // every card link are built from the same object, and a job opened from the
  // feed can always rebuild the feed it came from.
  const canonicalQuery = useMemo(
    () => new URLSearchParams(feedScopeQuery(scope)).toString(),
    [scope],
  );
  // Querystrings this component wrote and hasn't seen published yet. App Router
  // republishes our own `replace` back to us as a `searchParams` change, which
  // is indistinguishable from a navigation unless we remember what we sent.
  const ourWritesRef = useRef<Set<string>>(new Set());
  // Set for exactly the commit in which an incoming URL was adopted, so the
  // projection effect below can sit that one out. See its comment for why.
  const adoptingRef = useRef(false);

  // Deliberately keyed on `searchParams` alone. Keying it on the scope too
  // would make our own in-flight narrowing look like an outside navigation and
  // wipe it — the PR #626 failure, from the other direction.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (ourWritesRef.current.delete(searchParams.toString())) return;
    // Someone navigated to a different /feed URL without remounting us — the
    // sidebar's own "Feed" link, clicked from an already-filtered feed. Adopt
    // it whole, rather than the two-of-six fields the old sync effects covered.
    adoptingRef.current = true;
    setScope(clampScope(parseFeedScope(searchParams), restricted));
  }, [searchParams, restricted]);

  useEffect(() => {
    // The adoption effect above only *queued* the incoming scope — `scope`, and
    // so `canonicalQuery`, still hold the previous one for the rest of this
    // commit. Projecting that now would `router.replace` the URL the user just
    // navigated to back to the one they left. Sit out the one commit; the
    // adopted scope re-runs this effect and projects its own canonical form.
    if (adoptingRef.current) {
      adoptingRef.current = false;
      return;
    }
    if (canonicalQuery === searchParams.toString()) return;
    ourWritesRef.current.add(canonicalQuery);
    router.replace(
      canonicalQuery ? `${pathname}?${canonicalQuery}` : pathname,
      { scroll: false },
    );
    // `scope` is a dep even though `canonicalQuery` is derived from it: adopting
    // a URL that canonicalizes to the same string leaves canonicalQuery
    // value-equal, so without the object identity this effect would never re-run
    // after the commit it just sat out, and the projection would be lost.
  }, [scope, canonicalQuery, searchParams, pathname, router]);

  const setFeedScope = useCallback(
    (patch: Partial<FeedScope>) => {
      // No debounce on the `q` path: the jobs are already in memory and Fuse
      // re-filters them on every keystroke regardless, so this adds a render,
      // not a fetch. The repo's debounces (useLinksTable, useAddSearch) guard
      // network calls, which this isn't.
      setScope((previous) => {
        const next = { ...previous, ...patch };
        // Choosing a content type always means the Jobs list, never the Links
        // table — the one interaction between the two, stated once.
        if (patch.contentType !== undefined) next.view = 'jobs';
        return next;
      });
    },
    [],
  );
  const setContentType = useCallback(
    (value: string) => setFeedScope({ contentType: value }),
    [setFeedScope],
  );

  const switchToLinks = useCallback(() => {
    if (restricted) {
      showRestrictedToast('Links are available after sign-in.');
      return;
    }
    setFeedScope({ view: 'links' });
  }, [restricted, showRestrictedToast, setFeedScope]);

  // Expose the Feed search focus to the command launcher. focusLinkSearch
  // switches to Links first, then focuses LinksTable's own search input - not
  // #feed-search, which drives the Jobs query and would leave a stale filter.
  // focusSearch does the reverse: #feed-search is unmounted while Links is
  // active (FilterBar hides it there), so hitting `/` on that tab backs out
  // to the All tab first. Either way the target input only mounts on a later
  // render, which is what focusWhenMounted waits out. Reads showingLinksRef
  // rather than `showingLinks` so this doesn't re-register on every tab switch.
  useEffect(() => {
    registerFeedSearch({
      focusSearch: () => {
        if (!showingLinksRef.current) {
          document.getElementById('feed-search')?.focus();
          return;
        }
        setContentType('');
        focusWhenMounted('feed-search');
      },
      focusLinkSearch: () => {
        switchToLinks();
        focusWhenMounted('links-search');
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
    const tabs: FilterTab[] = CONTENT_TYPE_FILTERS.map(
      ({ label, value }, i) => ({
        label,
        value,
        count: value ? (contentTypeCounts[value] ?? 0) : totalCount,
        dividerBefore: i > 0,
      }),
    );
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
  const showingLinks = scope.view === 'links';
  // Read inside the focusSearch closure below without re-registering it on
  // every tab switch (registerFeedSearch only re-runs on identity changes).
  const showingLinksRef = useRef(showingLinks);
  showingLinksRef.current = showingLinks;
  // Gated by `enabled` so Links data only fetches while its tab is actually
  // active - mirrors how the Jobs feed already fetches regardless of tab,
  // except Links has no reason to poll while parked on Jobs.
  const linksData = useLinksTable({
    enabled: showingLinks && !restricted,
  });
  // CONTEXT.md `Feed layout toggle`: All-tab-only grid↔list switch, grid
  // default, persisted. Hydrated in an effect so SSR/first paint stay 'grid'.
  const [allLayout, setAllLayout] = useState<'grid' | 'list'>('grid');
  useEffect(() => {
    try {
      if (window.localStorage.getItem(LAYOUT_KEY) === 'list') {
        setAllLayout('list');
      }
    } catch {
      // storage unavailable (private mode) - stay on the grid default
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
  const hasFilters = Boolean(
    ctFilter || stFilter || checklistOnly || tagFilter.length || query.trim(),
  );
  const empty = !loading && !error && displayedJobs.length === 0;

  const countLabel = jobCountLabel(
    firstLoad,
    loading,
    query,
    displayedJobs.length,
    total,
  );

  // The global dialog (SubmitJobProvider) owns the mutation; the Feed only
  // reacts to an accepted job - insert an optimistic row so the submission is
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
    setFeedScope({
      contentType: '',
      status: '',
      query: '',
      checklistOnly: false,
      tags: [],
    });
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
            ? 'Google connected - exports will land in your Drive.'
            : 'Google connection was denied - you can try again anytime.'}
        </div>
      )}

      {/* Disconnected-only nudge (CONTEXT.md `Account affordance`) - the
          sidebar owns the persistent state; this panel disappears once connected. */}
      {!restricted && googleConnected === false && (
        <section className="rounded-lg border border-line bg-surface p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-mono-label font-medium text-muted">
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
              className="inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
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
          setContentType(value);
        }}
        search={
          showingLinks ? (
            <LinksSearchBar linksData={linksData} />
          ) : (
            <FilterSearchInput
              id="feed-search"
              query={query}
              setQuery={(next) => setFeedScope({ query: next })}
              label="Search by title or URL"
              placeholder="Search by title or URL…"
            />
          )
        }
        filters={
          // The Links table has no job statuses to narrow by, so it simply
          // renders no filter row.
          showingLinks ? undefined : (
            <FilterRow
              statusValue={stFilter}
              onStatusChange={(next) => setFeedScope({ status: next })}
              toggleFilters={[
                {
                  // Same mark the cards wear (GeneratedBadge), same paint — the
                  // chip is that badge turned into a control, so no text label
                  // is needed.
                  label: 'Checklist generated',
                  icon: BookmarkCheck,
                  iconClassName: GENERATED_MARK_PAINT,
                  active: checklistOnly,
                  onChange: (next) => setFeedScope({ checklistOnly: next }),
                },
              ]}
              tagFilter={{
                allTags,
                counts: tagCounts,
                selectedIds: tagFilter,
                onChange: (next) => setFeedScope({ tags: next }),
              }}
              trailing={
                <RecoveryPanel
                  contentType={ctFilter}
                  onRecovered={reload}
                  active={!showingLinks}
                />
              }
            />
          )
        }
        actionSlot={
          <>
            {/* Mobile-only (<sm): one non-floating intake launcher occupies the
             two-row footprint formerly used by Submit + Docs. The content tabs
             continue flowing into columns 2-4. */}
            <GhostButton
              type="button"
              accent="signal"
              onClick={openIntake}
              aria-label="Add to your Index"
              aria-haspopup="dialog"
              className="col-start-1 row-start-1 row-span-2 min-h-9 bg-surface px-1.5 text-body hover:text-ink sm:hidden"
            >
              <OwnixAddIcon
                aria-hidden="true"
                className="h-10 w-10"
              />
            </GhostButton>
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
              className="inline-flex items-center rounded border border-line px-1.5 py-0.5 font-mono text-mono-label font-medium tracking-wider text-muted"
              aria-live="polite"
            >
              {countLabel}
            </span>
            {/* CONTEXT.md `Feed layout toggle` - All tab only; typed tabs keep
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
                  <LayoutDashboard
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
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
                  <List
                    className="h-4 w-4"
                    aria-hidden="true"
                  />
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
                preloadIndexes={preloadIndexes}
                scope={scope}
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
                    scope={scope}
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
