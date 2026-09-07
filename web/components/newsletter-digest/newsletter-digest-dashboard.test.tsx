// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewsletterDigestDashboard } from './newsletter-digest-dashboard';
import * as api from '@/lib/newsletter-digest';
import type { NewsletterArchiveResolution, NewsletterWatch } from '@/lib/newsletter-digest';

const RESOLUTION: NewsletterArchiveResolution = {
  archive_url: 'https://alphasignal.ai',
  feed_url: 'https://alphasignal.ai/feed.xml',
  issue_path_prefix: '/news/',
  fetched_title: 'AlphaSignal',
  recent_issues: [
    { slug: 'gpt-6-launch', title: 'GPT-6 launches', url: 'https://alphasignal.ai/news/gpt-6-launch' },
  ],
};

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
  pending_count: 2,
  promoted_count: 1,
  error_count: 0,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('NewsletterDigestDashboard', () => {
  it('loads watches and renders their archive urls', async () => {
    vi.spyOn(api, 'fetchNewsletterWatches').mockResolvedValue([watch]);

    render(<NewsletterDigestDashboard />);

    await waitFor(() => expect(screen.getByText('AI Signals')).toBeInTheDocument());
    expect(screen.getByText('https://alphasignal.ai')).toBeInTheDocument();
  });

  it('resolves, confirms, and prepends the created watch to the feed', async () => {
    vi.spyOn(api, 'fetchNewsletterWatches').mockResolvedValue([]);
    vi.spyOn(api, 'resolveNewsletterArchive').mockResolvedValue(RESOLUTION);
    vi.spyOn(api, 'createNewsletterWatch').mockResolvedValue(watch);

    render(<NewsletterDigestDashboard />);

    await waitFor(() => expect(screen.getByText('No newsletters yet')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByLabelText('Watch name');

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    await waitFor(() =>
      expect(api.createNewsletterWatch).toHaveBeenCalledWith({
        archive_url: 'https://alphasignal.ai',
        name: 'AlphaSignal',
      }),
    );
    await waitFor(() => expect(screen.getByText('AI Signals')).toBeInTheDocument());
  });
});
