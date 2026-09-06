// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewsletterDigestDashboard } from './newsletter-digest-dashboard';
import * as api from '@/lib/newsletter-digest';
import type { NewsletterSubscription } from '@/lib/newsletter-digest';

const subscription: NewsletterSubscription = {
  id: 'sub_1',
  chat_id: 1,
  name: 'AI Signals',
  sender_email: 'editor@example.com',
  alias_local_part: 'u_token',
  alias: 'u_token@leondev.xyz',
  space_id: 'space_1',
  created_at: '2026-09-05 10:00:00',
  pending_count: 2,
  promoted_count: 1,
  error_count: 0,
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('NewsletterDigestDashboard', () => {
  it('loads subscriptions and renders their generated aliases', async () => {
    vi.spyOn(api, 'fetchNewsletterSubscriptions').mockResolvedValue([subscription]);

    render(<NewsletterDigestDashboard />);

    await waitFor(() => expect(screen.getByText('AI Signals')).toBeInTheDocument());
    expect(screen.getByText('u_token@leondev.xyz')).toBeInTheDocument();
  });

  it('creates a subscription from the form and prepends it to the feed', async () => {
    vi.spyOn(api, 'fetchNewsletterSubscriptions').mockResolvedValue([]);
    vi.spyOn(api, 'createNewsletterSubscription').mockResolvedValue(subscription);

    render(<NewsletterDigestDashboard />);

    await waitFor(() => expect(screen.getByText('No newsletters yet')).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'AI Signals' } });
    fireEvent.change(screen.getByLabelText('Sender email'), {
      target: { value: 'editor@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));

    await waitFor(() => expect(screen.getByText('AI Signals')).toBeInTheDocument());
  });
});
