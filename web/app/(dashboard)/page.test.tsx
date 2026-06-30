// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
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
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'POST') {
      return new Response(JSON.stringify({ enqueued: 1 }), { status: 200 });
    }
    return new Response(JSON.stringify({
      stale_pending: 2,
      error_jobs: 1,
      stale_in_flight: 1,
    }), { status: 200 });
  }));
  setupMocks();
});

describe('FeedPage', () => {
  it('renders VIG heading', () => {
    render(<FeedPage />);
    expect(screen.getByText('VIG')).toBeTruthy();
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
    expect(screen.getByRole('button', { name: /all 5/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /short 3/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /long 2/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /article 0/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /repo 0/i })).toBeTruthy();
  });

  it('updates the type query param when a content tab is clicked', () => {
    const setCtFilter = vi.fn();
    setupMocks({ setCtFilter });

    render(<FeedPage />);
    fireEvent.click(screen.getByRole('button', { name: /long 2/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith('/?type=long', { scroll: false });
    expect(setCtFilter).toHaveBeenCalledWith('long');
  });

  it('renders the all tab as the existing job list', () => {
    render(<FeedPage />);
    // JobCard uses an overlay link inside a styled wrapper; assert on the wrapper.
    const card = screen.getByRole('link', { name: /job one/i }).parentElement;

    expect(card?.className).toContain('px-4');
    expect(card?.className).toContain('py-3');
  });

  it('renders typed tabs as preview cards', () => {
    setupMocks({ ctFilter: 'short' });

    render(<FeedPage />);
    // Preview cards use a stretched overlay link; flex/p-3 and the date text live
    // on the card container, the link's parent.
    const card = screen.getByRole('link', { name: /job one/i }).parentElement;

    expect(card?.className).toContain('flex');
    expect(card?.className).toContain('p-3');
    expect(card?.textContent).toContain(new Date(JOBS[0].created_at).toLocaleString());
  });

  it('renders the recovery panel from the active tab summary', async () => {
    setupMocks({ ctFilter: 'short' });

    render(<FeedPage />);

    expect(await screen.findByRole('button', { name: /retry pending \(2\)/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /retry failed \(2\)/i })).toBeTruthy();
    expect(screen.getByText('1 stale in-flight')).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith(
      '/api/jobs/recovery/summary?content_type=short',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('refreshes recovery summary and feed data after retrying pending jobs', async () => {
    const reload = vi.fn();
    setupMocks({ ctFilter: 'short', reload });

    render(<FeedPage />);
    fireEvent.click(await screen.findByRole('button', { name: /retry pending \(2\)/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/jobs/recovery/retry-pending',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ content_type: 'short' }),
        }),
      );
      expect(reload).toHaveBeenCalled();
    });
  });

  it('requires the exact confirmation copy before clearing failed jobs', async () => {
    const confirmMock = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmMock);

    render(<FeedPage />);
    fireEvent.click(await screen.findByRole('button', { name: /clear failed \(1\)/i }));

    expect(confirmMock).toHaveBeenCalledWith(
      'Clear failed jobs in this tab? This marks them cancelled; it does not delete them from DB.',
    );
  });

  it('reloads the feed when the error banner retry is clicked', () => {
    const reload = vi.fn();
    setupMocks({ error: 'Failed to load jobs', jobs: [], total: 0, stats: undefined, reload });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);

    render(<FeedPage />);
    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    expect(reload).toHaveBeenCalled();
  });

  it('clears every filter from the empty-state Clear button', () => {
    const setStFilter = vi.fn();
    const setQuery = vi.fn();
    setupMocks({ stFilter: 'error', jobs: [], total: 0, stats: undefined, setStFilter });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery, displayedJobs: [] } as ReturnType<typeof useFuseSearch>);

    render(<FeedPage />);
    fireEvent.click(screen.getByRole('button', { name: /clear filters/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith('/', { scroll: false });
    expect(setStFilter).toHaveBeenCalledWith('');
    expect(setQuery).toHaveBeenCalledWith('');
  });
});
