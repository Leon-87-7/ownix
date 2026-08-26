// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import DocParserPage from './page';

class MockEventSource {
  addEventListener = vi.fn();
  close = vi.fn();
  constructor(public url: string) {}
}

vi.stubGlobal('EventSource', MockEventSource);
vi.mock('@/components/doc-parser/telegram-toggle', () => ({
  TelegramToggle: () => <button>Telegram</button>,
}));

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('EventSource', MockEventSource);
});

afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function useJobs(items: unknown[]) {
  server.use(http.get('/api/jobs', () => HttpResponse.json({ items })));
}

describe('DocParserPage', () => {
  it('shows an empty state when there are no documents', async () => {
    useJobs([]);

    render(<DocParserPage />);

    await waitFor(() => expect(screen.getByText(/no jobs yet/i)).toBeInTheDocument());
  });

  it('filters the job list by format tab (derived from the source extension)', async () => {
    const items = [
      { id: '1', url: 'documents/aaa.pdf', status: 'done', created_at: 'x' },
      { id: '2', url: 'documents/bbb.docx', status: 'done', created_at: 'x' },
      { id: '3', url: 'documents/ccc.xlsx', status: 'done', created_at: 'x' },
    ];
    useJobs(items);

    render(<DocParserPage />);

    // All three visible under the default "All" tab.
    await waitFor(() => expect(screen.getByText('documents/bbb.docx')).toBeInTheDocument());
    expect(screen.getByText('documents/aaa.pdf')).toBeInTheDocument();
    expect(screen.getByText('documents/ccc.xlsx')).toBeInTheDocument();

    // Clicking "Word" leaves only the .docx job.
    fireEvent.click(screen.getByRole('button', { name: /word/i }));
    await waitFor(() =>
      expect(screen.queryByText('documents/aaa.pdf')).not.toBeInTheDocument(),
    );
    expect(screen.getByText('documents/bbb.docx')).toBeInTheDocument();
    expect(screen.queryByText('documents/ccc.xlsx')).not.toBeInTheDocument();
  });

  it('shows a loading skeleton before the first response resolves', async () => {
    let resolveJobs: ((v: Response) => void) | undefined;
    server.use(
      http.get('/api/jobs', () => new Promise<Response>((resolve) => { resolveJobs = resolve; })),
    );

    const { container } = render(<DocParserPage />);

    expect(container.querySelectorAll('.skeleton-shimmer').length).toBeGreaterThan(0);
    await waitFor(() => expect(resolveJobs).toBeTypeOf('function'));
    await act(async () => {
      resolveJobs?.(HttpResponse.json({ items: [] }));
    });
  });
});
