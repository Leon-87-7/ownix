// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import DocDetail from './page';

let routeId = 'job-1';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: routeId }),
}));

vi.mock('@/components/doc-parser/telegram-toggle', () => ({
  TelegramToggle: () => <button>Telegram</button>,
}));

vi.mock('@/components/shell/page-shell', () => ({
  PageShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

const job = {
  id: 'job-1',
  title: '13 things: mentally/strong',
  url: 'documents/9a3aa177427fe1acc654db0235e999ead2d8c8f7e094e28e4ac6e13fdbe34ed5.pdf',
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
  routeId = 'job-1';
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

  it('renders a compact source chip and copies the full SHA-256', async () => {
    render(<DocDetail />);

    expect(await screen.findByText('PDF')).toBeTruthy();
    expect(screen.getByText('9a3aa177')).toBeTruthy();
    expect(screen.queryByText(job.url)).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: /copy source sha-256/i }));

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        '9a3aa177427fe1acc654db0235e999ead2d8c8f7e094e28e4ac6e13fdbe34ed5',
      ),
    );
    expect(await screen.findByText('Copied source SHA-256')).toBeTruthy();
  });

  it('uses generic copy text for fallback source values', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/jobs/job-1') {
        return Response.json({
          ...job,
          url: 'https://example.com/source.pdf',
        });
      }
      if (url === '/api/parsed/job-1/outputs') return Response.json(outputs);
      return new Response('not found', { status: 404 });
    }));

    render(<DocDetail />);

    expect(await screen.findByText('PDF')).toBeTruthy();
    expect(screen.getByText('source')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: /^copy source$/i }));

    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('source'),
    );
    expect(await screen.findByText('Copied source')).toBeTruthy();
    expect(screen.queryByText('Copied source SHA-256')).toBeNull();
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
    expect(anchor.download).toBe('ownix-13 things_ mentally_strong-raw_txt.txt');
  });

  it('shows the backend load failure detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/jobs/job-1') {
        return Response.json({ detail: 'Not authenticated' }, { status: 401 });
      }
      if (url === '/api/parsed/job-1/outputs') return Response.json(outputs);
      return new Response('not found', { status: 404 });
    }));

    render(<DocDetail />);

    expect(
      await screen.findByText('Failed to load document: Not authenticated'),
    ).toBeTruthy();
  });

  it('shows string backend detail for action failures', async () => {
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/jobs/job-1') return Response.json(job);
      if (url === '/api/parsed/job-1/outputs') return Response.json(outputs);
      if (url === '/api/parsed/job-1/clean') {
        return Response.json({ detail: 'Not authenticated' }, { status: 401 });
      }
      return new Response('not found', { status: 404 });
    }));

    render(<DocDetail />);

    fireEvent.click(await screen.findByRole('button', { name: 'Clean' }));

    expect(await screen.findByText('Not authenticated')).toBeTruthy();
  });

  it('does not apply a stale response after id changes', async () => {
    let resolveFirst: (value: unknown) => void;
    const firstJob = new Promise((resolve) => {
      resolveFirst = resolve;
    });

    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url === '/api/jobs/first') {
        return firstJob.then(() => Response.json({ ...job, id: 'first', title: 'First' }));
      }
      if (url === '/api/jobs/second') {
        return Promise.resolve(Response.json({ ...job, id: 'second', title: 'Second' }));
      }
      if (url === '/api/parsed/first/outputs' || url === '/api/parsed/second/outputs') {
        return Promise.resolve(Response.json([]));
      }
      return Promise.resolve(new Response('not found', { status: 404 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    routeId = 'first';
    const { rerender } = render(<DocDetail />);
    routeId = 'second';
    rerender(<DocDetail />);

    expect(await screen.findByText('Second')).toBeTruthy();

    resolveFirst!(undefined);
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(screen.getByText('Second')).toBeTruthy();
    expect(screen.queryByText('First')).toBeNull();
  });

});
