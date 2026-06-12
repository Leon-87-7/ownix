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
    const button = screen.getByRole('button', { name: /search/i });
    fireEvent.click(button);
    expect(screen.getByText(/please enter a search query/i)).toBeTruthy();
  });

  it('calls runSearch when query is non-empty and Search is clicked', () => {
    const runSearch = vi.fn();
    setupMocks({ query: 'machine learning', runSearch });
    render(<BrainPage />);
    const button = screen.getByRole('button', { name: /search/i });
    fireEvent.click(button);
    expect(runSearch).toHaveBeenCalled();
  });

  it('calls runSearch on Enter key press', () => {
    const runSearch = vi.fn();
    setupMocks({ query: 'startup advice', runSearch });
    render(<BrainPage />);
    const input = screen.getByRole('textbox', { name: /semantic search query/i });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(runSearch).toHaveBeenCalled();
  });
});
