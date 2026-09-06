// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { NewsletterSubscriptionCard } from './newsletter-subscription-card';
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
  candidate_count: 4,
  pending_count: 2,
  promoted_count: 1,
  dismissed_count: 1,
  error_count: 1,
};

describe('NewsletterSubscriptionCard', () => {
  it('renders the alias, sender, counts, and detail link', () => {
    render(<NewsletterSubscriptionCard subscription={subscription} />);

    expect(screen.getByRole('link')).toHaveAttribute('href', '/newsletter-digest/sub_1');
    expect(screen.getByText('AI Signals')).toBeInTheDocument();
    expect(screen.getByText('editor@example.com')).toBeInTheDocument();
    expect(screen.getByText('u_token@leondev.xyz')).toBeInTheDocument();
    expect(screen.getByText('2 pending')).toBeInTheDocument();
    expect(screen.getByText('1 promoted')).toBeInTheDocument();
    expect(screen.getByText('error')).toBeInTheDocument();
  });

  it('calls retry and delete actions with the subscription id', () => {
    const onRetry = vi.fn();
    const onDelete = vi.fn();
    render(
      <NewsletterSubscriptionCard
        subscription={subscription}
        onRetry={onRetry}
        onDelete={onDelete}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete AI Signals' }));

    expect(onRetry).toHaveBeenCalledWith('sub_1');
    expect(onDelete).toHaveBeenCalledWith('sub_1');
  });
});
