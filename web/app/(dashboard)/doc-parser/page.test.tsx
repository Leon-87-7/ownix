// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
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

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('EventSource', MockEventSource);
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('DocParserPage', () => {
  it('shows an empty state when there are no documents', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items: [] })));

    render(<DocParserPage />);

    await waitFor(() => expect(screen.getByText(/no jobs yet/i)).toBeInTheDocument());
  });

  it('filters the job list by format tab (derived from the source extension)', async () => {
    const items = [
      { id: '1', url: 'documents/aaa.pdf', status: 'done', created_at: 'x' },
      { id: '2', url: 'documents/bbb.docx', status: 'done', created_at: 'x' },
      { id: '3', url: 'documents/ccc.xlsx', status: 'done', created_at: 'x' },
    ];
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ items })));

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
    let resolveFetch: (v: Response) => void;
    vi.spyOn(global, 'fetch').mockReturnValue(new Promise((resolve) => { resolveFetch = resolve; }) as unknown as Promise<Response>);

    const { container } = render(<DocParserPage />);

    expect(container.querySelectorAll('.animate-pulse').length).toBeGreaterThan(0);
    await act(async () => {
      resolveFetch!(new Response(JSON.stringify({ items: [] })));
    });
  });
});
