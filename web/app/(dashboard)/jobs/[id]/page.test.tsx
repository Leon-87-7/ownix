// @vitest-environment jsdom
import { act, fireEvent, render, renderHook, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useState } from 'react';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import JobDetailPage from './page';
import type { JobDetail } from '@/lib/hooks/useJobDetail';
import {
  resetAccessibilitySettingsForTests,
  useAccessibilitySettings,
} from '@/lib/hooks/useAccessibilitySettings';

const routerBack = vi.fn();
const routerPush = vi.fn();
let searchParams = new URLSearchParams();
const server = setupServer(
  // Default JOB fixture below is status 'done', content_type 'long', which
  // mounts RepoFollowupPanel on nearly every test — an unhandled fetch here
  // would error under onUnhandledRequest: 'error'. Tests exercising repo
  // follow-ups themselves override this via server.use(...).
  http.get('/api/jobs/:id/repo-followups', () => HttpResponse.json([])),
);

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 'j1' }),
  useRouter: () => ({ push: routerPush, replace: vi.fn(), back: routerBack }),
  usePathname: () => '/jobs/j1',
  useSearchParams: () => searchParams,
}));

vi.mock('@/lib/hooks/useJobDetail', () => ({
  useJobDetail: vi.fn(),
}));
vi.mock('@/lib/hooks/useJobAnnotation', () => ({
  useJobAnnotation: vi.fn(),
}));
vi.mock('@/lib/hooks/useJobTags', () => ({
  useJobTags: vi.fn(),
}));
vi.mock('@/lib/hooks/useLinkTags', () => ({
  useLinkTags: vi.fn(),
}));
vi.mock('@/lib/polling', () => ({ startPolling: vi.fn(() => vi.fn()) }));
vi.mock('@/lib/restricted/context', () => ({
  useRestrictedMode: vi.fn(() => ({ restricted: false, showRestrictedToast: vi.fn() })),
}));
vi.mock('@/components/ui/tag-picker', () => ({
  TagMenu: () => <div data-testid="tag-menu">TagMenu</div>,
  TagChips: () => <div data-testid="tag-chips">TagChips</div>,
}));
vi.mock('@/components/ui/markdown-editor', () => ({
  default: () => <div data-testid="markdown-editor">MarkdownEditor</div>,
}));
// next/dynamic calls are resolved; mock the dynamic import target directly.
// Forwards onSave via a button so tests can simulate an edit without needing
// the real Milkdown editor - only one dynamic() consumer (transcript or
// annotations) ever mounts at once across this file's tests, so a single
// shared testid stays unambiguous.
vi.mock('next/dynamic', () => ({
  default: (fn: () => Promise<{ default: React.ComponentType }>) => {
    const Component = (props: { onSave?: (md: string) => void }) => (
      <div data-testid="dynamic-component">
        Dynamic Component
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
import { useJobAnnotation } from '@/lib/hooks/useJobAnnotation';
import { useJobTags } from '@/lib/hooks/useJobTags';
import { useLinkTags } from '@/lib/hooks/useLinkTags';
import { useRestrictedMode } from '@/lib/restricted/context';
import { startPolling } from '@/lib/polling';

const mockUseJobDetail = vi.mocked(useJobDetail);
const mockUseJobAnnotation = vi.mocked(useJobAnnotation);
const mockUseJobTags = vi.mocked(useJobTags);
const mockUseLinkTags = vi.mocked(useLinkTags);
const mockUseRestrictedMode = vi.mocked(useRestrictedMode);
const mockStartPolling = vi.mocked(startPolling);

const JOB = {
  id: 'j1',
  url: 'https://www.youtube.com/watch?v=test123',
  content_type: 'long',
  status: 'done',
  title: 'My Awesome Video',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  completed_at: '2024-01-01T01:00:00Z',
  error_msg: null,
  drive_url: 'https://drive.google.com/file/d/abc',
  ai_topic: 'Machine Learning',
  ai_objective: 'Learn ML basics',
  ai_action_points: 'Study | Practice | Build',
  ai_tools: 'Python | PyTorch',
  ai_market_data: null,
  promise_gap: null,
  template: null,
  template_analysis: null,
  summary: null,
  transcript: null,
  code: null,
  code_lang: null,
  key_phrases: null,
  links: null,
  checklists_md: null,
  checklists_generated_at: null,
};

function setupMocks(
  jobDetailOverrides: Partial<ReturnType<typeof useJobDetail>> = {},
  annotationOverrides: Partial<ReturnType<typeof useJobAnnotation>> = {},
  tagsOverrides: Partial<ReturnType<typeof useJobTags>> = {},
) {
  mockUseJobDetail.mockReturnValue({
    job: JOB,
    fetchState: 'ok',
    setData: vi.fn(),
    reload: vi.fn().mockResolvedValue(undefined),
    ...jobDetailOverrides,
  } as ReturnType<typeof useJobDetail>);

  mockUseJobAnnotation.mockReturnValue({
    annotation: { notes: '', updated_at: null },
    loaded: false,
    handleSave: vi.fn(),
    ...annotationOverrides,
  } as ReturnType<typeof useJobAnnotation>);

  mockUseJobTags.mockReturnValue({
    jobTags: [],
    allTags: [],
    refetchTags: vi.fn(),
    toggleTag: vi.fn(),
    createTag: vi.fn(),
    ...tagsOverrides,
  } as ReturnType<typeof useJobTags>);
  mockUseLinkTags.mockReturnValue({
    linkTags: [],
    allTags: [],
    toggleTag: vi.fn(),
    createTag: vi.fn(),
  } as ReturnType<typeof useLinkTags>);
}

beforeEach(() => {
  server.resetHandlers();
  setupMocks();
  mockUseRestrictedMode.mockReturnValue({ restricted: false, showRestrictedToast: vi.fn() });
  routerBack.mockReset();
  routerPush.mockReset();
  searchParams = new URLSearchParams();
  vi.unstubAllGlobals();
  mockStartPolling.mockReset();
  mockStartPolling.mockReturnValue(vi.fn());
  resetAccessibilitySettingsForTests();
});

describe('JobDetailPage', () => {
  it('offers speech for speakable enrichment fields', () => {
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn());
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Listen to Objective' })).toBeInTheDocument();
  });

  it('speaks the stripped field text when its listen button is clicked', () => {
    const speak = vi.fn();
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Listen to Objective' }));
    expect(speak).toHaveBeenCalledWith(expect.objectContaining({ text: 'Learn ML basics' }));
  });

  it('does not offer speech for links or code fields', () => {
    vi.stubGlobal('speechSynthesis', { cancel: vi.fn(), speak: vi.fn() });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn());
    setupMocks({
      job: {
        ...JOB,
        content_type: 'short',
        summary: 'A summary',
        code: 'console.log("hello")',
        links: '[{"url":"https://example.com"}]',
      },
    });
    render(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Listen to Code' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Listen to Links Found' })).not.toBeInTheDocument();
  });

  it.each(['link', 'article', 'repo'])('uses link tags for a resolved %s job', (contentType) => {
    setupMocks({ job: { ...JOB, content_type: contentType, link_id: 'link-1' } });
    render(<JobDetailPage />);
    expect(mockUseJobTags).toHaveBeenCalledWith('j1', 'ok', true);
    expect(mockUseLinkTags).toHaveBeenCalledWith('link-1', [], false, true);
  });

  it.each(['article', 'repo'])('uses editable job tags while an %s link is absent', (contentType) => {
    setupMocks({ job: { ...JOB, content_type: contentType } });
    render(<JobDetailPage />);
    expect(mockUseJobTags).toHaveBeenCalledWith('j1', 'ok', false);
    expect(mockUseLinkTags).toHaveBeenCalledWith('', [], true, true);
  });

  it('shows the Copy all action for populated job fields', () => {
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: /copy all fields/i })).toBeInTheDocument();
  });

  it('generates and displays a checklist', async () => {
    server.use(
      http.post('/api/jobs/:jobId/checklists', () =>
        HttpResponse.json({
          checklists_md: '# Review\n- [ ] Add tests',
          checklists_generated_at: '2026-08-11T12:00:00Z',
        }),
      ),
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Run Checklists' }));
    await waitFor(() => expect(screen.getByText(/Add tests/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'Regenerate' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy checklist' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download checklist' })).toBeInTheDocument();
  });
  it('captures screenshots and shows the Drive link on reload', async () => {
    const reload = vi.fn().mockResolvedValue(undefined);
    setupMocks({ reload });
    server.use(
      http.post('/api/jobs/:jobId/screenshots', () =>
        HttpResponse.json({ screenshots_status: 'generating' }),
      ),
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it('shows the Open in Drive button and retry button once generated', () => {
    setupMocks({
      job: {
        ...JOB,
        screenshots_status: 'done',
        screenshots_drive_url: 'https://drive.google.com/drive/folders/abc',
      },
    });
    render(<JobDetailPage />);
    expect(
      screen.getByRole('link', { name: 'Open screenshots in Drive' }),
    ).toHaveAttribute('href', 'https://drive.google.com/drive/folders/abc');
    expect(
      screen.getByRole('button', { name: 'Retry screenshot capture' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Capture' })).toBeNull();
  });

  it('shows only the retry button (no Drive link) after a failed capture', () => {
    setupMocks({
      job: { ...JOB, screenshots_status: 'error' },
    });
    render(<JobDetailPage />);
    expect(
      screen.getByRole('button', { name: 'Retry screenshot capture' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'Open screenshots in Drive' }),
    ).toBeNull();
    expect(screen.queryByRole('button', { name: 'Capture' })).toBeNull();
  });

  it('disables Capture Screenshots for videos over the duration cap', () => {
    setupMocks({ job: { ...JOB, video_duration_seconds: 6000 } });
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Capture' })).toBeDisabled();
  });

  it('does not gate the button when duration is unknown', () => {
    setupMocks({ job: { ...JOB, video_duration_seconds: null } });
    render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Capture' })).toBeEnabled();
  });

  it('shows an error message when screenshot capture fails to start', async () => {
    setupMocks();
    server.use(
      http.post('/api/jobs/:jobId/screenshots', () =>
        HttpResponse.json({ detail: 'Screenshot capture is already running' }, { status: 409 }),
      ),
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Capture' }));
    await waitFor(() =>
      expect(screen.getByText('Screenshot capture is already running')).toBeInTheDocument(),
    );
  });

  it('shows loading skeleton when fetchState is loading', () => {
    setupMocks({ fetchState: 'loading', job: null });
    render(<JobDetailPage />);
    expect(document.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows not found when fetchState is not_found', () => {
    setupMocks({ fetchState: 'not_found', job: null });
    render(<JobDetailPage />);
    expect(screen.getByText(/job not found/i)).toBeTruthy();
  });

  it('shows forbidden message when fetchState is forbidden', () => {
    setupMocks({ fetchState: 'forbidden', job: null });
    render(<JobDetailPage />);
    expect(screen.getByText(/access denied/i)).toBeTruthy();
  });

  it('shows error message when fetchState is error', () => {
    setupMocks({ fetchState: 'error', job: null });
    render(<JobDetailPage />);
    expect(screen.getByText(/failed to load job/i)).toBeTruthy();
  });

  it('renders job title when loaded', () => {
    render(<JobDetailPage />);
    expect(screen.getByText('My Awesome Video')).toBeTruthy();
  });

  it('edits and saves the job title, prefilled with the current title', async () => {
    const setData = vi.fn();
    setupMocks({ setData });
    let putBody: unknown;
    server.use(
      http.put('/api/jobs/:jobId/title', async ({ request }) => {
        putBody = await request.json();
        return HttpResponse.json({ title: 'New Title' });
      }),
    );
    render(<JobDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Edit title' }));
    const input = screen.getByLabelText('Job title') as HTMLInputElement;
    expect(input.value).toBe('My Awesome Video');

    fireEvent.change(input, { target: { value: 'New Title' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => expect(putBody).toEqual({ title: 'New Title' }));
    expect(setData).toHaveBeenCalledTimes(1);
    const updater = setData.mock.calls[0][0] as (prev: JobDetail) => JobDetail;
    expect(updater(JOB).title).toBe('New Title');
  });

  it('prefills the title field with the URL fallback when no title is set', () => {
    setupMocks({ job: { ...JOB, title: null } });
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Edit title' }));
    const input = screen.getByLabelText('Job title') as HTMLInputElement;
    expect(input.value).toBe('https://www.youtube.com/watch?v=test123');
  });

  it('cancels the title edit on Escape without saving', () => {
    setupMocks();
    render(<JobDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Edit title' }));
    const input = screen.getByLabelText('Job title') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'Discard me' } });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(screen.queryByLabelText('Job title')).toBeNull();
    expect(screen.getByText('My Awesome Video')).toBeTruthy();
  });

  it('deletes after confirmation and navigates back', async () => {
    let deletedPath = '';
    server.use(
      http.delete('/api/jobs/:jobId', ({ request }) => {
        deletedPath = new URL(request.url).pathname;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    window.history.pushState({}, '', '/feed');
    window.history.pushState({}, '', '/jobs/j1');
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => {
      expect(deletedPath).toBe('/api/jobs/j1');
      expect(routerBack).toHaveBeenCalledOnce();
    });
  });

  it('returns to the browser history entry for Back', async () => {
    window.history.pushState({}, '', '/brain?q=video');
    window.history.pushState({}, '', '/jobs/j1');
    render(<JobDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: /^back$/i }));

    expect(routerBack).toHaveBeenCalledOnce();
    expect(routerPush).not.toHaveBeenCalled();
  });

  it('falls back to the scoped feed URL when opened directly', () => {
    const historyLengthSpy = vi.spyOn(window.history, 'length', 'get').mockReturnValue(1);
    searchParams = new URLSearchParams('content_type=article&status=done');
    render(<JobDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: /^back$/i }));

    expect(routerBack).not.toHaveBeenCalled();
    expect(routerPush).toHaveBeenCalledWith('/feed?content_type=article&status=done');

    historyLengthSpy.mockRestore();
  });

  it('has no with-links checkbox when the job added no links', () => {
    setupMocks({ job: { ...JOB, link_count: 0 } });
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    expect(screen.queryByRole('checkbox')).toBeNull();
  });

  it('deletes with ?with_links=1 only when the checkbox is checked (ADR-0046)', async () => {
    setupMocks({ job: { ...JOB, link_count: 3 } });
    let deletedSearch = '';
    server.use(
      http.delete('/api/jobs/:jobId', ({ request }) => {
        deletedSearch = new URL(request.url).search;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    expect(screen.getByText(/also remove the 3 links/i)).toBeTruthy();
    fireEvent.click(screen.getByRole('checkbox'));
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => expect(deletedSearch).toBe('?with_links=1'));
  });

  it('shows the inline failure and closes the dialog', async () => {
    server.use(
      http.delete('/api/jobs/:jobId', () => new HttpResponse(null, { status: 500 })),
    );
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => expect(screen.getByText(/couldn't delete/i)).toBeInTheDocument());
    expect(screen.queryByText('Permanently delete this job?')).toBeNull();
  });

  it('hides the delete zone in restricted mode', () => {
    mockUseRestrictedMode.mockReturnValue({ restricted: true, showRestrictedToast: vi.fn() });
    render(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Delete job' })).toBeNull();
  });

  it('renders content type and status badges', () => {
    render(<JobDetailPage />);
    expect(screen.getByText('long')).toBeTruthy();
    expect(screen.getByText('done')).toBeTruthy();
  });

  it('renders job URL', () => {
    render(<JobDetailPage />);
    expect(screen.getByText('https://www.youtube.com/watch?v=test123')).toBeTruthy();
  });

  it('renders Open in Drive link', () => {
    render(<JobDetailPage />);
    expect(screen.getByText(/open in drive/i)).toBeTruthy();
  });

  it('renders enrichment field labels', () => {
    render(<JobDetailPage />);
    expect(screen.getByText('Title | Topic')).toBeTruthy();
    expect(screen.getByText('Objective')).toBeTruthy();
  });

  it('renders enrichment field values', () => {
    render(<JobDetailPage />);
    expect(screen.getByText(/Machine Learning/)).toBeTruthy();
    expect(screen.getByText('Learn ML basics')).toBeTruthy();
  });

  it('merges title and topic into one field, omitting a standalone Topic card', () => {
    render(<JobDetailPage />);
    expect(screen.queryByText('Topic')).toBeNull();
    const merged = screen.getByText('Title | Topic').closest('div')?.parentElement;
    expect(merged?.textContent).toContain('My Awesome Video');
    expect(merged?.textContent).toContain('Machine Learning');
  });

  it('renders a capped transcript preview for a long-video job with a transcript', () => {
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    render(<JobDetailPage />);
    expect(screen.getByText('Transcript')).toBeInTheDocument();
    expect(screen.getByText('Full long-video transcript')).toBeInTheDocument();
    // Editing lives on its own page now - the card never mounts the editor.
    expect(screen.queryByTestId('dynamic-component')).toBeNull();
  });

  // Separate mounts (not rerenders of one instance) — each represents a
  // different job navigated to fresh, not a live update of the same job.
  it('omits the transcript card for an article job with no transcript', () => {
    setupMocks({ job: { ...JOB, content_type: 'article', transcript: null } });
    render(<JobDetailPage />);
    expect(screen.queryByText('Transcript')).toBeNull();
  });

  it('omits the transcript card for a repo job with no transcript', () => {
    setupMocks({ job: { ...JOB, content_type: 'repo', transcript: null } });
    render(<JobDetailPage />);
    expect(screen.queryByText('Transcript')).toBeNull();
  });

  it('renders an Open transcript in Drive link on the transcript card when transcript_drive_url is set', () => {
    setupMocks({
      job: {
        ...JOB,
        transcript: 'Full long-video transcript',
        transcript_drive_url: 'https://drive.google.com/file/d/transcript-doc',
      },
    });
    render(<JobDetailPage />);
    const link = screen.getByRole('link', { name: /open transcript in drive/i });
    expect(link).toHaveAttribute('href', 'https://drive.google.com/file/d/transcript-doc');
  });

  it('omits the transcript card Drive link when transcript_drive_url is not set', () => {
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript', transcript_drive_url: null } });
    render(<JobDetailPage />);
    expect(screen.queryByRole('link', { name: /open transcript in drive/i })).toBeNull();
  });

  it('copy and download buttons reflect the transcript text', async () => {
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    let downloadedBlob: Blob | undefined;
    vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      downloadedBlob = blob as Blob;
      return 'blob:download';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);

    render(<JobDetailPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Copy transcript' }));
    await waitFor(() =>
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith('Full long-video transcript'),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Download transcript' }));
    await waitFor(() => expect(downloadedBlob).toBeDefined());
    const downloadedText = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsText(downloadedBlob!);
    });
    expect(downloadedText).toBe('Full long-video transcript');
  });

  it('links the Edit transcript button to the standalone transcript edit page', () => {
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    render(<JobDetailPage />);
    const link = screen.getByRole('link', { name: 'Edit transcript' });
    expect(link).toHaveAttribute('href', '/jobs/j1/transcript');
  });

  it('carries the active job-list filter scope onto the Edit transcript link', () => {
    searchParams = new URLSearchParams('content_type=long&status=done');
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    render(<JobDetailPage />);
    const link = screen.getByRole('link', { name: 'Edit transcript' });
    expect(link).toHaveAttribute(
      'href',
      '/jobs/j1/transcript?content_type=long&status=done',
    );
  });

  it('hides the Edit transcript button in Restricted mode', () => {
    mockUseRestrictedMode.mockReturnValue({ restricted: true, showRestrictedToast: vi.fn() });
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    render(<JobDetailPage />);
    expect(screen.getByText('Full long-video transcript')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Edit transcript' })).toBeNull();
  });

  it('shows the transcript card once a transcript arrives via a later refetch', () => {
    // A long job can mount with transcript still null and only get its real
    // transcript later via the 'enriching' status poll refetching job data —
    // same job.id, no remount.
    setupMocks({ job: { ...JOB, transcript: null } });
    const { rerender } = render(<JobDetailPage />);
    expect(screen.queryByText('Transcript')).toBeNull();

    setupMocks({ job: { ...JOB, transcript: 'Arrived later' } });
    rerender(<JobDetailPage />);
    expect(screen.getByText('Arrived later')).toBeInTheDocument();
  });

  it('shows Run Gemini only for unrestricted transcript-complete long jobs', () => {
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    const { rerender } = render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Enrich' })).toBeInTheDocument();
    setupMocks({ job: { ...JOB, status: 'done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Enrich' })).toBeNull();
    setupMocks({ job: { ...JOB, content_type: 'article', status: 'transcript_done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Enrich' })).toBeNull();
    mockUseRestrictedMode.mockReturnValue({ restricted: true, showRestrictedToast: vi.fn() });
    setupMocks({ job: { ...JOB, status: 'transcript_done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Enrich' })).toBeNull();
  });

  it('submits a named recipe and optimistically marks the job enriching', async () => {
    const reload = vi.fn().mockResolvedValue(undefined);
    mockUseJobDetail.mockImplementation(() => {
      const [job, setData] = useState<JobDetail>({
        ...JOB,
        status: 'transcript_done',
      } as JobDetail);
      return { job, setData, fetchState: 'ok', reload };
    });
    let body: unknown;
    server.use(http.get('/api/templates', () => HttpResponse.json([])), http.post('/api/jobs/:id/enrich', async ({ request }) => { body = await request.json(); return HttpResponse.json({ status: 'enriching' }, { status: 202 }); }));
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Enrich' }));
    fireEvent.click(screen.getByRole('button', { name: 'summary' }));
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Enrich' })).toBeNull();
      expect(screen.queryByTestId('gemini-accordion')).toBeNull();
    });
    expect(body).toEqual({ template: 'summary', freestyle_prompt: null });
  });

  it('requires Freestyle text and surfaces an API error inline, with an error haptic', async () => {
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: vibrate });
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    let resolveSettings!: () => void;
    const settingsDeferred = new Promise<void>((resolve) => {
      resolveSettings = resolve;
    });
    server.use(
      http.get('/api/templates', () => HttpResponse.json([])),
      http.post('/api/jobs/:id/enrich', () => HttpResponse.json({ detail: 'Already claimed' }, { status: 409 })),
      http.get('/api/controls/accessibility-settings', async () => {
        await settingsDeferred;
        return HttpResponse.json({ visual_motion: true, haptic_motion: true });
      }),
    );
    const settings = renderHook(() => useAccessibilitySettings());
    render(<JobDetailPage />);
    // Resolve the accessibility-settings GET (fired on mount) and wait for
    // useHapticFeedback's readiness gate to open before interacting, rather
    // than a fixed delay that only happens to outrun the real timing.
    await act(async () => {
      resolveSettings();
    });
    await waitFor(() => expect(settings.result.current.loaded).toBe(true));
    fireEvent.click(screen.getByRole('button', { name: 'Enrich' }));
    fireEvent.click(screen.getByRole('button', { name: 'Freestyle' }));
    const submit = screen.getByRole('button', { name: 'Run Freestyle' });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Freestyle instructions'), { target: { value: 'Find risks' } });
    fireEvent.click(submit);
    expect(await screen.findByRole('alert')).toHaveTextContent('Already claimed');
    await waitFor(() => expect(vibrate).toHaveBeenCalledWith([40, 30, 40]));
    Reflect.deleteProperty(navigator, 'vibrate');
  });

  it('uses the desktop slide panel with built-in descriptions', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    const builtins = [
      ['summary', 'A concise overview'],
      ['method', 'A step-by-step method'],
      ['technical', 'A technical deep dive'],
      ['review', 'A critical review'],
      ['narrative', 'A narrative retelling'],
    ].map(([name, description], index) => ({ id: String(index), name, description, extra_instructions: '', is_builtin: true }));
    server.use(http.get('/api/templates', () => HttpResponse.json([...builtins, { id: 'custom', name: 'custom', description: 'Hidden', extra_instructions: '', is_builtin: false }])));
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Enrich' }));
    expect(await screen.findByTestId('gemini-slide-panel')).toBeInTheDocument();
    expect(screen.getByTestId('gemini-slide-panel')).not.toHaveAttribute('inert');
    for (const [, description] of builtins.map(({ name, description }) => [name, description])) {
      expect(await screen.findByText(description)).toBeInTheDocument();
    }
    expect(screen.queryByText('Hidden')).toBeNull();
    expect(screen.queryByTestId('gemini-accordion')).toBeNull();
  });

  it('removes the closed desktop panel from keyboard navigation', async () => {
    const user = userEvent.setup();
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    server.use(http.get('/api/templates', () => HttpResponse.json([])));
    render(<JobDetailPage />);
    const panel = await screen.findByTestId('gemini-slide-panel');
    const runGemini = screen.getByRole('button', { name: 'Enrich' });
    runGemini.focus();

    expect(panel).toHaveAttribute('inert');
    await user.tab();
    expect(screen.getByRole('button', { name: 'Run Checklists' })).toHaveFocus();
  });

  it('keeps the inline accordion on narrow viewports', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    server.use(http.get('/api/templates', () => HttpResponse.json([])));
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Enrich' }));
    expect(await screen.findByTestId('gemini-accordion')).toBeInTheDocument();
    expect(screen.queryByTestId('gemini-slide-panel')).toBeNull();
  });

  it('polls with reload only while enrichment is in flight and cancels afterward', async () => {
    const reload = vi.fn().mockResolvedValue(undefined);
    const cancel = vi.fn();
    mockStartPolling.mockReturnValue(cancel);
    setupMocks({ job: { ...JOB, status: 'done' } });
    const { rerender } = render(<JobDetailPage />);
    expect(mockStartPolling).not.toHaveBeenCalled();
    setupMocks({ job: { ...JOB, status: 'enriching' }, reload });
    rerender(<JobDetailPage />);
    expect(mockStartPolling).toHaveBeenCalledWith(expect.any(Function), expect.any(Function), 10_000);
    const fetchJob = mockStartPolling.mock.calls[0][0];
    const isIdle = mockStartPolling.mock.calls[0][1];
    expect(isIdle()).toBe(false);
    await fetchJob();
    expect(reload).toHaveBeenCalledOnce();
    setupMocks({ job: { ...JOB, status: 'done' } });
    rerender(<JobDetailPage />);
    expect(cancel).toHaveBeenCalledOnce();
    expect(isIdle()).toBe(true);
  });

  it('shows error block when status is error', () => {
    setupMocks({
      job: { ...JOB, status: 'error', error_msg: 'Processing failed' },
    });
    render(<JobDetailPage />);
    expect(screen.getByText('Processing failed')).toBeTruthy();
  });

  it('renders tag menu and chips', () => {
    render(<JobDetailPage />);
    expect(screen.getByTestId('tag-menu')).toBeTruthy();
    expect(screen.getByTestId('tag-chips')).toBeTruthy();
  });

  it('renders MarkdownEditor when annotation is loaded', () => {
    setupMocks({}, { loaded: true, annotation: { notes: 'My notes', updated_at: null } });
    render(<JobDetailPage />);
    // MarkdownEditor is dynamic - mocked as dynamic component
    expect(screen.getByTestId('dynamic-component')).toBeTruthy();
  });

  it('uses URL as title when title is null', () => {
    setupMocks({ job: { ...JOB, title: null } });
    render(<JobDetailPage />);
    expect(screen.getAllByText('https://www.youtube.com/watch?v=test123').length).toBeGreaterThan(0);
  });

  it('renders template_analysis with JSON content', () => {
    const jsonAnalysis = JSON.stringify({ key_insight: 'This is valuable', action: 'Do something' });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('Template Analysis')).toBeTruthy();
  });

  it('renders template_analysis with invalid JSON as plain text', () => {
    setupMocks({ job: { ...JOB, template_analysis: 'not json text' } });
    render(<JobDetailPage />);
    expect(screen.getByText('not json text')).toBeTruthy();
  });

  it('does not render drive link when drive_url is null', () => {
    setupMocks({ job: { ...JOB, drive_url: null } });
    render(<JobDetailPage />);
    expect(screen.queryByText(/open in drive/i)).toBeNull();
  });

  it('renders template_analysis with nested object JSON', () => {
    const jsonAnalysis = JSON.stringify({
      overview: 'Great video',
      details: { author: 'John', year: 2024 },
      tags: ['AI', 'ML', 'Deep Learning'],
    });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('Template Analysis')).toBeTruthy();
    expect(screen.getByText('Overview')).toBeTruthy();
    expect(screen.getByText('Great video')).toBeTruthy();
  });

  it('renders template_analysis with all-scalar array', () => {
    const jsonAnalysis = JSON.stringify({ points: ['Point 1', 'Point 2', 'Point 3'] });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('Point 1')).toBeTruthy();
    expect(screen.getByText('Point 2')).toBeTruthy();
  });

  it('renders template_analysis with array of objects', () => {
    const jsonAnalysis = JSON.stringify({ steps: [{ name: 'Step 1', desc: 'Do this' }, { name: 'Step 2', desc: 'Do that' }] });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('Template Analysis')).toBeTruthy();
  });

  it('renders template_analysis with a top-level number value', () => {
    const jsonAnalysis = JSON.stringify({ score: 9.5, label: 'Excellent' });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('9.5')).toBeTruthy();
    expect(screen.getByText('Excellent')).toBeTruthy();
  });

  it('renders template_analysis with top-level array JSON', () => {
    const jsonAnalysis = JSON.stringify(['item1', 'item2', 'item3']);
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('item1')).toBeTruthy();
  });

  it('renders template_analysis with boolean values', () => {
    const jsonAnalysis = JSON.stringify({ is_recommended: true, reviewed: false });
    setupMocks({ job: { ...JOB, template_analysis: jsonAnalysis } });
    render(<JobDetailPage />);
    expect(screen.getByText('true')).toBeTruthy();
  });
});
