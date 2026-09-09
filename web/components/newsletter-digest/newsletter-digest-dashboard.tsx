'use client';

import { useEffect, useState } from 'react';
import { Newspaper } from 'lucide-react';
import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { NewsletterWatchCard } from '@/components/newsletter-digest/newsletter-watch-card';
import { NewsletterArchiveResolver } from '@/components/newsletter-digest/newsletter-archive-resolver';
import {
  createNewsletterWatch,
  deleteNewsletterWatch,
  fetchNewsletterWatches,
  resolveNewsletterArchive,
  retryEmailDigest,
  type NewsletterArchiveResolution,
  type NewsletterWatch,
} from '@/lib/newsletter-digest';
import { describeError } from '@/lib/fetch-utils';
import { toast } from '@/lib/toast';

export function NewsletterDigestDashboard() {
  const [watches, setWatches] = useState<NewsletterWatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);

  async function load() {
    setLoading(true);
    try {
      setWatches(await fetchNewsletterWatches());
      setError(null);
    } catch (err) {
      setError(describeError(err, 'Could not load newsletters'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleConfirm(resolution: NewsletterArchiveResolution, name: string) {
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await createNewsletterWatch({ archive_url: resolution.archive_url, name });
      // Defense in depth alongside the resolver's own submit guard: never
      // show the same watch twice even if a duplicate request slipped through.
      setWatches((current) =>
        current.some((item) => item.id === created.id) ? current : [created, ...current],
      );
      // Remount the resolver so it drops back to its empty input state.
      setFormKey((key) => key + 1);
    } catch (err) {
      setFormError(describeError(err, 'Could not add newsletter'));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm('Stop watching this newsletter and delete its candidates?')) return;
    setBusyId(id);
    setFormError(null);
    try {
      await deleteNewsletterWatch(id);
      setWatches((current) => current.filter((item) => item.id !== id));
      toast('Newsletter removed');
    } catch (err) {
      setFormError(describeError(err, 'Could not stop watching that newsletter'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleRetry(id: string) {
    setBusyId(id);
    setFormError(null);
    try {
      await retryEmailDigest(id);
      await load();
    } catch (err) {
      setFormError(describeError(err, 'Could not retry that digest'));
    } finally {
      setBusyId(null);
    }
  }

  if (loading) {
    return (
      <PageShell>
        <SkeletonBlock className="h-[170px]" />
        <SkeletonBlock className="h-[130px]" />
        <SkeletonBlock className="h-[130px]" />
      </PageShell>
    );
  }

  return (
    <PageShell>
      <PageHeader
        icon={Newspaper}
        title="Newsletter Digest"
        description="Watch a newsletter's public archive, review extracted candidates, then create jobs deliberately."
      />

      <NewsletterArchiveResolver
        key={formKey}
        onResolve={resolveNewsletterArchive}
        onConfirm={handleConfirm}
        // Without this the Confirm button never reflects the in-flight POST,
        // so a double-click fires createNewsletterWatch twice.
        submitting={submitting}
      />
      {formError && (
        <p role="alert" className="text-sm text-status-error">
          {formError}
        </p>
      )}
      {submitting && <p className="text-sm text-muted ownix-shimmer">Adding newsletter...</p>}

      {error && (
        <p role="alert" className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          {error}
        </p>
      )}

      {watches.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
          <p className="text-sm font-medium text-ink">No newsletters yet</p>
          <p className="mt-1 text-sm text-body">
            Find a newsletter&apos;s public archive above to start watching it.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {watches.map((watch) => (
            <NewsletterWatchCard
              key={watch.id}
              watch={watch}
              onDelete={handleDelete}
              onRetry={handleRetry}
              deleting={busyId === watch.id}
              retrying={busyId === watch.id}
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
