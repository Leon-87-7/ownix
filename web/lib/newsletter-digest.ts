import { apiDelete, apiPostJsonOrThrow, apiPut, parseApiJsonOrThrow } from '@/lib/fetch-utils';

export interface ResolvedIssue {
  slug: string;
  title: string;
  url: string;
}

export interface NewsletterArchiveResolution {
  archive_url: string;
  feed_url: string | null;
  issue_path_prefix: string;
  fetched_title: string;
  recent_issues: ResolvedIssue[];
}

export interface NewsletterWatch {
  id: string;
  chat_id: number;
  publication_id: string;
  space_id: string;
  name: string;
  watched_from: string;
  created_at: string;
  archive_url: string;
  feed_url: string | null;
  fetched_title: string | null;
  candidate_count?: number;
  pending_count?: number;
  promoting_count?: number;
  promoted_count?: number;
  dismissed_count?: number;
  error_count?: number;
}

export interface DigestCandidate {
  id: string;
  space_id: string;
  url: string;
  canonical_url: string;
  title: string | null;
  thumbnail_url: string | null;
  status: 'pending' | 'promoting' | 'promoted' | 'dismissed';
  job_id: string | null;
  created_at: string;
}

export async function fetchNewsletterWatches(): Promise<NewsletterWatch[]> {
  const res = await fetch('/api/newsletter-digest');
  return parseApiJsonOrThrow<NewsletterWatch[]>(res, 'Could not load newsletters');
}

export async function fetchNewsletterWatch(id: string): Promise<NewsletterWatch> {
  const res = await fetch(`/api/newsletter-digest/${id}`);
  return parseApiJsonOrThrow<NewsletterWatch>(res, 'Could not load newsletter');
}

/** Re-resolves `archive_url` server-side and creates the watch with its
 * explicit first-issue delivery (PLAN.md §6/§8, issue #609). */
export async function createNewsletterWatch(input: {
  archive_url: string;
  name: string;
}): Promise<NewsletterWatch> {
  return apiPostJsonOrThrow<NewsletterWatch>('/api/newsletter-digest', input, {
    fallback: (status) =>
      status === 409 ? 'Already watching this newsletter' : 'Could not add newsletter',
  });
}

export async function updateNewsletterWatch(
  id: string,
  input: { name: string },
): Promise<NewsletterWatch> {
  return apiPut<NewsletterWatch>(`/api/newsletter-digest/${id}`, input, 'Could not update newsletter');
}

export async function deleteNewsletterWatch(id: string): Promise<void> {
  await apiDelete(`/api/newsletter-digest/${id}`, 'Could not delete newsletter');
}

export async function fetchDigestCandidates(id: string): Promise<DigestCandidate[]> {
  const res = await fetch(`/api/newsletter-digest/${id}/candidates`);
  return parseApiJsonOrThrow<DigestCandidate[]>(res, 'Could not load candidates');
}

export async function promoteDigestCandidate(
  watchId: string,
  candidateId: string,
): Promise<{ job_id: string; status: string; content_type?: string }> {
  return apiPostJsonOrThrow(
    `/api/newsletter-digest/${watchId}/candidates/${candidateId}/promote`,
    {},
    { fallback: 'Could not create job' },
  );
}

export async function dismissDigestCandidate(
  watchId: string,
  candidateId: string,
  pendingOnly = false,
): Promise<void> {
  // pendingOnly is what `Dismiss rest` sends: a bulk loop works from a UI
  // snapshot, so it must not dismiss a candidate that turned `promoting` in
  // the meantime. Single-card dismiss keeps today's wider behaviour.
  const query = pendingOnly ? '?pending_only=true' : '';
  await apiDelete(
    `/api/newsletter-digest/${watchId}/candidates/${candidateId}${query}`,
    'Could not dismiss candidate',
  );
}

export async function retryEmailDigest(watchId: string): Promise<{ job_id: string }> {
  return apiPostJsonOrThrow(`/api/newsletter-digest/${watchId}/retry`, {}, { fallback: 'Could not retry digest' });
}

/** Read-only: resolves a newsletter's public archive from a URL or sender email. Creates nothing. */
export async function resolveNewsletterArchive(
  query: string,
): Promise<NewsletterArchiveResolution> {
  return apiPostJsonOrThrow<NewsletterArchiveResolution>(
    '/api/newsletter-digest/resolve',
    { query },
    {
      fallback: (status) =>
        status === 429
          ? 'Too many lookups — try again in a minute'
          : 'Could not find a public archive for that newsletter',
    },
  );
}
