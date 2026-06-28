// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocDetail from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'job-1' }),
}));

vi.mock('@/components/doc-parser/telegram-toggle', () => ({
  TelegramToggle: () => <button>Telegram</button>,
}));

vi.mock('@/components/page-shell', () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

const job = {
  id: 'job-1',
  title: '13 things: mentally/strong',
  url: 'https://example.com/doc',
  status: 'done',
  telegram_delivery: 'off',
};

const outputs = [
  {
    id: 'raw',
    kind: 'raw_txt',
    title: 'Raw parse',
    preview: 'truncated raw preview',
    content_url: '/api/parsed/job-1/outputs/raw',
    created_at: '2026-06-28T00:00:00Z',
  },
  {
    id: 'summary',
    kind: 'structured_summary',
    title: 'Structured summary',
    preview: 'truncated summary preview',
    content_url: '/api/parsed/job-1/outputs/summary',
    created_at: '2026-06-28T00:00:00Z',
  },
];

beforeEach(() => {
  document.body.innerHTML = '';
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url === '/api/jobs/job-1') return Response.json(job);
    if (url === '/api/parsed/job-1/outputs') return Response.json(outputs);
    if (url === '/api/parsed/job-1/outputs/raw') return new Response('full raw content');
    if (url === '/api/parsed/job-1/outputs/summary') return new Response('full summary content');
    return new Response('not found', { status: 404 });
  }));
  Object.assign(navigator, {
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
  vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:download');
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    this.dataset.clicked = 'true';
  });
});

describe('DocDetail', () => {
  it('renders Telegram as the first action after the title-only header', async () => {
    render(<DocDetail />);

    expect(await screen.findByRole('heading', { name: job.title })).toBeTruthy();
    const actions = screen.getAllByRole('button').slice(0, 3).map((button) => button.textContent);
    expect(actions).toEqual(['Telegram', 'Clean', 'Freestyle']);
  });

  it('copies the full output instead of the truncated preview and shows copied feedback', async () => {
    render(<DocDetail />);

    fireEvent.click((await screen.findAllByRole('button', { name: /copy full output/i }))[0]);

    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith('full raw content'));
    expect(await screen.findByText('Copied')).toBeTruthy();

    await waitFor(() => expect(screen.queryByText('Copied')).toBeNull(), { timeout: 2000 });
  });

  it('shows copy failed feedback when the output fetch rejects', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/jobs/job-1') return Response.json(job);
      if (url === '/api/parsed/job-1/outputs') return Response.json(outputs);
      return new Response('error', { status: 500 });
    }));

    render(<DocDetail />);

    fireEvent.click((await screen.findAllByRole('button', { name: /copy full output/i }))[0]);

    expect(await screen.findByText('Copy failed')).toBeTruthy();
  });

  it('downloads the full output with the expected sanitized filename', async () => {
    render(<DocDetail />);

    fireEvent.click((await screen.findAllByRole('button', { name: /download full output/i }))[0]);

    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled());
    expect(fetch).toHaveBeenCalledWith('/api/parsed/job-1/outputs/raw', expect.anything());
    const clickMock = vi.mocked(HTMLAnchorElement.prototype.click);
    const anchor = clickMock.mock.contexts[0] as HTMLAnchorElement;
    expect(anchor.download).toBe('vig-13 things_ mentally_strong-raw_txt.txt');
  });
});
