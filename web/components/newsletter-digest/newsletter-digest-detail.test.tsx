// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewsletterDigestDetail } from './newsletter-digest-detail';
import * as api from '@/lib/newsletter-digest';
import type { DigestCandidate, NewsletterSubscription } from '@/lib/newsletter-digest';

vi.mock('./newsletter-context-list', () => ({
  NewsletterContextList: ({ spaceId }: { spaceId: string }) => (
    <div data-testid="context-list">{spaceId}</div>
  ),
}));

const subscription: NewsletterSubscription = {
  id: 'sub_1',
  chat_id: 1,
  name: 'AI Signals',
  sender_email: 'editor@example.com',
  alias_local_part: 'u_token',
  alias: 'u_token@leondev.xyz',
  space_id: 'space_1',
  created_at: '2026-09-05 10:00:00',
  pending_count: 1,
  promoted_count: 0,
  error_count: 1,
};

const candidate: DigestCandidate = {
  id: 'cand_1',
  space_id: 'space_1',
  url: 'https://example.com/post',
  canonical_url: 'https://example.com/post',
  title: 'A useful post',
  thumbnail_url: null,
  status: 'pending',
  job_id: null,
  created_at: '2026-09-05 10:00:00',
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe('NewsletterDigestDetail', () => {
  it('loads candidates and the digest context panel for the subscription space', async () => {
    vi.spyOn(api, 'fetchNewsletterSubscription').mockResolvedValue(subscription);
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);

    render(<NewsletterDigestDetail subscriptionId="sub_1" />);

    await waitFor(() => expect(screen.getByText('A useful post')).toBeInTheDocument());
    expect(screen.getByTestId('context-list')).toHaveTextContent('space_1');
    expect(screen.getByRole('button', { name: 'Retry digest' })).toBeInTheDocument();
  });

  it('marks a candidate promoted only after the promotion endpoint succeeds', async () => {
    vi.spyOn(api, 'fetchNewsletterSubscription').mockResolvedValue({
      ...subscription,
      error_count: 0,
    });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);
    vi.spyOn(api, 'promoteDigestCandidate').mockResolvedValue({
      job_id: 'job_1',
      status: 'pending',
      content_type: 'link',
    });

    render(<NewsletterDigestDetail subscriptionId="sub_1" />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Create job' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Create job' }));

    await waitFor(() => expect(screen.getByRole('link', { name: 'Open job' })).toHaveAttribute('href', '/jobs/job_1'));
  });
});
