// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { UrlsTab } from './UrlsTab';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 's1' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/spaces/s1',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useAddSearch', () => ({ useAddSearch: vi.fn() }));

vi.mock('@/lib/hooks/useSpaceUrls', () => ({
  useSpaceUrls: vi.fn(),
}));

import { useSpaceUrls } from '@/lib/hooks/useSpaceUrls';
import { useAddSearch } from '@/lib/hooks/useAddSearch';
const mockUseSpaceUrls = vi.mocked(useSpaceUrls);
const mockUseAddSearch = vi.mocked(useAddSearch);

const SPACE_URLS = [
  { id: 'j1', title: 'Video One', url: 'https://youtube.com/watch?v=1', content_type: 'long', status: 'done', sort_order: 1, added_at: '' },
  { id: 'j2', title: null, url: 'https://instagram.com/reel/abc', content_type: 'short', status: 'done', sort_order: 2, added_at: '' },
];
const ALL_JOBS = [
  { id: 'j3', url: 'https://youtube.com/watch?v=3', title: 'Job Three', content_type: 'long', status: 'done', created_at: '' },
];

function setupMocks(overrides: Partial<ReturnType<typeof useSpaceUrls>> = {}) {
  mockUseAddSearch.mockReturnValue({ query: '', setQuery: vi.fn(), results: [] });
  mockUseSpaceUrls.mockReturnValue({
    spaceUrls: SPACE_URLS,
    allJobs: ALL_JOBS,
    loading: false,
    addJob: vi.fn(),
    removeUrl: vi.fn(),
    reorderUrl: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useSpaceUrls>);
}

beforeEach(() => { setupMocks(); });

describe('UrlsTab', () => {
  it('shows loading skeleton when loading', () => {
    setupMocks({ loading: true, spaceUrls: [], allJobs: [] });
    render(<UrlsTab spaceId="s1" />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows empty message when no URLs', () => {
    setupMocks({ spaceUrls: [] });
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText(/no jobs added yet/i)).toBeTruthy();
  });

  it('renders list of space URLs', () => {
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText('Video One')).toBeTruthy();
  });

  it('uses raw URL as display when title is null', () => {
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText('https://instagram.com/reel/abc')).toBeTruthy();
  });

  it('renders content type badges', () => {
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText('long')).toBeTruthy();
    expect(screen.getByText('short')).toBeTruthy();
  });

  it('renders Remove buttons', () => {
    render(<UrlsTab spaceId="s1" />);
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    expect(removeButtons).toHaveLength(2);
  });

  it('calls removeUrl when Remove is clicked', () => {
    const removeUrl = vi.fn();
    setupMocks({ removeUrl });
    render(<UrlsTab spaceId="s1" />);
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);
    expect(removeUrl).toHaveBeenCalledWith('j1');
  });

  it('renders the merged search input', () => {
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });

  it('calls setQuery when typing in the search input', () => {
    const setQuery = vi.fn();
    mockUseAddSearch.mockReturnValue({ query: '', setQuery, results: [] });
    render(<UrlsTab spaceId="s1" />);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'foo' } });
    expect(setQuery).toHaveBeenCalledWith('foo');
  });

  it('renders search results returned by useAddSearch', () => {
    mockUseAddSearch.mockReturnValue({
      query: 'foo',
      setQuery: vi.fn(),
      results: [{ url: 'https://example.com/a', title: 'Result A', jobId: 'j9' }],
    });
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText('Result A')).toBeTruthy();
  });

  it('clicking Add on a resolved result calls addJob with its jobId', () => {
    const addJob = vi.fn();
    setupMocks({ addJob });
    mockUseAddSearch.mockReturnValue({
      query: 'foo',
      setQuery: vi.fn(),
      results: [{ url: 'https://example.com/a', title: 'Result A', jobId: 'j9' }],
    });
    render(<UrlsTab spaceId="s1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    expect(addJob).toHaveBeenCalledWith('j9');
  });

  it('clicking Save & Add on an unresolved result saves the URL then calls addJob', async () => {
    const addJob = vi.fn();
    setupMocks({ addJob });
    mockUseAddSearch.mockReturnValue({
      query: 'foo',
      setQuery: vi.fn(),
      results: [{ url: 'https://example.com/b', title: 'Result B' }],
    });
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ job_id: 'j10' }), { status: 200 }),
    );
    render(<UrlsTab spaceId="s1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Save & Add' }));
    await waitFor(() => expect(addJob).toHaveBeenCalledWith('j10'));
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/jobs',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ url: 'https://example.com/b' }),
      }),
    );
  });

  it('a failed save renders an inline error and does not call addJob', async () => {
    const addJob = vi.fn();
    setupMocks({ addJob });
    mockUseAddSearch.mockReturnValue({
      query: 'foo',
      setQuery: vi.fn(),
      results: [{ url: 'https://example.com/c', title: 'Result C' }],
    });
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Unsupported URL' }), { status: 422 }),
    );
    render(<UrlsTab spaceId="s1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Save & Add' }));
    await waitFor(() => expect(screen.getByText('Unsupported URL')).toBeTruthy());
    expect(addJob).not.toHaveBeenCalled();
  });

  it('renders reorder up/down buttons', () => {
    render(<UrlsTab spaceId="s1" />);
    const upBtns = screen.getAllByRole('button', { name: /move up/i });
    const downBtns = screen.getAllByRole('button', { name: /move down/i });
    expect(upBtns.length).toBeGreaterThan(0);
    expect(downBtns.length).toBeGreaterThan(0);
  });

  it('calls reorderUrl when Move down is clicked', () => {
    const reorderUrl = vi.fn();
    setupMocks({ reorderUrl });
    render(<UrlsTab spaceId="s1" />);
    const downBtns = screen.getAllByRole('button', { name: /move down/i });
    // First item's down button
    fireEvent.click(downBtns[0]);
    expect(reorderUrl).toHaveBeenCalledWith(0, 'down');
  });
});
