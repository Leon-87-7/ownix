// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MockInstance } from 'vitest';
import type { JobSummary } from '@/components/feed/job-card';
import { AppHeader } from '@/components/shell/app-header';
import { SubmitJobProvider } from '@/components/feed/submit-job';
import { RestrictedModeProvider } from '@/lib/restricted/context';
import FeedPage from './page';

const RECOVERY_SUMMARY = { stale_pending: 2, error_jobs: 1, stale_in_flight: 1 };

// RecoveryPanel is always mounted (only its `active` prop changes), so its
// GET fires on every render regardless of which view/tab a test exercises.
const server = setupServer(
  http.get('/api/jobs/recovery/summary', () => HttpResponse.json(RECOVERY_SUMMARY)),
  http.post('/api/jobs/recovery/retry-pending', () => HttpResponse.json({ enqueued: 1 })),
  http.post('/api/jobs/recovery/retry-error', () => HttpResponse.json({ enqueued: 1 })),
  http.post('/api/jobs/recovery/clear-failed', () => HttpResponse.json({ enqueued: 1 })),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());

// FeedPage now consumes the global submit dialog + header the (dashboard)
// layout provides; render the same tree here so both triggers stay covered.
function FeedTree({
  restricted = false,
}: { restricted?: boolean } = {}) {
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
    // Stable identity like the real useRouter - an unstable object re-fires
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

const STATS = {
  total: 5,
  by_status: { done: 3, error: 1 },
  by_content_type: { short: 3, long: 2 },
};
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
  useFuseFilter: vi.fn(),
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
import { useFuseFilter } from '@/lib/hooks/useFuseSearch';
import { useInFlightPolling } from '@/lib/hooks/useInFlightPolling';

const mockUseFeedData = vi.mocked(useFeedData);
const mockUseFuseFilter = vi.mocked(useFuseFilter);

function setupMocks(
  overrides: Partial<ReturnType<typeof useFeedData>> = {},
) {
  mockUseFeedData.mockReturnValue({
    tagCounts: {},
    stats: STATS,
    jobs: JOBS,
    total: JOBS.length,
    loading: false,
    error: null,
    reload: vi.fn(),
    preloadIndexes: new Map(),
    ...overrides,
  } as ReturnType<typeof useFeedData>);

  mockUseFuseFilter.mockReturnValue(JOBS);

  vi.mocked(useInFlightPolling).mockReturnValue(undefined);
}

async function openRecoveryActions() {
  fireEvent.click(
    await screen.findByRole('button', { name: /4 need attention/i }),
  );
}

let fetchSpy: MockInstance<typeof fetch>;

beforeEach(() => {
  window.localStorage.clear();
  navigationMock.replace.mockClear();
  navigationMock.searchParams = new URLSearchParams();
  googleStatusMock.connected = null;
  mockUseFeedData.mockReset();
  mockUseFuseFilter.mockReset();
  fetchSpy = vi.spyOn(globalThis, 'fetch');
  setupMocks();
});

afterEach(() => {
  fetchSpy.mockRestore();
  server.resetHandlers();
});

// extractSharedUrl unit tests live beside the helper: lib/share-target.test.ts

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
    expect(
      screen.getByRole('link', { name: /connect google/i }),
    ).toBeTruthy();
  });

  it('hides the Connect Google nudge when connected', () => {
    googleStatusMock.connected = true;
    render(<FeedTree />);
    expect(
      screen.queryByRole('link', { name: /connect google/i }),
    ).toBeNull();
  });

  it('hides the Connect Google nudge while status is unknown', () => {
    render(<FeedTree />);
    expect(
      screen.queryByRole('link', { name: /connect google/i }),
    ).toBeNull();
  });

  it('shows a one-time success banner on ?google=connected and strips the param', () => {
    navigationMock.searchParams = new URLSearchParams(
      'google=connected',
    );
    render(<FeedTree />);
    expect(screen.getByText(/google connected/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('shows a denied banner on ?google=denied and strips the param', () => {
    navigationMock.searchParams = new URLSearchParams(
      'google=denied',
    );
    render(<FeedTree />);
    expect(screen.getByText(/connection was denied/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('preserves other query params when stripping ?google=', () => {
    navigationMock.searchParams = new URLSearchParams(
      'type=short&google=connected',
    );
    render(<FeedTree />);
    expect(navigationMock.replace).toHaveBeenCalledWith(
      '/feed?type=short',
      { scroll: false },
    );
  });

  it('strips ?google= and an unsupported ?type= in a single replace', () => {
    navigationMock.searchParams = new URLSearchParams(
      'type=bogus&google=connected',
    );
    render(<FeedTree />);
    expect(screen.getByText(/google connected/i)).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledTimes(1);
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('still drops an unsupported ?type= without a google param', () => {
    setupMocks();
    navigationMock.searchParams = new URLSearchParams('type=bogus');
    render(<FeedTree />);
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('hands share_text URLs to the Submit URL dialog and strips share params once', async () => {
    navigationMock.searchParams = new URLSearchParams(
      'share_title=Nice&share_text=Check+this+out+https%3A%2F%2Fexample.com%2Fx+%F0%9F%98%8D',
    );
    const { rerender } = render(<FeedTree />);

    await waitFor(() =>
      expect(
        screen.getByRole('dialog', { name: 'Submit URL' }),
      ).toBeTruthy(),
    );
    expect(
      screen.getByDisplayValue('https://example.com/x'),
    ).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });

    navigationMock.replace.mockClear();
    navigationMock.searchParams = new URLSearchParams();
    rerender(<FeedTree />);

    expect(navigationMock.replace).not.toHaveBeenCalled();
  });

  it('strips share params even when no shared URL can be extracted', () => {
    navigationMock.searchParams = new URLSearchParams(
      'share_text=nope&share_url=ftp%3A%2F%2Fexample.com',
    );
    render(<FeedTree />);

    expect(
      screen.queryByRole('dialog', { name: 'Submit URL' }),
    ).toBeNull();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('shows job count when loaded', () => {
    render(<FeedTree />);
    expect(screen.getByText('1 job')).toBeTruthy();
  });

  it('shows skeleton during first load (loading=true, no jobs, no error)', () => {
    setupMocks({
      loading: true,
      jobs: [],
      total: 0,
      stats: undefined,
      error: null,
    });
    mockUseFuseFilter.mockReturnValue([]);
    render(<FeedTree />);
    expect(screen.getByText('loading…')).toBeTruthy();
  });

  it('shows syncing label while loading with existing jobs', () => {
    setupMocks({ loading: true, jobs: JOBS, total: 1 });
    render(<FeedTree />);
    expect(screen.getByText('syncing…')).toBeTruthy();
  });

  it('shows error banner on error', () => {
    setupMocks({
      error: 'Failed to load jobs',
      jobs: [],
      total: 0,
      stats: undefined,
    });
    mockUseFuseFilter.mockReturnValue([]);
    render(<FeedTree />);
    expect(screen.getByText(/failed to load jobs/i)).toBeTruthy();
  });

  it('shows result count when query is present', () => {
    navigationMock.searchParams = new URLSearchParams('q=test');
    setupMocks();
    mockUseFuseFilter.mockReturnValue(JOBS);
    render(<FeedTree />);
    expect(screen.getByText('1 result')).toBeTruthy();
  });

  it('shows empty state when no jobs match and no filters', () => {
    setupMocks({ jobs: [], total: 0, stats: undefined });
    mockUseFuseFilter.mockReturnValue([]);
    render(<FeedTree />);
    // empty state renders something when displayedJobs.length === 0 and no first load
    expect(screen.getByText('0 jobs')).toBeTruthy();
  });

  it('shows plural job count', () => {
    const multiJobs = [
      {
        id: 'j1',
        url: 'https://a.com',
        title: 'A',
        content_type: 'short',
        status: 'done',
        created_at: '',
      },
      {
        id: 'j2',
        url: 'https://b.com',
        title: 'B',
        content_type: 'long',
        status: 'done',
        created_at: '',
      },
    ];
    setupMocks({ jobs: multiJobs, total: 2 });
    mockUseFuseFilter.mockReturnValue(multiJobs);
    render(<FeedTree />);
    expect(screen.getByText('2 jobs')).toBeTruthy();
  });

  // The back-navigation fix: a job detail page is a separate route, so Back
  // remounts the Feed. Anything not in the URL is gone — which is why the whole
  // scope, not just ?type=, has to round-trip through it.
  it('restores the whole filter scope from the URL on a remount', () => {
    navigationMock.searchParams = new URLSearchParams(
      'type=short&status=done&q=skill&checklist=1&tags=t1,t2',
    );
    render(<FeedTree />);
    expect(mockUseFeedData).toHaveBeenCalledWith(
      {
        contentType: 'short',
        status: 'done',
        query: 'skill',
        checklistOnly: true,
        tags: ['t1', 't2'],
        view: 'jobs',
      },
      false,
    );
    expect(mockUseFuseFilter).toHaveBeenCalledWith(
      expect.anything(),
      'skill',
    );
  });

  // The adoption/projection race: both effects run in the same commit, adoption
  // first. It only *queues* the incoming scope, so the projection effect still
  // sees the previous one — and would replace() the URL the user just navigated
  // to back to the one they left.
  it('adopts an external /feed navigation instead of restoring the previous scope', () => {
    navigationMock.searchParams = new URLSearchParams('status=done&q=skill');
    const { rerender } = render(<FeedTree />);
    navigationMock.replace.mockClear();

    // Sidebar "Feed" click from an already-filtered feed: new URL, no remount.
    navigationMock.searchParams = new URLSearchParams();
    rerender(<FeedTree />);

    expect(navigationMock.replace).not.toHaveBeenCalled();
    expect(mockUseFeedData).toHaveBeenLastCalledWith(
      expect.objectContaining({ status: '', query: '' }),
      false,
    );
  });

  // Every replace() is fed back as the next searchParams, the way App Router
  // publishes it — so a scope that never settles shows up as a replace() loop
  // rather than passing on the first render.
  it('settles the URL after an external navigation instead of ping-ponging', () => {
    navigationMock.searchParams = new URLSearchParams('status=done&q=skill');
    const { rerender } = render(<FeedTree />);

    // Navigate to a URL that still needs canonicalizing (?google= is transient),
    // so there is a real projection to converge on.
    navigationMock.searchParams = new URLSearchParams(
      'type=short&checklist=1&google=denied',
    );
    navigationMock.replace.mockClear();
    rerender(<FeedTree />);

    for (let i = 0; i < 5; i += 1) {
      const call = navigationMock.replace.mock.calls.at(-1);
      if (!call) break; // nothing new to publish — the URL has settled
      navigationMock.replace.mockClear();
      navigationMock.searchParams = new URLSearchParams(
        (call[0] as string).split('?')[1] ?? '',
      );
      rerender(<FeedTree />);
    }

    expect(navigationMock.searchParams.toString()).toBe('type=short&checklist=1');
  });

  it('writes the search query to the URL so Back can restore it', () => {
    render(<FeedTree />);
    fireEvent.change(screen.getByLabelText('Search by title or URL'), {
      target: { value: 'skill' },
    });
    expect(navigationMock.replace).toHaveBeenCalledWith(
      '/feed?q=skill',
      { scroll: false },
    );
  });

  // searchParams only updates once App Router publishes the previous replace().
  // A second control touched before that lands must not clone stale params and
  // silently drop the first filter from the URL.
  it('keeps an earlier filter when a second one is set before the URL updates', () => {
    navigationMock.searchParams = new URLSearchParams('q=skill');
    render(<FeedTree />);
    // searchParams deliberately left empty — the mock never publishes the write.
    fireEvent.click(screen.getByRole('button', { name: 'Done' }));
    expect(navigationMock.replace).toHaveBeenCalledWith(
      '/feed?status=done&q=skill',
      { scroll: false },
    );
  });

  it('deletes a filter param when its filter is cleared', () => {
    // The input has to actually hold the query, or clearing it is a no-op event.
    navigationMock.searchParams = new URLSearchParams('q=skill');
    render(<FeedTree />);
    fireEvent.change(screen.getByLabelText('Search by title or URL'), {
      target: { value: '' },
    });
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
  });

  it('restores a tag filter from the URL at any feed size', () => {
    navigationMock.searchParams = new URLSearchParams('tags=t1,t2');
    render(<FeedTree />);
    expect(mockUseFeedData).toHaveBeenCalledWith(
      {
        contentType: '',
        status: '',
        query: '',
        checklistOnly: false,
        tags: ['t1', 't2'],
        view: 'jobs',
      },
      false,
    );
  });

  it('initializes content type from the URL type param', () => {
    navigationMock.searchParams = new URLSearchParams('type=short');
    render(<FeedTree />);
    expect(mockUseFeedData).toHaveBeenCalledWith(
      {
        contentType: 'short',
        status: '',
        query: '',
        checklistOnly: false,
        tags: [],
        view: 'jobs',
      },
      false,
    );
  });

  it('renders content-type tabs with counts', () => {
    render(<FeedTree />);
    expect(
      screen.getByRole('button', { name: /all 5/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /short 3/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /long 2/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /article 0/i }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /repo 0/i }),
    ).toBeTruthy();
  });

  it('renders extracted links as a first-class Feed view', async () => {
    server.use(
      http.get('/api/brain/links/view', () =>
        HttpResponse.json({ order: 'desc', size: 25 }),
      ),
      http.put('/api/brain/links/view', () =>
        HttpResponse.json({ order: 'desc', size: 25 }),
      ),
      http.get('/api/brain/links', () =>
        HttpResponse.json({
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
      ),
    );

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /links/i }));

    await waitFor(() => {
      // Link rows show the trimmed URL (path only); the full URL lives in
      // tooltip + expanded More panel.
      expect(
        screen.getAllByText('/canonical').length,
      ).toBeGreaterThan(0);
    });
    expect(navigationMock.replace).toHaveBeenCalledWith(
      '/feed?view=links',
      { scroll: false },
    );
    expect(screen.queryByText('Jobs')).toBeNull();
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/brain/links?limit=25&offset=0&order=desc',
    );
  });

  // switchToLinks used to clone `searchParams` directly instead of the ref
  // setFeedScope advances immediately -- so a filter picked right before
  // opening Links (still unpublished by App Router) was silently dropped from
  // the URL, even though switchToLinks never meant to touch it (CodeRabbit,
  // PR #626).
  it('keeps a pending scope change when Links is opened before the URL updates', () => {
    server.use(
      http.get('/api/brain/links/view', () =>
        HttpResponse.json({ order: 'desc', size: 25 }),
      ),
      http.get('/api/brain/links', () =>
        HttpResponse.json({ items: [], limit: 25, offset: 0, total: 0 }),
      ),
    );
    render(<FeedTree />);
    // searchParams deliberately left empty — the mock never publishes the write.
    fireEvent.click(screen.getByRole('button', { name: 'Done' }));
    fireEvent.click(screen.getByRole('button', { name: /links/i }));

    expect(navigationMock.replace).toHaveBeenLastCalledWith(
      '/feed?status=done&view=links',
      { scroll: false },
    );
  });

  it('omits the Links view and skips authenticated links fetches in restricted mode', async () => {
    navigationMock.searchParams = new URLSearchParams('view=links');

    render(<FeedTree restricted />);

    expect(
      screen.queryByRole('button', { name: /^links$/i }),
    ).toBeNull();
    expect(screen.getByText('Jobs')).toBeTruthy();
    expect(navigationMock.replace).toHaveBeenCalledWith('/feed', {
      scroll: false,
    });
    expect(fetchSpy).not.toHaveBeenCalledWith(
      '/api/brain/links/view',
    );
    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).startsWith('/api/brain/links'),
      ),
    ).toBe(false);
  });

  it('renders one mobile intake launcher instead of separate Submit and Docs chips', () => {
    render(<FeedTree />);

    expect(
      screen.getByRole('button', { name: 'Add to your Index' }),
    ).toBeTruthy();
    expect(
      screen.queryByRole('button', { name: 'Submit URL' }),
    ).toBeNull();
    expect(
      screen.queryByRole('button', { name: 'Ingest docs' }),
    ).toBeNull();
  });

  it('opens the intake sheet from the mobile launcher in restricted mode and gates per item', async () => {
    render(<FeedTree restricted />);
    fireEvent.click(
      screen.getByRole('button', { name: 'Keep looking' }),
    );

    fireEvent.click(
      screen.getByRole('button', { name: 'Add to your Index' }),
    );

    expect(screen.getByText('Add to your Index')).toBeTruthy();
    expect(
      screen.getByText(
        'Save a link as-is to your Brain - no processing.',
      ),
    ).toBeTruthy();

    fireEvent.click(
      screen.getByRole('button', {
        name: /Submit URL\s*Paste a URL/i,
      }),
    );

    await waitFor(() =>
      expect(
        screen.getByText('Sign in to submit URLs to your own Index.'),
      ).toBeTruthy(),
    );
    expect(
      screen.queryByRole('dialog', { name: 'Submit URL' }),
    ).toBeNull();
  });

  it('opens the docs ingest dialog with the D shortcut', async () => {
    render(<FeedTree />);
    fireEvent.keyDown(window, { key: 'd' });
    expect(await screen.findByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Ingest Docs')).toBeTruthy();
    // The dialog now hosts the full DocUploadPanel (URL fetch + PDF drop),
    // not the old "Open Doc Parser" redirect button.
    expect(
      screen.getByRole('button', { name: /fetch/i }),
    ).toBeTruthy();
  });

  it('updates the type query param when a content tab is clicked', () => {
    setupMocks();

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /long 2/i }));

    expect(navigationMock.replace).toHaveBeenCalledWith(
      '/feed?type=long',
      { scroll: false },
    );
  });

  it('renders the all tab as the bento grid by default', () => {
    render(<FeedTree />);
    // Bento cards carry their row-span; landscape spans 2 row-units.
    const card = screen.getByRole('link', {
      name: /job one/i,
    }).parentElement;

    expect(card?.className).toContain('sm:row-span-2');
  });

  it('toggles the all tab to the flat list and persists the choice', () => {
    render(<FeedTree />);
    fireEvent.click(
      screen.getByRole('button', { name: /list layout/i }),
    );

    // JobCard uses an overlay link inside a styled wrapper; assert on the wrapper.
    const card = screen.getByRole('link', {
      name: /job one/i,
    }).parentElement;
    expect(card?.className).toContain('px-4');
    expect(card?.className).toContain('py-3');
    expect(window.localStorage.getItem('ownix.feed.layout')).toBe(
      'list',
    );
  });

  it('restores the persisted list layout on mount', () => {
    window.localStorage.setItem('ownix.feed.layout', 'list');
    render(<FeedTree />);

    const card = screen.getByRole('link', {
      name: /job one/i,
    }).parentElement;
    expect(card?.className).toContain('px-4');
  });

  it('hides the layout toggle on typed tabs', () => {
    setupMocks();
    navigationMock.searchParams = new URLSearchParams('type=short');
    render(<FeedTree />);

    expect(
      screen.queryByRole('button', { name: /list layout/i }),
    ).toBeNull();
  });

  it('renders the short tab as the compact shorts grid', () => {
    setupMocks();
    navigationMock.searchParams = new URLSearchParams('type=short');
    render(<FeedTree />);

    const card = screen.getByRole('link', {
      name: /job one/i,
    }).parentElement;
    // Compact shorts card drops the status badge; status stays in the pills.
    expect(card?.querySelector('.font-mono')).toBeTruthy();
    expect(card?.textContent).not.toContain('done');
  });

  it('renders typed tabs as preview cards', () => {
    setupMocks();
    navigationMock.searchParams = new URLSearchParams('type=short');

    render(<FeedTree />);
    // Preview cards use a stretched overlay link; flex/p-3 and the date text live
    // on the card container, the link's parent.
    const card = screen.getByRole('link', {
      name: /job one/i,
    }).parentElement;

    expect(card?.className).toContain('flex');
    expect(card?.className).toContain('p-3');
    expect(card?.textContent).toContain(
      new Date(JOBS[0].created_at).toLocaleString(),
    );
  });

  it('renders the recovery panel from the active tab summary', async () => {
    setupMocks();
    navigationMock.searchParams = new URLSearchParams('type=short');

    render(<FeedTree />);
    await openRecoveryActions();

    expect(
      await screen.findByRole('button', {
        name: /retry pending \(2\)/i,
      }),
    ).toBeTruthy();
    expect(
      screen.getByRole('button', { name: /retry failed \(2\)/i }),
    ).toBeTruthy();
    expect(screen.getByText('1 stale in-flight')).toBeTruthy();
    expect(fetch).toHaveBeenCalledWith(
      '/api/jobs/recovery/summary?content_type=short',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('refreshes recovery summary and feed data after retrying pending jobs', async () => {
    const reload = vi.fn();
    setupMocks({ reload });
    navigationMock.searchParams = new URLSearchParams('type=short');

    render(<FeedTree />);
    await openRecoveryActions();
    fireEvent.click(
      await screen.findByRole('button', {
        name: /retry pending \(2\)/i,
      }),
    );

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
    fireEvent.click(
      await screen.findByRole('button', {
        name: /clear failed \(1\)/i,
      }),
    );

    expect(confirmMock).toHaveBeenCalledWith(
      'Clear failed jobs in this tab? This marks them cancelled; it does not delete them from DB.',
    );
  });

  it('reloads the feed when the error banner retry is clicked', () => {
    const reload = vi.fn();
    setupMocks({
      error: 'Failed to load jobs',
      jobs: [],
      total: 0,
      stats: undefined,
      reload,
    });
    mockUseFuseFilter.mockReturnValue([]);

    render(<FeedTree />);
    fireEvent.click(screen.getByRole('button', { name: /^retry$/i }));

    expect(reload).toHaveBeenCalled();
  });

  it('keeps an accepted submission visible when the post-submit refresh fails', async () => {
    // Pass the merged feed through so optimistic rows actually render.
    mockUseFuseFilter.mockImplementation((jobs: JobSummary[]) => jobs);
    // reload resolves without delivering the new job - useFeedData swallows
    // background fetch errors, so a failed refresh looks exactly like this.
    const reload = vi.fn(async () => {});
    mockUseFeedData.mockReturnValue({
      tagCounts: {},
      tagFilterDisabled: false,
      stats: STATS,
      jobs: JOBS,
      total: JOBS.length,
      loading: false,
      error: null,
      reload,
      preloadIndexes: new Map(),
    } as ReturnType<typeof useFeedData>);
    server.use(
      http.post('/api/jobs', () =>
        HttpResponse.json({
          id: 'accepted-1',
          job_id: 'accepted-1',
          url: 'https://example.com/new',
          content_type: 'short',
          status: 'pending',
          title: null,
        }),
      ),
    );

    render(<FeedTree />);
    fireEvent.keyDown(window, {
      ctrlKey: true,
      key: 'K',
      shiftKey: true,
    });
    fireEvent.click(
      screen.getByRole('button', { name: /Submit URL\s*N/i }),
    );
    fireEvent.change(screen.getByPlaceholderText(/paste a video/i), {
      target: { value: 'https://example.com/new' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /^submit$/i }),
    );

    await waitFor(() => expect(reload).toHaveBeenCalled());
    // The accepted job survives the stale refresh (title is null → card shows the URL)…
    expect(screen.getByText('https://example.com/new')).toBeTruthy();
    // …and it feeds the in-flight poll so the refresh keeps retrying.
    const polled =
      vi.mocked(useInFlightPolling).mock.calls.at(-1)?.[0] ?? [];
    expect(
      polled.some(
        (j) => j.id === 'accepted-1' && j.status === 'pending',
      ),
    ).toBe(true);
  });

  it('drops the optimistic copy once the refreshed feed carries the job', async () => {
    mockUseFuseFilter.mockImplementation((jobs: JobSummary[]) => jobs);
    const reload = vi.fn(async () => {});
    const feedState = {
      tagCounts: {},
      tagFilterDisabled: false,
      stats: STATS,
      jobs: JOBS,
      total: JOBS.length,
      loading: false,
      error: null,
      reload,
      preloadIndexes: new Map(),
    } as ReturnType<typeof useFeedData>;
    mockUseFeedData.mockReturnValue(feedState);
    server.use(
      http.post('/api/jobs', () =>
        HttpResponse.json({
          id: 'accepted-1',
          url: 'https://example.com/new',
          content_type: 'short',
          status: 'pending',
          title: null,
        }),
      ),
    );

    const { rerender } = render(<FeedTree />);
    fireEvent.keyDown(window, {
      ctrlKey: true,
      key: 'K',
      shiftKey: true,
    });
    fireEvent.click(
      screen.getByRole('button', { name: /Submit URL\s*N/i }),
    );
    fireEvent.change(screen.getByPlaceholderText(/paste a video/i), {
      target: { value: 'https://example.com/new' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /^submit$/i }),
    );
    await waitFor(() =>
      expect(
        screen.getByText('https://example.com/new'),
      ).toBeTruthy(),
    );

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

    // Exactly one row - no optimistic duplicate alongside the server copy.
    await waitFor(() =>
      expect(
        screen.getAllByText('https://example.com/new'),
      ).toHaveLength(1),
    );
  });

  // The sidebar's own "Feed" link, clicked from an already-filtered feed,
  // changes the params without remounting this page. The scope is seeded at
  // mount, so it has to adopt an outside navigation explicitly.
  it('adopts a /feed navigation that lands without a remount', () => {
    navigationMock.searchParams = new URLSearchParams('type=short');
    const { rerender } = render(<FeedTree />);
    expect(mockUseFeedData).toHaveBeenLastCalledWith(
      expect.objectContaining({ contentType: 'short' }),
      false,
    );

    navigationMock.searchParams = new URLSearchParams();
    rerender(<FeedTree />);

    expect(mockUseFeedData).toHaveBeenLastCalledWith(
      expect.objectContaining({ contentType: '', view: 'jobs' }),
      false,
    );
  });

  it('clears every filter from the empty-state Clear button', () => {
    // "Every filter" has to include the toggle chips — an active one that
    // survives Clear strands the feed in a filtered view with nothing left
    // to click. The bare '/feed' the projection writes is the proof: the
    // address bar is the scope, so a param left behind is a filter left on.
    navigationMock.searchParams = new URLSearchParams(
      'status=error&checklist=1&q=skill',
    );
    setupMocks({ jobs: [], total: 0, stats: undefined });
    mockUseFuseFilter.mockReturnValue([]);

    render(<FeedTree />);
    fireEvent.click(
      screen.getByRole('button', { name: /clear filters/i }),
    );

    expect(navigationMock.replace).toHaveBeenLastCalledWith('/feed', {
      scroll: false,
    });
  });
});
