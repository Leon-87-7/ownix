'use client';

import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import type { FormEvent } from 'react';
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
import { SubmitUrlForm } from '@/components/submit-url-form';
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { FileCode2, Plus } from 'lucide-react';
import type { JobSummary } from '@/components/job-card';

const CONTENT_TYPES = new Set(['short', 'long', 'article', 'repo']);

const CONTENT_TYPE_FILTERS = [
  { label: 'All', value: '' },
  { label: 'Short', value: 'short' },
  { label: 'Long', value: 'long' },
  { label: 'Article', value: 'article' },
  { label: 'Repo', value: 'repo' },
  {
    label: 'Docs',
    value: 'docs',
    href: '/doc-parser',
    dividerBefore: true,
    icon: FileCode2,
  },
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
  const [submitUrl, setSubmitUrl] = useState('');
  const [submitTemplate, setSubmitTemplate] = useState('summary');
  const [freestylePrompt, setFreestylePrompt] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [optimisticJobs, setOptimisticJobs] = useState<JobSummary[]>(
    [],
  );
  const [dialogOpen, setDialogOpen] = useState(false);
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
      CONTENT_TYPE_FILTERS.map(
        ({ label, value, href, dividerBefore, icon }, i) => ({
          label,
          value,
          href,
          icon,
          count: href
            ? undefined
            : value
              ? (contentTypeCounts[value] ?? 0)
              : totalCount,
          dividerBefore: dividerBefore ?? i > 0,
        }),
      ),
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

  const submitJob = useCallback(
    async (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault();
      const url = submitUrl.trim();
      if (!url || submitting) return;
      const tempId = `pending-${Date.now()}`;
      const placeholder: JobSummary = {
        id: tempId,
        title: 'Submitting…',
        url,
        content_type: ctFilter || 'short',
        status: 'pending',
        created_at: new Date().toISOString(),
      };
      setSubmitError(null);
      setSubmitting(true);
      setOptimisticJobs((current) => [placeholder, ...current]);
      try {
        const payload: Record<string, string> = {
          url,
          template: submitTemplate,
        };
        if (submitTemplate === 'freestyle')
          payload.freestyle_prompt = freestylePrompt.trim();
        const res = await fetch('/api/jobs', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok)
          throw new Error(data.detail || 'Could not submit job');
        // The submit is accepted at this point. reload() swallows fetch errors
        // (it is shared with background polling), so the accepted job must not
        // depend on the refresh landing: promote the placeholder to the real
        // job from the response and keep it until the feed carries that id —
        // the reconcile effect on `jobs` removes it, and in-flight polling
        // retries the refresh for as long as the row reads as pending.
        const acceptedId =
          typeof data.id === 'string' && data.id ? data.id : null;
        if (acceptedId) {
          setOptimisticJobs((current) =>
            current.map((job) =>
              job.id === tempId
                ? {
                    ...job,
                    id: acceptedId,
                    title:
                      typeof data.title === 'string'
                        ? data.title
                        : null,
                    content_type:
                      typeof data.content_type === 'string'
                        ? data.content_type
                        : job.content_type,
                    status:
                      typeof data.status === 'string'
                        ? data.status
                        : job.status,
                  }
                : job,
            ),
          );
        }
        setSubmitUrl('');
        setFreestylePrompt('');
        setDialogOpen(false);
        await reload();
        if (!acceptedId) {
          // No job id in the response — nothing to reconcile against, so fall
          // back to dropping the placeholder after the refresh attempt.
          setOptimisticJobs((current) =>
            current.filter((job) => job.id !== tempId),
          );
        }
      } catch (e) {
        const message =
          e instanceof Error ? e.message : 'Could not submit job';
        setSubmitError(message);
        setOptimisticJobs((current) =>
          current.filter((job) => job.id !== tempId),
        );
      } finally {
        setSubmitting(false);
      }
    },
    [
      ctFilter,
      freestylePrompt,
      reload,
      submitTemplate,
      submitUrl,
      submitting,
    ],
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
          <span className="text-sm font-medium italic text-body">
            Servavi.
          </span>
          <span className="text-sm font-medium italic text-body">
            Ditavi.
          </span>
          <span className="text-sm font-medium italic text-body">
            Inveni.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-muted">
            Saved.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-muted">
            Enriched.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-muted">
            Found.
          </span>
        </div>

        <Dialog
          open={dialogOpen}
          onOpenChange={setDialogOpen}
        >
          <DialogTrigger asChild>
            <button
              type="button"
              className="ml-auto hidden h-9 items-center gap-2 rounded-md border border-line border-b-2 border-b-signal bg-surface px-3.5 text-sm font-medium text-body transition-ui hover:text-ink active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas sm:inline-flex motion-reduce:active:scale-100"
            >
              <Plus
                aria-hidden="true"
                className="h-4 w-4"
              />
              Submit URL
            </button>
          </DialogTrigger>
          <DialogContent>
            <DialogTitle>Submit URL</DialogTitle>
            <div className="mt-4">
              <SubmitUrlForm
                url={submitUrl}
                onUrlChange={setSubmitUrl}
                template={submitTemplate}
                onTemplateChange={setSubmitTemplate}
                freestylePrompt={freestylePrompt}
                onFreestylePromptChange={setFreestylePrompt}
                submitting={submitting}
                error={submitError}
                onSubmit={submitJob}
              />
            </div>
          </DialogContent>
        </Dialog>
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
        actionSlot={
          /* Mobile-only (<sm): the submit trigger lives in the first slot of the
             chip wrap grid so it flows with the filters instead of floating alone.
             Signal underline + signal text mark it as the row's one action without
             matching the active chip's full signal fill (The Signal Rule). Opens
             the same dialog as the sm+ header trigger. */
          <button
            type="button"
            onClick={() => setDialogOpen(true)}
            aria-label="Submit URL"
            aria-haspopup="dialog"
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-md border border-line border-b-2 border-b-signal bg-surface px-1.5 text-[13px] font-medium text-signal transition-ui hover:bg-raised active:scale-[0.96] motion-reduce:active:scale-100 sm:hidden"
          >
            <Plus
              aria-hidden="true"
              className="h-4 w-4"
            />
            Submit
          </button>
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
