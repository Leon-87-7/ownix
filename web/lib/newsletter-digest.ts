import { apiDelete, apiPostJsonOrThrow, apiPut, parseApiJsonOrThrow } from '@/lib/fetch-utils';

export interface NewsletterSubscription {
  id: string;
  chat_id: number;
  name: string;
  sender_email: string;
  alias_local_part: string;
  alias: string;
  space_id: string;
  created_at: string;
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

export async function fetchNewsletterSubscriptions(): Promise<NewsletterSubscription[]> {
  const res = await fetch('/api/newsletter-digest');
  return parseApiJsonOrThrow<NewsletterSubscription[]>(res, 'Could not load newsletters');
}

export async function fetchNewsletterSubscription(id: string): Promise<NewsletterSubscription> {
  const res = await fetch(`/api/newsletter-digest/${id}`);
  return parseApiJsonOrThrow<NewsletterSubscription>(res, 'Could not load newsletter');
}

export async function createNewsletterSubscription(input: {
  name: string;
  sender_email: string;
}): Promise<NewsletterSubscription> {
  return apiPostJsonOrThrow<NewsletterSubscription>('/api/newsletter-digest', input, {
    fallback: 'Could not add newsletter',
  });
}

export async function updateNewsletterSubscription(
  id: string,
  input: { name: string; sender_email: string },
): Promise<NewsletterSubscription> {
  return apiPut<NewsletterSubscription>(
    `/api/newsletter-digest/${id}`,
    input,
    'Could not update newsletter',
  );
}

export async function deleteNewsletterSubscription(id: string): Promise<void> {
  await apiDelete(`/api/newsletter-digest/${id}`, 'Could not delete newsletter');
}

export async function fetchDigestCandidates(id: string): Promise<DigestCandidate[]> {
  const res = await fetch(`/api/newsletter-digest/${id}/candidates`);
  return parseApiJsonOrThrow<DigestCandidate[]>(res, 'Could not load candidates');
}

export async function promoteDigestCandidate(
  subscriptionId: string,
  candidateId: string,
): Promise<{ job_id: string; status: string; content_type?: string }> {
  return apiPostJsonOrThrow(
    `/api/newsletter-digest/${subscriptionId}/candidates/${candidateId}/promote`,
    {},
    { fallback: 'Could not create job' },
  );
}

export async function dismissDigestCandidate(
  subscriptionId: string,
  candidateId: string,
): Promise<void> {
  await apiDelete(
    `/api/newsletter-digest/${subscriptionId}/candidates/${candidateId}`,
    'Could not dismiss candidate',
  );
}

export async function retryEmailDigest(subscriptionId: string): Promise<{ job_id: string }> {
  return apiPostJsonOrThrow(
    `/api/newsletter-digest/${subscriptionId}/retry`,
    {},
    { fallback: 'Could not retry digest' },
  );
}
