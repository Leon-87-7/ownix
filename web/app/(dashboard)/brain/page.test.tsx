// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import BrainPage from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/brain',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useSemanticSearch', () => ({
  useSemanticSearch: vi.fn(),
}));

vi.mock('@/components/brain-graph', () => ({
  BrainGraph: () => <div data-testid="brain-graph" />,
}));

import { useSemanticSearch } from '@/lib/hooks/useSemanticSearch';
const mockUseSemanticSearch = vi.mocked(useSemanticSearch);

const RESULTS = [
  { title: 'AI Video', url: 'https://example.com/ai', topic: 'AI', score: 0.95 },
  { title: 'ML Video', url: 'https://example.com/ml', topic: 'ML', score: 0.88 },
];

function setupMocks(overrides: Partial<ReturnType<typeof useSemanticSearch>> = {}) {
  mockUseSemanticSearch.mockReturnValue({
    query: '',
    setQuery: vi.fn(),
    results: [],
    searchState: 'idle',
    errorMessage: '',
    runSearch: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useSemanticSearch>);
}

beforeEach(() => { setupMocks(); });

describe('BrainPage', () => {
  it('renders Brain heading', () => {
    render(<BrainPage />);
    expect(screen.getByText('Brain')).toBeTruthy();
  });

  it('shows idle banner by default', () => {
    render(<BrainPage />);
    expect(screen.getByText(/search your second brain/i)).toBeTruthy();
  });

  it('shows loading spinner when searchState is loading', () => {
    setupMocks({ searchState: 'loading' });
    render(<BrainPage />);
    expect(screen.getByText('Searching…')).toBeTruthy();
  });

  it('shows error banner when searchState is error', () => {
    setupMocks({ searchState: 'error', errorMessage: 'Something went wrong' });
    render(<BrainPage />);
    expect(screen.getByText('Something went wrong')).toBeTruthy();
  });

  it('shows empty banner when searchState is empty', () => {
    setupMocks({ searchState: 'empty' });
    render(<BrainPage />);
    expect(screen.getByText(/no results found/i)).toBeTruthy();
  });

  it('shows results when searchState is results', () => {
    setupMocks({ searchState: 'results', results: RESULTS });
    render(<BrainPage />);
    expect(screen.getByText('AI Video')).toBeTruthy();
    expect(screen.getByText('ML Video')).toBeTruthy();
    expect(screen.getByText('2 results')).toBeTruthy();
  });

  it('shows 1 result singular', () => {
    setupMocks({ searchState: 'results', results: [RESULTS[0]] });
    render(<BrainPage />);
    expect(screen.getByText('1 result')).toBeTruthy();
  });

  it('shows blank warning when Search is clicked with empty query', () => {
    render(<BrainPage />);
    const button = screen.getByRole('button', { name: /run search/i });
    fireEvent.click(button);
    expect(screen.getByText(/please enter a search query/i)).toBeTruthy();
  });

  it('calls runSearch when query is non-empty and Search is clicked', () => {
    const runSearch = vi.fn();
    setupMocks({ query: 'machine learning', runSearch });
    render(<BrainPage />);
    const button = screen.getByRole('button', { name: /run search/i });
    fireEvent.click(button);
    expect(runSearch).toHaveBeenCalled();
  });

  it('calls runSearch on Enter key press', () => {
    const runSearch = vi.fn();
    setupMocks({ query: 'startup advice', runSearch });
    render(<BrainPage />);
    const input = screen.getByRole('searchbox', { name: /semantic search query/i });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(runSearch).toHaveBeenCalled();
  });

  it('renders links tab rows from the paginated endpoint', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/brain/links/view' && init?.method === 'PUT') {
        return Promise.resolve({ ok: true, json: async () => ({ sort: 'last_seen', order: 'desc', size: 25 }) });
      }
      if (url === '/api/brain/links/view') {
        return Promise.resolve({ ok: true, json: async () => ({ sort: 'last_seen', order: 'desc', size: 25 }) });
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({
          items: [
            {
              url: 'https://example.com/canonical',
              title: 'Canonical',
              topic: 'Docs',
              seen_count: 4,
              first_seen: '2026-06-28T12:00:00+00:00',
            },
          ],
          limit: 25,
          offset: 0,
          total: 1,
        }),
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<BrainPage />);
    fireEvent.click(screen.getByRole('button', { name: /links/i }));

    await waitFor(() => {
      expect(screen.getByText('https://example.com/canonical')).toBeTruthy();
    });
    const link = screen.getByRole('link', { name: /https:\/\/example.com\/canonical/i });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(screen.getByText('4')).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledWith('/api/brain/links?limit=25&offset=0&sort=last_seen&order=desc');
    // The skipFirstPut guard must not write the freshly-loaded view back.
    expect(fetchMock).not.toHaveBeenCalledWith(
      '/api/brain/links/view',
      expect.objectContaining({ method: 'PUT' }),
    );
  });
});
