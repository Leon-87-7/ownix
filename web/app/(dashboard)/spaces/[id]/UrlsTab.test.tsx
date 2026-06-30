// @vitest-environment jsdom
import { render, screen, fireEvent } from '@/test/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { UrlsTab } from './UrlsTab';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 's1' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/spaces/s1',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useSpaceUrls', () => ({
  useSpaceUrls: vi.fn(),
}));

import { useSpaceUrls } from '@/lib/hooks/useSpaceUrls';
const mockUseSpaceUrls = vi.mocked(useSpaceUrls);

const SPACE_URLS = [
  { id: 'j1', title: 'Video One', url: 'https://youtube.com/watch?v=1', content_type: 'long', status: 'done', sort_order: 1, added_at: '' },
  { id: 'j2', title: null, url: 'https://instagram.com/reel/abc', content_type: 'short', status: 'done', sort_order: 2, added_at: '' },
];
const ALL_JOBS = [
  { id: 'j3', url: 'https://youtube.com/watch?v=3', title: 'Job Three', content_type: 'long', status: 'done', created_at: '' },
];

function setupMocks(overrides: Partial<ReturnType<typeof useSpaceUrls>> = {}) {
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
  it('shows loading spinner when loading', () => {
    setupMocks({ loading: true, spaceUrls: [], allJobs: [] });
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByText('Loading…')).toBeTruthy();
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

  it('renders job select dropdown with available jobs', () => {
    render(<UrlsTab spaceId="s1" />);
    // j1, j2 are pinned; j3 should be in the select
    expect(screen.getByText(/job three/i)).toBeTruthy();
  });

  it('renders add button', () => {
    render(<UrlsTab spaceId="s1" />);
    expect(screen.getByRole('button', { name: /add/i })).toBeTruthy();
  });

  it('Add button is disabled when no job selected', () => {
    render(<UrlsTab spaceId="s1" />);
    const addBtn = screen.getByRole('button', { name: /^add$/i });
    expect(addBtn).toHaveAttribute('disabled');
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
