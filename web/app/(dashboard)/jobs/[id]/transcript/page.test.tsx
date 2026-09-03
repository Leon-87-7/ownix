// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import TranscriptEditPage from './page';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());

let searchParams = new URLSearchParams();
const mockBack = vi.fn();
const mockPush = vi.fn();

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'j1' }),
  useSearchParams: () => searchParams,
  useRouter: () => ({ back: mockBack, push: mockPush }),
}));

vi.mock('@/lib/hooks/useJobDetail', () => ({
  useJobDetail: vi.fn(),
}));
vi.mock('@/lib/restricted/context', () => ({
  useRestrictedMode: vi.fn(() => ({ restricted: false, showRestrictedToast: vi.fn() })),
}));
// next/dynamic calls are resolved; mock the dynamic import target directly.
// Forwards onSave via a button so tests can simulate an edit without needing
// the real Milkdown editor.
vi.mock('next/dynamic', () => ({
  default: (fn: () => Promise<{ default: React.ComponentType }>) => {
    const Component = (props: { initialMarkdown?: string; onSave?: (md: string) => void }) => (
      <div data-testid="dynamic-component">
        {props.initialMarkdown}
        {props.onSave && (
          <button type="button" onClick={() => props.onSave!('edited transcript text')}>
            Simulate edit
          </button>
        )}
      </div>
    );
    return Component;
  },
}));

import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useRestrictedMode } from '@/lib/restricted/context';

const mockUseJobDetail = vi.mocked(useJobDetail);
const mockUseRestrictedMode = vi.mocked(useRestrictedMode);

const JOB = {
  id: 'j1',
  transcript: 'Full long-video transcript',
} as JobDetail;

function setupMocks(overrides: Partial<ReturnType<typeof useJobDetail>> = {}) {
  mockUseJobDetail.mockReturnValue({
    job: JOB,
    fetchState: 'ok',
    setData: vi.fn(),
    reload: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  } as ReturnType<typeof useJobDetail>);
}

beforeEach(() => {
  server.resetHandlers();
  setupMocks();
  mockUseRestrictedMode.mockReturnValue({ restricted: false, showRestrictedToast: vi.fn() });
  searchParams = new URLSearchParams();
  mockBack.mockClear();
  mockPush.mockClear();
});

describe('TranscriptEditPage', () => {
  it('shows a loading skeleton while the job fetches', () => {
    setupMocks({ fetchState: 'loading', job: null });
    render(<TranscriptEditPage />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows a fallback with a link back to the feed when the job fails to load', () => {
    setupMocks({ fetchState: 'error', job: null });
    render(<TranscriptEditPage />);
    expect(screen.getByText(/couldn't load this job/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to feed/i })).toHaveAttribute('href', '/feed');
  });

  it('renders a back link to the job and the editor pre-filled with the transcript', () => {
    render(<TranscriptEditPage />);
    expect(screen.getByRole('link', { name: /back to job/i })).toHaveAttribute('href', '/jobs/j1');
    expect(screen.getByTestId('dynamic-component')).toHaveTextContent('Full long-video transcript');
  });

  it('pops history instead of pushing a duplicate job entry when the back link is clicked', () => {
    // Arriving at Transcript always means Detail was pushed onto history
    // first - mirror that so history.length > 1, same as real usage.
    window.history.pushState({}, '', '/jobs/j1/transcript');
    render(<TranscriptEditPage />);
    fireEvent.click(screen.getByRole('link', { name: /back to job/i }));
    expect(mockBack).toHaveBeenCalledOnce();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('falls back to router.push with the scoped job href when there is no history to pop', () => {
    const historyLengthSpy = vi.spyOn(window.history, 'length', 'get').mockReturnValue(1);
    try {
      render(<TranscriptEditPage />);
      fireEvent.click(screen.getByRole('link', { name: /back to job/i }));
      expect(mockPush).toHaveBeenCalledWith('/jobs/j1');
      expect(mockBack).not.toHaveBeenCalled();
    } finally {
      historyLengthSpy.mockRestore();
    }
  });

  it('leaves modified clicks (ctrl/cmd/shift/middle-click) to the plain Link href instead of intercepting navigation', () => {
    window.history.pushState({}, '', '/jobs/j1/transcript');
    render(<TranscriptEditPage />);
    const link = screen.getByRole('link', { name: /back to job/i });
    fireEvent.click(link, { metaKey: true });
    fireEvent.click(link, { ctrlKey: true });
    fireEvent.click(link, { shiftKey: true });
    fireEvent.click(link, { button: 1 });
    expect(mockBack).not.toHaveBeenCalled();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('carries the active job-list filter scope onto the back link', () => {
    searchParams = new URLSearchParams('content_type=long&status=done');
    render(<TranscriptEditPage />);
    expect(screen.getByRole('link', { name: /back to job/i })).toHaveAttribute(
      'href',
      '/jobs/j1?content_type=long&status=done',
    );
  });

  it('saves an edit through the transcript PUT endpoint', async () => {
    let putBody: unknown;
    server.use(
      http.put('/api/jobs/:id/transcript', async ({ request }) => {
        const body = await request.json();
        putBody = body;
        return HttpResponse.json(body);
      }),
    );
    render(<TranscriptEditPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Simulate edit' }));
    await waitFor(() =>
      expect(putBody).toEqual({ transcript: 'edited transcript text' }),
    );
  });

  it('shows a read-only capped transcript in Restricted mode instead of the editor', () => {
    mockUseRestrictedMode.mockReturnValue({ restricted: true, showRestrictedToast: vi.fn() });
    render(<TranscriptEditPage />);
    expect(screen.getByText('Full long-video transcript')).toBeInTheDocument();
    expect(screen.queryByTestId('dynamic-component')).toBeNull();
  });
});
