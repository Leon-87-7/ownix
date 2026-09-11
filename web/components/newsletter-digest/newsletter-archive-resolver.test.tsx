// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi } from 'vitest';
import { NewsletterArchiveResolver } from './newsletter-archive-resolver';
import type { NewsletterArchiveResolution } from '@/lib/newsletter-digest';

const RESOLUTION: NewsletterArchiveResolution = {
  archive_url: 'https://alphasignal.ai',
  feed_url: 'https://alphasignal.ai/feed.xml',
  issue_path_prefix: '/news/',
  fetched_title: 'AlphaSignal',
  recent_issues: [
    { slug: 'gpt-6-launch', title: 'GPT-6 launches', url: 'https://alphasignal.ai/news/gpt-6-launch' },
    { slug: 'rag-tips', title: 'RAG tips', url: 'https://alphasignal.ai/news/rag-tips' },
  ],
};

describe('NewsletterArchiveResolver', () => {
  it('resolves the trimmed query and shows a confirmation card with recent issue titles', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    render(<NewsletterArchiveResolver onResolve={onResolve} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: '  https://alphasignal.ai  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));

    await waitFor(() => expect(onResolve).toHaveBeenCalledWith('https://alphasignal.ai'));
    expect(await screen.findByText('AlphaSignal')).toBeInTheDocument();
    expect(screen.getByText('GPT-6 launches')).toBeInTheDocument();
    expect(screen.getByText('RAG tips')).toBeInTheDocument();
  });

  it('does not call onResolve for a blank query', () => {
    const onResolve = vi.fn();
    render(<NewsletterArchiveResolver onResolve={onResolve} />);

    fireEvent.click(screen.getByRole('button', { name: 'Find' }));

    expect(onResolve).not.toHaveBeenCalled();
  });

  it('renders a resolution error as an alert and keeps the field editable', async () => {
    const onResolve = vi.fn().mockRejectedValue(new Error('Could not find a public archive'));
    render(<NewsletterArchiveResolver onResolve={onResolve} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://nobody-publishes-here.example' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Could not find a public archive');
    // The form is shown again (not stuck on a phantom confirmation card).
    expect(screen.getByRole('button', { name: 'Find' })).toBeInTheDocument();
  });

  it('pre-fills the watch name from the fetched title and calls onConfirm with it', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    const onConfirm = vi.fn();
    render(<NewsletterArchiveResolver onResolve={onResolve} onConfirm={onConfirm} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByText('AlphaSignal');

    const nameInput = screen.getByLabelText('Watch name') as HTMLInputElement;
    expect(nameInput.value).toBe('AlphaSignal');

    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(RESOLUTION, 'AlphaSignal');
  });

  it('lets the watch name be edited before confirming', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    const onConfirm = vi.fn();
    render(<NewsletterArchiveResolver onResolve={onResolve} onConfirm={onConfirm} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByText('AlphaSignal');

    fireEvent.change(screen.getByLabelText('Watch name'), { target: { value: 'My AI digest' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm' }));

    expect(onConfirm).toHaveBeenCalledWith(RESOLUTION, 'My AI digest');
  });

  it('"Try another" clears the confirmation card and returns to the input', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    render(<NewsletterArchiveResolver onResolve={onResolve} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByText('AlphaSignal');

    fireEvent.click(screen.getByRole('button', { name: 'Try another' }));

    expect(screen.getByLabelText(/Archive URL, issue link, or sender email/)).toBeInTheDocument();
    expect(screen.queryByText('AlphaSignal')).not.toBeInTheDocument();
  });

  it('disables Confirm while the create request is in flight (council review)', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    const onConfirm = vi.fn();
    const { rerender } = render(
      <NewsletterArchiveResolver onResolve={onResolve} onConfirm={onConfirm} submitting={false} />,
    );

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByText('AlphaSignal');

    // The parent flips `submitting` the moment its POST starts.
    rerender(
      <NewsletterArchiveResolver onResolve={onResolve} onConfirm={onConfirm} submitting={true} />,
    );

    const confirm = screen.getByRole('button', { name: 'Adding...' });
    expect(confirm).toBeDisabled();
    fireEvent.click(confirm);
    expect(onConfirm).not.toHaveBeenCalled();
    // "Try another" is locked too, so the panel can't be torn down mid-request.
    expect(screen.getByRole('button', { name: 'Try another' })).toBeDisabled();
  });

  it('confirms on Enter from the watch-name field', async () => {
    const onResolve = vi.fn().mockResolvedValue(RESOLUTION);
    const onConfirm = vi.fn();
    render(<NewsletterArchiveResolver onResolve={onResolve} onConfirm={onConfirm} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));
    await screen.findByText('AlphaSignal');

    // Enter submits on the query field one step earlier; it must here too.
    fireEvent.submit(screen.getByLabelText('Watch name').closest('form')!);

    expect(onConfirm).toHaveBeenCalledWith(RESOLUTION, 'AlphaSignal');
  });

  it('shows an empty state when the archive resolved with no issues', async () => {
    const onResolve = vi.fn().mockResolvedValue({ ...RESOLUTION, recent_issues: [] });
    render(<NewsletterArchiveResolver onResolve={onResolve} />);

    fireEvent.change(screen.getByLabelText(/Archive URL, issue link, or sender email/), {
      target: { value: 'https://alphasignal.ai' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Find' }));

    expect(await screen.findByText(/no issues listed yet/i)).toBeInTheDocument();
  });
});
