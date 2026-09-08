// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewsletterDigestDetail } from './newsletter-digest-detail';
import * as api from '@/lib/newsletter-digest';
import type { DigestCandidate, NewsletterWatch } from '@/lib/newsletter-digest';

vi.mock('./newsletter-context-list', () => ({
  NewsletterContextList: ({ spaceId }: { spaceId: string }) => (
    <div data-testid="context-list">{spaceId}</div>
  ),
}));

const watch: NewsletterWatch = {
  id: 'watch_1',
  chat_id: 1,
  publication_id: 'pub_1',
  space_id: 'space_1',
  name: 'AI Signals',
  watched_from: '2026-09-05 10:00:00',
  created_at: '2026-09-05 10:00:00',
  archive_url: 'https://alphasignal.ai',
  feed_url: 'https://alphasignal.ai/feed.xml',
  fetched_title: 'AlphaSignal',
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
  it('loads candidates and the digest context panel for the watch space', async () => {
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue(watch);
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    await waitFor(() => expect(screen.getByText('A useful post')).toBeInTheDocument());
    expect(screen.getByTestId('context-list')).toHaveTextContent('space_1');
    expect(screen.getByRole('button', { name: 'Retry digest' })).toBeInTheDocument();
  });

  it('marks a candidate promoted only after the promotion endpoint succeeds', async () => {
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);
    vi.spyOn(api, 'promoteDigestCandidate').mockResolvedValue({
      job_id: 'job_1',
      status: 'pending',
      content_type: 'link',
    });

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    await waitFor(() => expect(screen.getByRole('button', { name: 'Create job' })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: 'Create job' }));

    await waitFor(() => expect(screen.getByRole('link', { name: 'Open job' })).toHaveAttribute('href', '/jobs/job_1'));
  });

  it('discards a stale response after subscriptionId changes before it resolves', async () => {
    let resolveFirst!: (value: NewsletterWatch) => void;
    const firstPromise = new Promise<NewsletterWatch>((resolve) => {
      resolveFirst = resolve;
    });
    vi.spyOn(api, 'fetchNewsletterWatch')
      .mockImplementationOnce(() => firstPromise)
      .mockResolvedValueOnce({ ...watch, id: 'watch_2', name: 'Second Newsletter' });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([]);

    const { rerender } = render(<NewsletterDigestDetail subscriptionId="watch_1" />);
    rerender(<NewsletterDigestDetail subscriptionId="watch_2" />);

    await waitFor(() => expect(screen.getByText('Second Newsletter')).toBeInTheDocument());

    resolveFirst({ ...watch, id: 'watch_1', name: 'First Newsletter' });
    await waitFor(() => expect(screen.getByText('Second Newsletter')).toBeInTheDocument());
    expect(screen.queryByText('First Newsletter')).not.toBeInTheDocument();
  });

  it('dismisses only pending candidates, counting them in the label (#613)', async () => {
    const second = { ...candidate, id: 'cand_2', title: 'Second post' };
    const promoting = {
      ...candidate,
      id: 'cand_3',
      title: 'Already promoting',
      status: 'promoting' as const,
    };
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate, second, promoting]);
    const dismiss = vi.spyOn(api, 'dismissDigestCandidate').mockResolvedValue();

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    // The count is the guard, and it counts pending only — not the promoting one.
    const button = await screen.findByRole('button', { name: 'Dismiss rest (2)' });
    fireEvent.click(button);

    await waitFor(() => expect(dismiss).toHaveBeenCalledTimes(2));
    expect(dismiss).toHaveBeenNthCalledWith(1, 'watch_1', 'cand_1', true);
    expect(dismiss).toHaveBeenNthCalledWith(2, 'watch_1', 'cand_2', true);
    // The promoting candidate was never touched and stays on screen.
    expect(screen.getByText('Already promoting')).toBeInTheDocument();
  });

  it('keeps already-dismissed candidates dismissed when the loop fails partway (#613)', async () => {
    const second = { ...candidate, id: 'cand_2', title: 'Second post' };
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate, second]);
    const dismiss = vi
      .spyOn(api, 'dismissDigestCandidate')
      .mockResolvedValueOnce()
      .mockRejectedValueOnce(new Error('network failed'));

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss rest (2)' }));

    // The failure surfaces WITH partial progress, and the first candidate stays
    // dismissed — no rollback.
    await waitFor(() =>
      expect(screen.getByText(/Dismissed 1 of 2\. network failed/)).toBeInTheDocument(),
    );
    expect(dismiss).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('A useful post')).not.toBeInTheDocument();
    expect(screen.getByText('Second post')).toBeInTheDocument();
  });

  it('clears the bulk-dismiss guard for the next watch after subscriptionId changes mid-dismiss (#614)', async () => {
    const second = { ...candidate, id: 'cand_2', title: 'Second post' };
    const third = { ...candidate, id: 'cand_3', title: 'Third post' };
    let resolveDismiss!: () => void;
    const dismissPromise = new Promise<void>((resolve) => {
      resolveDismiss = resolve;
    });
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates')
      .mockResolvedValueOnce([candidate, second])
      .mockResolvedValueOnce([third]);
    vi.spyOn(api, 'dismissDigestCandidate').mockReturnValueOnce(dismissPromise);

    const { rerender } = render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    fireEvent.click(await screen.findByRole('button', { name: 'Dismiss rest (2)' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dismissing...' })).toBeInTheDocument());

    rerender(<NewsletterDigestDetail subscriptionId="watch_2" />);
    await waitFor(() => expect(screen.getByText('Third post')).toBeInTheDocument());

    resolveDismiss();

    // The stale watch_1 dismiss loop must not leave watch_2's guard stuck busy.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Dismiss rest (1)' })).not.toBeDisabled(),
    );
  });
});
