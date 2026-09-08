'use client';

import Link from 'next/link';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Newspaper, RotateCcw, Trash2 } from 'lucide-react';
import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { CopyButton } from '@/components/ui/copy-button';
import { NewsletterCandidateCard } from '@/components/newsletter-digest/newsletter-candidate-card';
import { NewsletterContextList } from '@/components/newsletter-digest/newsletter-context-list';
import {
  dismissDigestCandidate,
  fetchDigestCandidates,
  fetchNewsletterWatch,
  promoteDigestCandidate,
  retryEmailDigest,
  type DigestCandidate,
  type NewsletterWatch,
} from '@/lib/newsletter-digest';

export function NewsletterDigestDetail({ subscriptionId }: { subscriptionId: string }) {
  const [watch, setWatch] = useState<NewsletterWatch | null>(null);
  const [candidates, setCandidates] = useState<DigestCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyCandidateId, setBusyCandidateId] = useState<string | null>(null);
  const [dismissingRest, setDismissingRest] = useState(false);
  const [retrying, setRetrying] = useState(false);
  // Guards against a stale load() — from a prior subscriptionId — resolving after
  // a newer one has already started and overwriting its state with old data.
  const requestIdRef = useRef(0);

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
      setError(err instanceof Error ? err.message : 'Could not load newsletter digest');
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
      setError(err instanceof Error ? err.message : 'Could not create job');
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
      setError(err instanceof Error ? err.message : 'Could not dismiss candidate');
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
      const reason = failure instanceof Error ? failure.message : 'Some candidates failed';
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
      setError(err instanceof Error ? err.message : 'Could not retry digest');
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
            {retrying ? 'Retrying...' : 'Retry digest'}
          </button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(320px,0.9fr)]">
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-headline font-semibold text-ink">Candidates</h2>
            <div className="flex items-center gap-3">
              {pendingCandidates.length > 0 && (
                // The count in the label is the guard — no confirm modal, since
                // dismissal is a soft status flip that leaves the row in the
                // dedup set (CONTEXT.md, [[Job delete]]).
                // Real button chrome and an error-hover: this is the most
                // destructive control in the feature and the count is its only
                // guard, so it must not read as ambient metadata next to the
                // "N visible" counter. The count itself is mono/tabular —
                // DESIGN.md's Mono Fact Rule — because the number IS the guard.
                <button
                  type="button"
                  onClick={handleDismissRest}
                  disabled={dismissingRest || busyCandidateId !== null}
                  className="flex h-8 items-center gap-1.5 rounded-md border border-line px-3 text-label font-medium text-muted transition-ui hover:border-status-error hover:text-status-error disabled:opacity-50"
                >
                  <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                  {dismissingRest ? (
                    'Dismissing...'
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
          </div>
          {visibleCandidates.length === 0 ? (
            <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
              <p className="text-sm font-medium text-ink">No candidates yet</p>
              <p className="mt-1 text-sm text-body">
                Incoming issues will appear here after the newsletter poll worker runs.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {visibleCandidates.map((candidate) => (
                <NewsletterCandidateCard
                  key={candidate.id}
                  candidate={candidate}
                  onPromote={handlePromote}
                  onDismiss={handleDismiss}
                  // Locked during a bulk dismiss too: otherwise a card the
                  // loop is about to DELETE stays clickable, and only the
                  // server's pending-only guard prevents the collision.
                  busy={dismissingRest || busyCandidateId === candidate.id}
                />
              ))}
            </div>
          )}
        </section>

        <aside className="space-y-3">
          <h2 className="text-headline font-semibold text-ink">Context</h2>
          <NewsletterContextList spaceId={watch.space_id} />
        </aside>
      </div>
    </PageShell>
  );
}
