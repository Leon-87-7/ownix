'use client';

import { useEffect, useState } from 'react';
import { Newspaper } from 'lucide-react';
import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { NewsletterSubscriptionCard } from '@/components/newsletter-digest/newsletter-subscription-card';
import { NewsletterSubscriptionForm } from '@/components/newsletter-digest/newsletter-subscription-form';
import {
  createNewsletterSubscription,
  deleteNewsletterSubscription,
  fetchNewsletterSubscriptions,
  retryEmailDigest,
  type NewsletterSubscription,
} from '@/lib/newsletter-digest';

export function NewsletterDigestDashboard() {
  const [subscriptions, setSubscriptions] = useState<NewsletterSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    try {
      setSubscriptions(await fetchNewsletterSubscriptions());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load newsletters');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCreate(input: { name: string; sender_email: string }) {
    setSubmitting(true);
    setFormError(null);
    try {
      const created = await createNewsletterSubscription(input);
      setSubscriptions((current) => [created, ...current]);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Could not add newsletter');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm('Delete this newsletter feed and its candidates?')) return;
    setBusyId(id);
    try {
      await deleteNewsletterSubscription(id);
      setSubscriptions((current) => current.filter((item) => item.id !== id));
    } finally {
      setBusyId(null);
    }
  }

  async function handleRetry(id: string) {
    setBusyId(id);
    try {
      await retryEmailDigest(id);
      await load();
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
        description="Route newsletter issues into Ownix, review extracted candidates, then create jobs deliberately."
      />

      <NewsletterSubscriptionForm
        onSubmit={handleCreate}
        submitting={submitting}
        error={formError}
      />

      {error && (
        <p role="alert" className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          {error}
        </p>
      )}

      {subscriptions.length === 0 ? (
        <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
          <p className="text-sm font-medium text-ink">No newsletters yet</p>
          <p className="mt-1 text-sm text-body">
            Add a sender to generate an Ownix alias for that newsletter.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          {subscriptions.map((subscription) => (
            <NewsletterSubscriptionCard
              key={subscription.id}
              subscription={subscription}
              onDelete={handleDelete}
              onRetry={handleRetry}
              deleting={busyId === subscription.id}
              retrying={busyId === subscription.id}
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
