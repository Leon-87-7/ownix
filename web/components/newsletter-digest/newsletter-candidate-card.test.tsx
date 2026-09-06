// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { NewsletterCandidateCard } from './newsletter-candidate-card';
import type { DigestCandidate } from '@/lib/newsletter-digest';

const candidate: DigestCandidate = {
  id: 'cand_1',
  space_id: 'space_1',
  url: 'https://example.com/post?utm_source=newsletter',
  canonical_url: 'https://example.com/post',
  title: 'A useful post',
  thumbnail_url: null,
  status: 'pending',
  job_id: null,
  created_at: '2026-09-05 10:00:00',
};

describe('NewsletterCandidateCard', () => {
  it('renders the candidate URL separately from the create-job action', () => {
    const onPromote = vi.fn();
    render(<NewsletterCandidateCard candidate={candidate} onPromote={onPromote} />);

    expect(screen.getByRole('link', { name: 'A useful post' })).toHaveAttribute(
      'href',
      candidate.url,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Create job' }));
    expect(onPromote).toHaveBeenCalledWith('cand_1');
  });

  it('calls dismiss only for pending candidates', () => {
    const onDismiss = vi.fn();
    render(<NewsletterCandidateCard candidate={candidate} onDismiss={onDismiss} />);

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss A useful post' }));

    expect(onDismiss).toHaveBeenCalledWith('cand_1');
  });

  it('links to the promoted job when a candidate has been promoted', () => {
    render(
      <NewsletterCandidateCard
        candidate={{ ...candidate, status: 'promoted', job_id: 'job_1' }}
      />,
    );

    expect(screen.getByRole('link', { name: 'Open job' })).toHaveAttribute(
      'href',
      '/jobs/job_1',
    );
    expect(screen.queryByRole('button', { name: 'Create job' })).not.toBeInTheDocument();
  });
});
