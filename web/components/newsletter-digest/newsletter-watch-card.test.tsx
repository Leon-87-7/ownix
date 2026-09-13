// @vitest-environment jsdom
import { fireEvent, render, screen, within } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { NewsletterWatchCard } from './newsletter-watch-card';
import type { NewsletterWatch } from '@/lib/newsletter-digest';

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
  candidate_count: 4,
  pending_count: 2,
  promoted_count: 1,
  dismissed_count: 1,
  error_count: 1,
};

describe('NewsletterWatchCard', () => {
  it('renders the archive url, counts, and detail link', () => {
    render(<NewsletterWatchCard watch={watch} />);

    expect(screen.getByRole('link')).toHaveAttribute('href', '/newsletter-digest/watch_1');
    expect(screen.getByText('AI Signals')).toBeInTheDocument();
    expect(screen.getByText('https://alphasignal.ai')).toBeInTheDocument();
    expect(screen.getByText('2 pending')).toBeInTheDocument();
    expect(screen.getByText('1 promoted')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
  });

  it('calls retry with the watch id', () => {
    const onRetry = vi.fn();
    render(<NewsletterWatchCard watch={watch} onRetry={onRetry} />);

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(onRetry).toHaveBeenCalledWith('watch_1');
  });

  it('calls delete only after confirming in the dialog', async () => {
    const onDelete = vi.fn();
    render(<NewsletterWatchCard watch={watch} onDelete={onDelete} />);

    fireEvent.click(screen.getByRole('button', { name: 'Delete AI Signals' }));
    expect(onDelete).not.toHaveBeenCalled();

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: 'Stop watching' }));

    expect(onDelete).toHaveBeenCalledWith('watch_1');
  });
});
