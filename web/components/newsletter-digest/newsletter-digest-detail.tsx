'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import { Newspaper, RotateCcw } from 'lucide-react';
import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { CopyButton } from '@/components/ui/copy-button';
import { NewsletterCandidateCard } from '@/components/newsletter-digest/newsletter-candidate-card';
import { NewsletterContextList } from '@/components/newsletter-digest/newsletter-context-list';
import {
  dismissDigestCandidate,
  fetchDigestCandidates,
  fetchNewsletterSubscription,
  promoteDigestCandidate,
  retryEmailDigest,
  type DigestCandidate,
  type NewsletterSubscription,
} from '@/lib/newsletter-digest';

export function NewsletterDigestDetail({ subscriptionId }: { subscriptionId: string }) {
  const [subscription, setSubscription] = useState<NewsletterSubscription | null>(null);
  const [candidates, setCandidates] = useState<DigestCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyCandidateId, setBusyCandidateId] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const [nextSubscription, nextCandidates] = await Promise.all([
        fetchNewsletterSubscription(subscriptionId),
        fetchDigestCandidates(subscriptionId),
      ]);
      setSubscription(nextSubscription);
      setCandidates(nextCandidates);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load newsletter digest');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [subscriptionId]);

  const visibleCandidates = useMemo(
    () => candidates.filter((candidate) => candidate.status !== 'dismissed'),
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

  if (!subscription) {
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
        title={subscription.name}
        description={
          <span className="font-mono text-label">
            {subscription.sender_email} to {subscription.alias}
          </span>
        }
        action={<CopyButton value={subscription.alias} ariaLabel="Copy alias" label="Copy alias" />}
      />

      {error && (
        <p role="alert" className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          {error}
        </p>
      )}

      {(subscription.error_count ?? 0) > 0 && (
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
            <span className="font-mono text-label text-muted tabular-nums">
              {visibleCandidates.length} visible
            </span>
          </div>
          {visibleCandidates.length === 0 ? (
            <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
              <p className="text-sm font-medium text-ink">No candidates yet</p>
              <p className="mt-1 text-sm text-body">
                Incoming issues will appear here after the email digest worker runs.
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
                  busy={busyCandidateId === candidate.id}
                />
              ))}
            </div>
          )}
        </section>

        <aside className="space-y-3">
          <h2 className="text-headline font-semibold text-ink">Context</h2>
          <NewsletterContextList spaceId={subscription.space_id} />
        </aside>
      </div>
    </PageShell>
  );
}
