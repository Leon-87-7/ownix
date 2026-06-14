// @vitest-environment jsdom
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { JobSummary } from '@/components/job-card';
import FeedPage from './page';

const navigationMock = vi.hoisted(() => ({
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn(), replace: navigationMock.replace, back: vi.fn() }),
  usePathname: () => '/',
  useSearchParams: () => navigationMock.searchParams,
}));

const STATS = { total: 5, by_status: { done: 3, error: 1 }, by_content_type: { short: 3, long: 2 } };
const JOBS: JobSummary[] = [
  {
    id: 'j1',
    url: 'https://example.com/1',
    title: 'Job One',
    content_type: 'short',
    status: 'done',
    created_at: '2024-01-01T00:00:00Z',
    thumbnail_url: 'https://example.com/thumb.jpg',
    thumbnail_kind: 'landscape',
  },
];

// Mock all hooks used by FeedPage
vi.mock('@/lib/hooks/useFeedData', () => ({
  useFeedData: vi.fn(),
}));
vi.mock('@/lib/hooks/useFuseSearch', () => ({
  useFuseSearch: vi.fn(),
}));
vi.mock('@/lib/hooks/useInFlightPolling', () => ({
  useInFlightPolling: vi.fn(),
}));

import { useFeedData } from '@/lib/hooks/useFeedData';
import { useFuseSearch } from '@/lib/hooks/useFuseSearch';
import { useInFlightPolling } from '@/lib/hooks/useInFlightPolling';

const mockUseFeedData = vi.mocked(useFeedData);
const mockUseFuseSearch = vi.mocked(useFuseSearch);

function setupMocks(overrides: Partial<ReturnType<typeof useFeedData>> = {}) {
  mockUseFeedData.mockReturnValue({
    ctFilter: '',
    setCtFilter: vi.fn(),
    stFilter: '',
    setStFilter: vi.fn(),
    stats: STATS,
    jobs: JOBS,
    total: JOBS.length,
    loading: false,
    error: null,
    reload: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useFeedData>);

  mockUseFuseSearch.mockReturnValue({
    query: '',
    setQuery: vi.fn(),
    displayedJobs: JOBS,
  } as ReturnType<typeof useFuseSearch>);

  vi.mocked(useInFlightPolling).mockReturnValue(undefined);
}

beforeEach(() => {
  navigationMock.replace.mockClear();
  navigationMock.searchParams = new URLSearchParams();
  mockUseFeedData.mockReset();
  mockUseFuseSearch.mockReset();
  setupMocks();
});

describe('FeedPage', () => {
  it('renders Feed heading', () => {
    render(<FeedPage />);
    expect(screen.getByText('Feed')).toBeTruthy();
  });

  it('renders Jobs section', () => {
    render(<FeedPage />);
    expect(screen.getByText('Jobs')).toBeTruthy();
  });

  it('shows job count when loaded', () => {
    render(<FeedPage />);
    expect(screen.getByText('1 job')).toBeTruthy();
  });

  it('shows skeleton during first load (loading=true, no jobs, no error)', () => {
    setupMocks({ loading: true, jobs: [], total: 0, stats: undefined, error: null });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedPage />);
    expect(screen.getByText('loading…')).toBeTruthy();
  });

  it('shows syncing label while loading with existing jobs', () => {
    setupMocks({ loading: true, jobs: JOBS, total: 1 });
    render(<FeedPage />);
    expect(screen.getByText('syncing…')).toBeTruthy();
  });

  it('shows error banner on error', () => {
    setupMocks({ error: 'Failed to load jobs', jobs: [], total: 0, stats: undefined });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedPage />);
    expect(screen.getByText(/failed to load jobs/i)).toBeTruthy();
  });

  it('shows result count when query is present', () => {
    setupMocks();
    mockUseFuseSearch.mockReturnValue({ query: 'test', setQuery: vi.fn(), displayedJobs: JOBS } as ReturnType<typeof useFuseSearch>);
    render(<FeedPage />);
    expect(screen.getByText('1 result')).toBeTruthy();
  });

  it('shows empty state when no jobs match and no filters', () => {
    setupMocks({ jobs: [], total: 0, stats: undefined });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedPage />);
    // empty state renders something when displayedJobs.length === 0 and no first load
    expect(screen.getByText('0 jobs')).toBeTruthy();
  });

  it('shows plural job count', () => {
    const multiJobs = [
      { id: 'j1', url: 'https://a.com', title: 'A', content_type: 'short', status: 'done', created_at: '' },
      { id: 'j2', url: 'https://b.com', title: 'B', content_type: 'long', status: 'done', created_at: '' },
    ];
    setupMocks({ jobs: multiJobs, total: 2 });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: multiJobs } as ReturnType<typeof useFuseSearch>);
    render(<FeedPage />);
    expect(screen.getByText('2 jobs')).toBeTruthy();
  });

  it('initializes content type from the URL type param', () => {
    navigationMock.searchParams = new URLSearchParams('type=short');
    render(<FeedPage />);
    expect(mockUseFeedData).toHaveBeenCalledWith('short');
  });

  it('renders content-type tabs with counts', () => {
    render(<FeedPage />);
    expect(screen.getByRole('tab', { name: /all 5/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /short 3/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /long 2/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /article 0/i })).toBeTruthy();
    expect(screen.getByRole('tab', { name: /repo 0/i })).toBeTruthy();
  });

  it('updates the type query param when a content tab is clicked', () => {
    const setCtFilter = vi.fn();
    setupMocks({ setCtFilter });

    render(<FeedPage />);
    fireEvent.click(screen.getByRole('tab', { name: /long 2/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith('/?type=long', { scroll: false });
    expect(setCtFilter).toHaveBeenCalledWith('long');
  });

  it('renders the all tab as the existing job list', () => {
    render(<FeedPage />);
    const card = screen.getByRole('link', { name: /job one/i });

    expect(card.className).toContain('px-4');
    expect(card.className).toContain('py-3');
  });

  it('renders typed tabs as preview cards', () => {
    setupMocks({ ctFilter: 'short' });

    render(<FeedPage />);
    const card = screen.getByRole('link', { name: /job one/i });

    expect(card.className).toContain('flex');
    expect(card.className).toContain('p-3');
    expect(card.textContent).toContain(new Date(JOBS[0].created_at).toLocaleString());
  });
});
