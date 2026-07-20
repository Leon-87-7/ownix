// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { JobSummary } from '@/components/feed/job-card';
import { AppHeader } from '@/components/shell/app-header';
import { SubmitJobProvider } from '@/components/feed/submit-job';
import { RestrictedModeProvider } from '@/lib/restricted/context';
import FeedPage from './page';

// FeedPage now consumes the global submit dialog + header the (dashboard)
// layout provides; render the same tree here so both triggers stay covered.
function FeedTree({ restricted = false }: { restricted?: boolean } = {}) {
  return (
    <RestrictedModeProvider restricted={restricted}>
      <SubmitJobProvider>
        <AppHeader />
        <FeedPage />
      </SubmitJobProvider>
    </RestrictedModeProvider>
  );
}

const navigationMock = vi.hoisted(() => {
  const replace = vi.fn();
  return {
    replace,
    // Stable identity like the real useRouter — an unstable object re-fires
    // effects that depend on the router.
    router: { push: vi.fn(), replace, back: vi.fn() },
    searchParams: new URLSearchParams(),
  };
});

// Mock next/navigation
vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => navigationMock.router,
  usePathname: () => '/feed',
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

const googleStatusMock = vi.hoisted(() => ({
  connected: null as boolean | null,
}));
vi.mock('@/components/shell/google-status', () => ({
  useGoogleStatus: () => ({
    connected: googleStatusMock.connected,
    refresh: vi.fn(),
    disconnect: vi.fn(),
  }),
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

async function openRecoveryActions() {
  fireEvent.click(await screen.findByRole('button', { name: /4 need attention/i }));
}

beforeEach(() => {
  navigationMock.replace.mockClear();
  navigationMock.searchParams = new URLSearchParams();
  googleStatusMock.connected = null;
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
  it('renders Ownix heading', () => {
    render(<FeedTree />);
    expect(screen.getByText('Ownix')).toBeTruthy();
  });

  it('renders Jobs section', () => {
    render(<FeedTree />);
    expect(screen.getByText('Jobs')).toBeTruthy();
  });

  it('shows the Connect Google nudge only while disconnected', () => {
    googleStatusMock.connected = false;
    render(<FeedTree />);
    expect(screen.getByRole('link', { name: /connect google/i })).toBeTruthy();
  });

  it('hides the Connect Google nudge when connected', () => {
    googleStatusMock.connected = true;
    render(<FeedTree />);
    expect(screen.queryByRole('link', { name: /connect google/i })).toBeNull();
  });

  it('hides the Connect Google nudge while status is unknown', () => {
    render(<FeedTree />);
    expect(screen.queryByRole('link', { name: /connect google/i })).toBeNull();
  });

  it('shows a one-time success banner on ?google=connected and strips the param', () => {
    navigationMock.searchParams = new URLSearchParams('google=connected');
    render(<FeedTree />);
    expect(screen.getByText(/google connected/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
  });

  it('shows a denied banner on ?google=denied and strips the param', () => {
    navigationMock.searchParams = new URLSearchParams('google=denied');
    render(<FeedTree />);
    expect(screen.getByText(/connection was denied/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
  });

  it('preserves other query params when stripping ?google=', () => {
    navigationMock.searchParams = new URLSearchParams('type=short&google=connected');
    render(<FeedTree />);
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed?type=short', { scroll: false });
  });

  it('strips ?google= and an unsupported ?type= in a single replace', () => {
    navigationMock.searchParams = new URLSearchParams('type=bogus&google=connected');
    render(<FeedTree />);
    expect(screen.getByText(/google connected/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledTimes(1);
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
  });

  it('still drops an unsupported ?type= without a google param', () => {
    const setCtFilter = vi.fn();
    setupMocks({ setCtFilter });
    navigationMock.searchParams = new URLSearchParams('type=bogus');
    render(<FeedTree />);
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
    expect(setCtFilter).toHaveBeenCalledWith('');
  });

  it('shows job count when loaded', () => {
    render(<FeedTree />);
    expect(screen.getByText('1 job')).toBeTruthy();
  });

  it('shows skeleton during first load (loading=true, no jobs, no error)', () => {
    setupMocks({ loading: true, jobs: [], total: 0, stats: undefined, error: null });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedTree />);
    expect(screen.getByText('loading…')).toBeTruthy();
  });

  it('shows syncing label while loading with existing jobs', () => {
    setupMocks({ loading: true, jobs: JOBS, total: 1 });
    render(<FeedTree />);
    expect(screen.getByText('syncing…')).toBeTruthy();
  });

  it('shows error banner on error', () => {
    setupMocks({ error: 'Failed to load jobs', jobs: [], total: 0, stats: undefined });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedTree />);
    expect(screen.getByText(/failed to load jobs/i)).toBeTruthy();
  });

  it('shows result count when query is present', () => {
    setupMocks();
    mockUseFuseSearch.mockReturnValue({ query: 'test', setQuery: vi.fn(), displayedJobs: JOBS } as ReturnType<typeof useFuseSearch>);
    render(<FeedTree />);
    expect(screen.getByText('1 result')).toBeTruthy();
  });

  it('shows empty state when no jobs match and no filters', () => {
    setupMocks({ jobs: [], total: 0, stats: undefined });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);
    render(<FeedTree />);
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
    render(<FeedTree />);
    expect(screen.getByText('2 jobs')).toBeTruthy();
  });

  it('initializes content type from the URL type param', () => {
    navigationMock.searchParams = new URLSearchParams('type=short');
    render(<FeedTree />);
    expect(mockUseFeedData).toHaveBeenCalledWith('short', false);
  });

  it('renders content-type tabs with counts', () => {
    render(<FeedTree />);
    expect(screen.getByRole('button', { name: /all 5/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /short 3/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /long 2/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /article 0/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /repo 0/i })).toBeTruthy();
  });


  it('renders extracted links as a first-class Feed view', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === '/api/brain/links/view' && init?.method === 'PUT') {
        return Promise.resolve(new Response(JSON.stringify({ order: 'desc', size: 25 }), { status: 200 }));
      }
      if (url === '/api/brain/links/view') {
        return Promise.resolve(new Response(JSON.stringify({ order: 'desc', size: 25 }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({
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
      }), { status: 200 }));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /links/i }));

    await waitFor(() => {
      // Link rows show the trimmed URL (path only); the full URL lives in
      // tooltip + expanded More panel.
      expect(screen.getAllByText('/canonical').length).toBeGreaterThan(0);
    });
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed?view=links', { scroll: false });
    expect(screen.queryByText('Jobs')).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith('/api/brain/links?limit=25&offset=0&order=desc');
  });

  it('omits the Links view and skips authenticated links fetches in restricted mode', async () => {
    navigationMock.searchParams = new URLSearchParams('view=links');
    const fetchMock = vi.fn(async (_input?: RequestInfo | URL) =>
      new Response(JSON.stringify({
        stale_pending: 0,
        error_jobs: 0,
        stale_in_flight: 0,
      }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<FeedTree restricted />);

    expect(screen.queryByRole('button', { name: /^links$/i })).toBeNull();
    expect(screen.getByText('Jobs')).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
    expect(fetchMock).not.toHaveBeenCalledWith('/api/brain/links/view');
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).startsWith('/api/brain/links'),
      ),
    ).toBe(false);
  });

  it('opens the docs ingest dialog with the D shortcut', async () => {
    render(<FeedTree />);
    fireEvent.keyDown(window, { key: 'd' });
    expect(await screen.findByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Ingest Docs')).toBeTruthy();
    // The dialog now hosts the full DocUploadPanel (URL fetch + PDF drop),
    // not the old "Open Doc Parser" redirect button.
    expect(screen.getByRole('button', { name: /fetch/i })).toBeTruthy();
  });

  it('updates the type query param when a content tab is clicked', () => {
    const setCtFilter = vi.fn();
    setupMocks({ setCtFilter });

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /long 2/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith('/feed?type=long', { scroll: false });
    expect(setCtFilter).toHaveBeenCalledWith('long');
  });

  it('renders the all tab as the existing job list', () => {
    render(<FeedTree />);
    // JobCard uses an overlay link inside a styled wrapper; assert on the wrapper.
    const card = screen.getByRole('link', { name: /job one/i }).parentElement;

    expect(card?.className).toContain('px-4');
    expect(card?.className).toContain('py-3');
  });

  it('renders typed tabs as preview cards', () => {
    setupMocks({ ctFilter: 'short' });

    render(<FeedTree />);
    // Preview cards use a stretched overlay link; flex/p-3 and the date text live
    // on the card container, the link's parent.
    const card = screen.getByRole('link', { name: /job one/i }).parentElement;

    expect(card?.className).toContain('flex');
    expect(card?.className).toContain('p-3');
    expect(card?.textContent).toContain(new Date(JOBS[0].created_at).toLocaleString());
  });

  it('renders the recovery panel from the active tab summary', async () => {
    setupMocks({ ctFilter: 'short' });

    render(<FeedTree />);
    await openRecoveryActions();

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

    render(<FeedTree />);
    await openRecoveryActions();
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

    render(<FeedTree />);
    await openRecoveryActions();
    fireEvent.click(await screen.findByRole('button', { name: /clear failed \(1\)/i }));

    expect(confirmMock).toHaveBeenCalledWith(
      'Clear failed jobs in this tab? This marks them cancelled; it does not delete them from DB.',
    );
  });

  it('reloads the feed when the error banner retry is clicked', () => {
    const reload = vi.fn();
    setupMocks({ error: 'Failed to load jobs', jobs: [], total: 0, stats: undefined, reload });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery: vi.fn(), displayedJobs: [] } as ReturnType<typeof useFuseSearch>);

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    expect(reload).toHaveBeenCalled();
  });

  it('keeps an accepted submission visible when the post-submit refresh fails', async () => {
    // Pass the merged feed through so optimistic rows actually render.
    mockUseFuseSearch.mockImplementation(
      (jobs: JobSummary[]) =>
        ({ query: '', setQuery: vi.fn(), displayedJobs: jobs }) as ReturnType<typeof useFuseSearch>,
    );
    // reload resolves without delivering the new job — useFeedData swallows
    // background fetch errors, so a failed refresh looks exactly like this.
    const reload = vi.fn(async () => {});
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
      reload,
    } as ReturnType<typeof useFeedData>);
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return new Response(JSON.stringify({
          id: 'accepted-1',
          job_id: 'accepted-1',
          url: 'https://example.com/new',
          content_type: 'short',
          status: 'pending',
          title: null,
        }), { status: 200 });
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }));

    render(<FeedTree />);
    // Two triggers (header + tabs-row action slot) open the same dialog; either works.
    fireEvent.click(screen.getAllByRole('button', { name: /submit url/i })[0]);
    fireEvent.change(screen.getByPlaceholderText(/paste a video/i), {
      target: { value: 'https://example.com/new' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));

    await waitFor(() => expect(reload).toHaveBeenCalled());
    // The accepted job survives the stale refresh (title is null → card shows the URL)…
    expect(screen.getByText('https://example.com/new')).toBeTruthy();
    // …and it feeds the in-flight poll so the refresh keeps retrying.
    const polled = vi.mocked(useInFlightPolling).mock.calls.at(-1)?.[0] ?? [];
    expect(polled.some((j) => j.id === 'accepted-1' && j.status === 'pending')).toBe(true);
  });

  it('drops the optimistic copy once the refreshed feed carries the job', async () => {
    mockUseFuseSearch.mockImplementation(
      (jobs: JobSummary[]) =>
        ({ query: '', setQuery: vi.fn(), displayedJobs: jobs }) as ReturnType<typeof useFuseSearch>,
    );
    const reload = vi.fn(async () => {});
    const feedState = {
      ctFilter: '',
      setCtFilter: vi.fn(),
      stFilter: '',
      setStFilter: vi.fn(),
      stats: STATS,
      jobs: JOBS,
      total: JOBS.length,
      loading: false,
      error: null,
      reload,
    } as ReturnType<typeof useFeedData>;
    mockUseFeedData.mockReturnValue(feedState);
    vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === 'POST') {
        return new Response(JSON.stringify({
          id: 'accepted-1',
          url: 'https://example.com/new',
          content_type: 'short',
          status: 'pending',
          title: null,
        }), { status: 200 });
      }
      return new Response(JSON.stringify({}), { status: 200 });
    }));

    const { rerender } = render(<FeedTree />);
    fireEvent.click(screen.getAllByRole('button', { name: /submit url/i })[0]);
    fireEvent.change(screen.getByPlaceholderText(/paste a video/i), {
      target: { value: 'https://example.com/new' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^submit$/i }));
    await waitFor(() => expect(screen.getByText('https://example.com/new')).toBeTruthy());

    // Feed catches up: the server list now carries the accepted job.
    const acceptedJob: JobSummary = {
      id: 'accepted-1',
      url: 'https://example.com/new',
      title: null,
      content_type: 'short',
      status: 'pending',
      created_at: '2024-01-02T00:00:00Z',
    };
    mockUseFeedData.mockReturnValue({
      ...feedState,
      jobs: [acceptedJob, ...JOBS],
      total: JOBS.length + 1,
    } as ReturnType<typeof useFeedData>);
    rerender(<FeedTree />);

    // Exactly one row — no optimistic duplicate alongside the server copy.
    await waitFor(() =>
      expect(screen.getAllByText('https://example.com/new')).toHaveLength(1),
    );
  });

  it('clears every filter from the empty-state Clear button', () => {
    const setStFilter = vi.fn();
    const setQuery = vi.fn();
    setupMocks({ stFilter: 'error', jobs: [], total: 0, stats: undefined, setStFilter });
    mockUseFuseSearch.mockReturnValue({ query: '', setQuery, displayedJobs: [] } as ReturnType<typeof useFuseSearch>);

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /clear filters/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', { scroll: false });
    expect(setStFilter).toHaveBeenCalledWith('');
    expect(setQuery).toHaveBeenCalledWith('');
  });
});
