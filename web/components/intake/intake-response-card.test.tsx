// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { IntakeResponseCard } from './intake-response-card';
import type { IntakeThreadItem } from '@/lib/hooks/useIntakeThread';
import type { IntakeResponseShape } from '@/lib/hooks/useIntake';
import type { JobSummary } from '@/components/feed/job-card';

function response(overrides: Partial<IntakeResponseShape> = {}): IntakeResponseShape {
  return {
    schema_version: 1,
    kind: 'job_created',
    text: 'Received — job_abcd (short).',
    job_id: 'j1',
    job_url: '/jobs/j1',
    actions: [],
    artifacts: [],
    retryable: false,
    ...overrides,
  };
}

function job(overrides: Partial<JobSummary> = {}): JobSummary {
  return {
    id: 'j1',
    title: 'A short video',
    url: 'https://youtube.com/shorts/abc',
    content_type: 'short',
    status: 'processing',
    created_at: '2026-08-06T10:00:00Z',
    ...overrides,
  };
}

function item(overrides: Partial<IntakeThreadItem> = {}): IntakeThreadItem {
  return { id: 'i1', response: response(), ...overrides };
}

describe('IntakeResponseCard', () => {
  it('echoes what the user submitted above the card', () => {
    render(<IntakeResponseCard item={item({ echo: 'https://youtube.com/shorts/abc' })} />);
    expect(screen.getByText('https://youtube.com/shorts/abc')).toBeInTheDocument();
  });

  it('shows the live status line and badge while the job is in flight', () => {
    render(<IntakeResponseCard item={item({ job: job({ status: 'processing' }) })} />);
    expect(screen.getByText(/processing…/i)).toBeInTheDocument();
    // The badge is visible throughout, not only at the end.
    expect(screen.getByText('processing')).toBeInTheDocument();
  });

  it('changes the label as the job advances', () => {
    const { rerender } = render(<IntakeResponseCard item={item({ job: job({ status: 'pending' }) })} />);
    expect(screen.getByText(/queued…/i)).toBeInTheDocument();
    rerender(<IntakeResponseCard item={item({ job: job({ status: 'enriching' }) })} />);
    expect(screen.getByText(/enriching…/i)).toBeInTheDocument();
  });

  it('renders no stepper or percentage', () => {
    const { container } = render(<IntakeResponseCard item={item({ job: job({ status: 'processing' }) })} />);
    expect(container.querySelector('progress')).toBeNull();
    expect(container.textContent).not.toMatch(/%/);
  });

  it('resolves into the finished preview once done', () => {
    render(<IntakeResponseCard item={item({ job: job({ status: 'done' }) })} />);
    expect(screen.getByText('A short video')).toBeInTheDocument();
    // The preview is itself a link to the job, so the text link steps aside.
    expect(screen.queryByRole('link', { name: /view job/i })).not.toBeInTheDocument();
  });

  it('keeps the text link to the job until the preview replaces it', () => {
    render(<IntakeResponseCard item={item({ job: job({ status: 'processing' }) })} />);
    expect(screen.getByRole('link', { name: /view job/i })).toHaveAttribute('href', '/jobs/j1');
  });

  it('says so when the job row is gone', () => {
    render(<IntakeResponseCard item={item({ job: null })} />);
    expect(screen.getByText(/job no longer exists/i)).toBeInTheDocument();
  });

  it('offers a retry on a retryable response and disables it while in flight', async () => {
    const user = userEvent.setup();
    let resolveRetry: () => void = () => {};
    const retry = vi.fn(() => new Promise<void>((r) => { resolveRetry = r; }));

    render(
      <IntakeResponseCard
        item={item({
          response: response({ kind: 'error', text: 'Could not process this PDF right now.', job_id: null, retryable: true }),
          retry,
        })}
      />,
    );

    const button = screen.getByRole('button', { name: /try again/i });
    await user.click(button);
    expect(retry).toHaveBeenCalledTimes(1);
    // Double-firing must not produce a second submit.
    expect(screen.getByRole('button', { name: /retrying…/i })).toBeDisabled();
    resolveRetry();
  });

  it('offers no retry when the item cannot be replayed', () => {
    render(
      <IntakeResponseCard
        item={item({ response: response({ kind: 'error', retryable: true, job_id: null }) })}
      />,
    );
    expect(screen.queryByRole('button', { name: /try again/i })).not.toBeInTheDocument();
  });
});

describe('IntakeResponseCard — unknown tag offer (#489)', () => {
  const offer = {
    action_id: 'create_tag:j1:goto',
    kind: 'create_tag',
    label: 'Create #GoTo',
    job_id: 'j1',
    payload: { tag_name: 'GoTo' },
  };

  it('renders a closed offer as a button', () => {
    render(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer] }) })}
        onSaveOffer={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /create #goto/i })).toBeInTheDocument();
  });

  it('expands into the inline tag form when opened', () => {
    render(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer] }) })}
        openOfferId={offer.action_id}
        onSaveOffer={vi.fn()}
      />,
    );
    expect(screen.getByPlaceholderText(/tag name/i)).toHaveValue('GoTo');
    expect(screen.getByRole('button', { name: /create tag/i })).toBeInTheDocument();
  });

  it('saves with the edited values and the original job id', async () => {
    const user = userEvent.setup();
    const onSaveOffer = vi.fn().mockResolvedValue(undefined);
    render(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer] }) })}
        openOfferId={offer.action_id}
        onSaveOffer={onSaveOffer}
      />,
    );

    const meaning = screen.getByPlaceholderText(/what this tag means/i);
    await user.type(meaning, 'read soon');
    await user.click(screen.getByRole('button', { name: /create tag/i }));

    expect(onSaveOffer).toHaveBeenCalledTimes(1);
    const sent = onSaveOffer.mock.calls[0][0];
    expect(sent.job_id).toBe('j1');
    expect(sent.payload.tag_name).toBe('GoTo');
    expect(sent.payload.meaning).toBe('read soon');
  });

  it('tells you how many offers remain', () => {
    const second = { ...offer, action_id: 'create_tag:j1:foo', payload: { tag_name: 'Foo' } };
    render(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer, second] }) })}
        openOfferId={offer.action_id}
        onSaveOffer={vi.fn()}
      />,
    );
    expect(screen.getByText(/1 more after this/i)).toBeInTheDocument();
  });

  it('gives each new tag a distinct default colour', () => {
    const second = { ...offer, action_id: 'create_tag:j1:foo', payload: { tag_name: 'Foo' } };
    const { rerender } = render(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer, second] }) })}
        openOfferId={offer.action_id}
        onSaveOffer={vi.fn()}
      />,
    );
    const first = screen.getByRole('button', { name: /^color/i, pressed: true }).getAttribute('aria-label');
    rerender(
      <IntakeResponseCard
        item={item({ response: response({ actions: [offer, second] }) })}
        openOfferId={second.action_id}
        onSaveOffer={vi.fn()}
      />,
    );
    const nextColor = screen.getByRole('button', { name: /^color/i, pressed: true }).getAttribute('aria-label');
    expect(nextColor).not.toBe(first);
  });
});
