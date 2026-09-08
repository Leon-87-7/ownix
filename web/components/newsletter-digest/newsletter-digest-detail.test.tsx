// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { NewsletterDigestDetail } from './newsletter-digest-detail';
import * as api from '@/lib/newsletter-digest';
import type { DigestCandidate, NewsletterWatch } from '@/lib/newsletter-digest';
import { useSpaceContext } from '@/lib/hooks/useSpaceContext';

vi.mock('@/lib/hooks/useSpaceContext', () => ({ useSpaceContext: vi.fn() }));

const mockedUseSpaceContext = vi.mocked(useSpaceContext);

vi.mock('next/dynamic', () => ({
  default: () =>
    function MockMarkdownEditor({ initialMarkdown }: { initialMarkdown: string }) {
      return <div data-testid="markdown-editor">{initialMarkdown}</div>;
    },
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

beforeEach(() => {
  mockedUseSpaceContext.mockReturnValue({
    blobs: [],
    loading: false,
    blobError: null,
    setBlobError: vi.fn(),
    addBlob: vi.fn(),
    updateBlob: vi.fn(),
    deleteBlob: vi.fn(),
    reorderBlob: vi.fn(),
    patchBlobName: vi.fn(),
  });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('NewsletterDigestDetail', () => {
  it('loads candidates for the watch', async () => {
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue(watch);
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    await waitFor(() => expect(screen.getByText('A useful post')).toBeInTheDocument());
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

  it('renders issues newest-first, nesting candidates under the newest one only', async () => {
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);
    mockedUseSpaceContext.mockReturnValue({
      blobs: [
        {
          id: 'blob_older',
          space_id: 'space_1',
          name: 'Older issue',
          content: 'Older note',
          source_url: 'https://older.example.com/p/older',
          sort_order: 0,
          created_at: '2026-09-01 10:00:00',
          updated_at: '2026-09-01 10:00:00',
        },
        {
          id: 'blob_newest',
          space_id: 'space_1',
          name: 'Newest issue',
          content: 'Newest note',
          source_url: 'https://newest.example.com/p/newest',
          sort_order: 1,
          created_at: '2026-09-05 10:00:00',
          updated_at: '2026-09-05 10:00:00',
        },
      ],
      loading: false,
      blobError: null,
      setBlobError: vi.fn(),
      addBlob: vi.fn(),
      updateBlob: vi.fn(),
      deleteBlob: vi.fn(),
      reorderBlob: vi.fn(),
      patchBlobName: vi.fn(),
    });

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    await waitFor(() => expect(screen.getByText('Newest issue')).toBeInTheDocument());
    // Newest-first order: the newest issue's heading precedes the older one's.
    const headings = screen.getAllByRole('heading', { level: 2 });
    const order = headings.map((h) => h.textContent);
    expect(order.indexOf('Newest issue')).toBeLessThan(order.indexOf('Older issue'));

    expect(screen.getByRole('link', { name: /newest\.example\.com/i })).toHaveAttribute(
      'href',
      'https://newest.example.com/p/newest',
    );
    // Only the newest issue nests the candidate list.
    expect(screen.getByText('Links from this issue')).toBeInTheDocument();
    expect(screen.getByText('A useful post')).toBeInTheDocument();
  });

  it('switches candidates between the preview card and the dense list row', async () => {
    vi.spyOn(api, 'fetchNewsletterWatch').mockResolvedValue({ ...watch, error_count: 0 });
    vi.spyOn(api, 'fetchDigestCandidates').mockResolvedValue([candidate]);

    render(<NewsletterDigestDetail subscriptionId="watch_1" />);

    await waitFor(() => expect(screen.getByText('A useful post')).toBeInTheDocument());
    // Default is grid — the card shows a "Create job" affordance either way,
    // so assert on the layout buttons' pressed state instead.
    expect(screen.getByRole('button', { name: 'Grid layout' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );

    fireEvent.click(screen.getByRole('button', { name: 'List layout' }));

    expect(screen.getByRole('button', { name: 'List layout' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Grid layout' })).toHaveAttribute(
      'aria-pressed',
      'false',
    );
    expect(screen.getByText('A useful post')).toBeInTheDocument();
  });
});
