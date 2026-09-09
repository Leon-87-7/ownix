'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ExternalLink, LayoutDashboard, List, Newspaper, RotateCcw, Trash2 } from 'lucide-react';
import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { CopyButton } from '@/components/ui/copy-button';
import { DateTime } from '@/components/ui/date-time';
import { NewsletterCandidateCard } from '@/components/newsletter-digest/newsletter-candidate-card';
import { NewsletterCandidateRow } from '@/components/newsletter-digest/newsletter-candidate-row';
import { useSpaceContext } from '@/lib/hooks/useSpaceContext';
import {
  dismissDigestCandidate,
  fetchDigestCandidates,
  fetchNewsletterWatch,
  promoteDigestCandidate,
  retryEmailDigest,
  type DigestCandidate,
  type NewsletterWatch,
} from '@/lib/newsletter-digest';
import { describeError } from '@/lib/fetch-utils';

const MarkdownEditor = dynamic(() => import('@/components/ui/markdown-editor'), {
  ssr: false,
  loading: () => <p className="text-sm text-muted">Loading context...</p>,
});

// Mirrors the Feed page's own grid/list toggle (app/(dashboard)/feed/page.tsx)
// — same key shape, its own storage slot since the two pages' preferences
// are independent.
const LAYOUT_KEY = 'ownix.newsletter-digest.candidates-layout';

function asUtcIso(raw: string): string {
  return /[Zz]|[+-]\d\d:?\d\d$/.test(raw) ? raw : `${raw.replace(' ', 'T')}Z`;
}

function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export function NewsletterDigestDetail({ subscriptionId }: { subscriptionId: string }) {
  const [watch, setWatch] = useState<NewsletterWatch | null>(null);
  const [candidates, setCandidates] = useState<DigestCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyCandidateId, setBusyCandidateId] = useState<string | null>(null);
  const [dismissingRest, setDismissingRest] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [layout, setLayout] = useState<'grid' | 'list'>('grid');
  // Guards against a stale load() — from a prior subscriptionId — resolving after
  // a newer one has already started and overwriting its state with old data.
  const requestIdRef = useRef(0);

  useEffect(() => {
    try {
      if (window.localStorage.getItem(LAYOUT_KEY) === 'list') setLayout('list');
    } catch {
      // storage unavailable (private mode) - stay on the grid default
    }
  }, []);

  function switchLayout(mode: 'grid' | 'list') {
    setLayout(mode);
    try {
      window.localStorage.setItem(LAYOUT_KEY, mode);
    } catch {
      // non-persistent session is fine
    }
  }

  async function load() {
    const requestId = ++requestIdRef.current;
    setLoading(true);
    try {
      const [nextWatch, nextCandidates] = await Promise.all([
        fetchNewsletterWatch(subscriptionId),
        fetchDigestCandidates(subscriptionId),
      ]);
      if (requestId !== requestIdRef.current) return;
      setWatch(nextWatch);
      setCandidates(nextCandidates);
      setError(null);
    } catch (err) {
      if (requestId !== requestIdRef.current) return;
      setError(describeError(err, 'Could not load newsletter digest'));
    } finally {
      if (requestId === requestIdRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [subscriptionId]);

  const visibleCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.status !== 'dismissed'),
    [candidates],
  );

  const pendingCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.status === 'pending'),
    [candidates],
  );

  const { blobs } = useSpaceContext(watch?.space_id ?? '');
  // Newest issue first: context_blobs are appended (sort_order = max+1) once
  // per processed issue, so list_context_blobs' chronological-ascending order
  // reversed is newest-first for the feed.
  //
  // Approximation: candidates carry no issue foreign key yet, so every
  // visible candidate nests under the newest issue only — older issues show
  // their note with no links. A real per-issue split needs that FK on
  // digest_candidates, stamped at insert time in email_digest.run().
  const issues = useMemo(() => [...blobs].reverse(), [blobs]);

  async function handlePromote(candidateId: string) {
    setBusyCandidateId(candidateId);
    try {
      const result = await promoteDigestCandidate(subscriptionId, candidateId);
      setCandidates((current) =>
        current.map((candidate) =>
          candidate.id === candidateId
            ? { ...candidate, status: 'promoted', job_id: result.job_id }
            : candidate,
        ),
      );
    } catch (err) {
      setError(describeError(err, 'Could not create job'));
    } finally {
      setBusyCandidateId(null);
    }
  }

  async function handleDismiss(candidateId: string) {
    setBusyCandidateId(candidateId);
    try {
      await dismissDigestCandidate(subscriptionId, candidateId);
      setCandidates((current) =>
        current.map((candidate) =>
          candidate.id === candidateId ? { ...candidate, status: 'dismissed' } : candidate,
        ),
      );
    } catch (err) {
      setError(describeError(err, 'Could not dismiss candidate'));
    } finally {
      setBusyCandidateId(null);
    }
  }

  async function handleDismissRest() {
    // Loops the existing per-candidate DELETE rather than adding a batch
    // endpoint: all-or-nothing semantics are wrong here, so a failure partway
    // through keeps everything already dismissed and surfaces the error.
    const requestId = requestIdRef.current;
    const targets = pendingCandidates;
    setDismissingRest(true);
    setError(null);
    let dismissed = 0;
    let failure: unknown = null;
    for (const candidate of targets) {
      try {
        await dismissDigestCandidate(subscriptionId, candidate.id, true);
        dismissed += 1;
        // Only flip a row that is still pending: a concurrent promote may have
        // moved it on, and the server's pending-only guard would have rejected
        // our DELETE in that case anyway.
        setCandidates((current) =>
          current.map((item) =>
            item.id === candidate.id && item.status === 'pending'
              ? { ...item, status: 'dismissed' }
              : item,
          ),
        );
      } catch (err) {
        // Keep going: one candidate failing (e.g. it turned `promoting`) must
        // not strand the rest still pending.
        failure = err;
      }
    }
    // A load() for a different watch may have started while we were looping —
    // same guard load() uses, so its state never lands on another watch's view.
    if (requestId !== requestIdRef.current) {
      setDismissingRest(false);
      return;
    }
    if (failure) {
      const reason = describeError(failure, 'Some candidates failed');
      setError(`Dismissed ${dismissed} of ${targets.length}. ${reason}`);
    }
    setDismissingRest(false);
  }

  async function handleRetry() {
    setRetrying(true);
    try {
      await retryEmailDigest(subscriptionId);
      await load();
    } catch (err) {
      setError(describeError(err, 'Could not retry digest'));
    } finally {
      setRetrying(false);
    }
  }

  if (loading) {
    return (
      <PageShell>
        <SkeletonBlock className="h-[80px]" />
        <SkeletonBlock className="h-[170px]" />
        <SkeletonBlock className="h-[170px]" />
      </PageShell>
    );
  }

  if (!watch) {
    return (
      <PageShell>
        <p className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          {error ?? 'Newsletter not found'}
        </p>
      </PageShell>
    );
  }

  function renderCandidates(list: DigestCandidate[]) {
    if (layout === 'list') {
      return (
        <div className="flex flex-col gap-2">
          {list.map((candidate) => (
            <NewsletterCandidateRow
              key={candidate.id}
              candidate={candidate}
              onPromote={handlePromote}
              onDismiss={handleDismiss}
              busy={dismissingRest || busyCandidateId === candidate.id}
            />
          ))}
        </div>
      );
    }
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {list.map((candidate) => (
          <NewsletterCandidateCard
            key={candidate.id}
            candidate={candidate}
            onPromote={handlePromote}
            onDismiss={handleDismiss}
            busy={dismissingRest || busyCandidateId === candidate.id}
          />
        ))}
      </div>
    );
  }

  const nothingYet = visibleCandidates.length === 0 && issues.length === 0;

  return (
    <PageShell>
      <Link
        href="/newsletter-digest"
        className="inline-flex items-center gap-1 text-sm font-medium text-muted transition-ui hover:text-ink"
      >
        <OwnixChevronRight className="h-3.5 w-3.5 rotate-180" aria-hidden="true" />
        Newsletter Digest
      </Link>
      <PageHeader
        icon={Newspaper}
        title={watch.name}
        description={<span className="font-mono text-label">{watch.archive_url}</span>}
        action={<CopyButton value={watch.archive_url} ariaLabel="Copy archive URL" label="Copy URL" />}
      />

      {error && (
        <p role="alert" className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          {error}
        </p>
      )}

      {(watch.error_count ?? 0) > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-status-error-tint px-4 py-3">
          <p className="text-sm text-status-error">
            A digest issue failed before its payload was cleared.
          </p>
          <button
            type="button"
            onClick={handleRetry}
            disabled={retrying}
            className="flex h-8 items-center gap-1.5 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] active:bg-signal-deep disabled:bg-surface disabled:text-muted"
          >
            <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
            {retrying ? <span className="ownix-shimmer">Retrying...</span> : 'Retry digest'}
          </button>
        </div>
      )}

      {nothingYet ? (
        <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
          <p className="text-sm font-medium text-ink">No candidates yet</p>
          <p className="mt-1 text-sm text-body">
            Incoming issues will appear here after the newsletter poll worker runs.
          </p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              {pendingCandidates.length > 0 && (
                // The count in the label is the guard — no confirm modal, since
                // dismissal is a soft status flip that leaves the row in the
                // dedup set (CONTEXT.md, [[Job delete]]).
                <button
                  type="button"
                  onClick={handleDismissRest}
                  disabled={dismissingRest || busyCandidateId !== null}
                  className="flex h-8 items-center gap-1.5 rounded-md border border-line px-3 text-label font-medium text-muted transition-ui hover:border-status-error hover:text-status-error active:scale-[0.96] disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  {dismissingRest ? (
                    <span className="ownix-shimmer">Dismissing...</span>
                  ) : (
                    <>
                      Dismiss rest{' '}
                      <span className="font-mono tabular-nums">({pendingCandidates.length})</span>
                    </>
                  )}
                </button>
              )}
              <span className="font-mono text-label text-muted tabular-nums">
                {visibleCandidates.length} visible
              </span>
            </div>
            {visibleCandidates.length > 0 && (
              <div
                role="group"
                aria-label="Layout"
                className="flex items-center gap-0.5 rounded-lg border border-line bg-surface p-0.5"
              >
                <button
                  type="button"
                  aria-pressed={layout === 'grid'}
                  aria-label="Grid layout"
                  onClick={() => switchLayout('grid')}
                  className={`inline-flex h-7 w-8 items-center justify-center rounded-md transition-ui ${
                    layout === 'grid'
                      ? 'bg-signal text-onsignal'
                      : 'text-muted hover:bg-raised hover:text-ink'
                  }`}
                >
                  <LayoutDashboard className="h-4 w-4" aria-hidden="true" />
                </button>
                <button
                  type="button"
                  aria-pressed={layout === 'list'}
                  aria-label="List layout"
                  onClick={() => switchLayout('list')}
                  className={`inline-flex h-7 w-8 items-center justify-center rounded-md transition-ui ${
                    layout === 'list'
                      ? 'bg-signal text-onsignal'
                      : 'text-muted hover:bg-raised hover:text-ink'
                  }`}
                >
                  <List className="h-4 w-4" aria-hidden="true" />
                </button>
              </div>
            )}
          </div>

          {issues.length > 0 ? (
            <div className="space-y-10">
              {issues.map((issue, i) => (
                <article key={issue.id} className={i > 0 ? 'border-t border-line pt-8' : undefined}>
                  <p className="font-mono text-label text-muted">
                    <DateTime iso={asUtcIso(issue.created_at)} />
                  </p>
                  <h2 className="mt-1 text-headline tracking-headline font-semibold text-balance text-ink">
                    {issue.name}
                  </h2>
                  {issue.source_url && (
                    <a
                      href={issue.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-flex items-center gap-1 font-mono text-label text-muted transition-ui hover:text-signal"
                    >
                      <ExternalLink className="h-3 w-3" aria-hidden="true" />
                      {hostname(issue.source_url)}
                    </a>
                  )}
                  <div className="mt-3">
                    <MarkdownEditor initialMarkdown={issue.content} readOnly label="" />
                  </div>
                  {i === 0 && visibleCandidates.length > 0 && (
                    <div className="mt-6">
                      <p className="mb-3 font-mono text-mono-label uppercase tracking-wider text-muted">
                        Links from this issue
                      </p>
                      {renderCandidates(visibleCandidates)}
                    </div>
                  )}
                </article>
              ))}
            </div>
          ) : (
            renderCandidates(visibleCandidates)
          )}
        </>
      )}
    </PageShell>
  );
}
