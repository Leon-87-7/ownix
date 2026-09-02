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

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'j1' }),
  useSearchParams: () => searchParams,
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
