// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { useState } from 'react';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import JobDetailPage from './page';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

const routerBack = vi.fn();
const routerPush = vi.fn();
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
  useSearchParams: () => new URLSearchParams(),
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
// next/dynamic calls are resolved; mock the dynamic import target directly
vi.mock('next/dynamic', () => ({
  default: (fn: () => Promise<{ default: React.ComponentType }>) => {
    const Component = () => <div data-testid="dynamic-component">Dynamic Component</div>;
    return Component;
  },
}));

import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobAnnotation } from '@/lib/hooks/useJobAnnotation';
import { useJobTags } from '@/lib/hooks/useJobTags';
import { useRestrictedMode } from '@/lib/restricted/context';
import { startPolling } from '@/lib/polling';

const mockUseJobDetail = vi.mocked(useJobDetail);
const mockUseJobAnnotation = vi.mocked(useJobAnnotation);
const mockUseJobTags = vi.mocked(useJobTags);
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
}

beforeEach(() => {
  server.resetHandlers();
  setupMocks();
  mockUseRestrictedMode.mockReturnValue({ restricted: false, showRestrictedToast: vi.fn() });
  routerBack.mockReset();
  routerPush.mockReset();
  vi.unstubAllGlobals();
  mockStartPolling.mockReset();
  mockStartPolling.mockReturnValue(vi.fn());
});

describe('JobDetailPage', () => {
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
    expect(screen.getByText('Topic')).toBeTruthy();
    expect(screen.getByText('Objective')).toBeTruthy();
  });

  it('renders enrichment field values', () => {
    render(<JobDetailPage />);
    expect(screen.getByText('Machine Learning')).toBeTruthy();
    expect(screen.getByText('Learn ML basics')).toBeTruthy();
  });

  it('renders a long transcript but omits empty article and repo transcripts', () => {
    setupMocks({ job: { ...JOB, transcript: 'Full long-video transcript' } });
    const { rerender } = render(<JobDetailPage />);
    expect(screen.getByText('Transcript')).toBeInTheDocument();
    expect(screen.getByText('Full long-video transcript')).toBeInTheDocument();
    setupMocks({ job: { ...JOB, content_type: 'article', transcript: null } });
    rerender(<JobDetailPage />);
    expect(screen.queryByText('Transcript')).toBeNull();
    setupMocks({ job: { ...JOB, content_type: 'repo', transcript: null } });
    rerender(<JobDetailPage />);
    expect(screen.queryByText('Transcript')).toBeNull();
  });

  it('shows Run Gemini only for unrestricted transcript-complete long jobs', () => {
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    const { rerender } = render(<JobDetailPage />);
    expect(screen.getByRole('button', { name: 'Run Gemini' })).toBeInTheDocument();
    setupMocks({ job: { ...JOB, status: 'done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Run Gemini' })).toBeNull();
    setupMocks({ job: { ...JOB, content_type: 'article', status: 'transcript_done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Run Gemini' })).toBeNull();
    mockUseRestrictedMode.mockReturnValue({ restricted: true, showRestrictedToast: vi.fn() });
    setupMocks({ job: { ...JOB, status: 'transcript_done' } }); rerender(<JobDetailPage />);
    expect(screen.queryByRole('button', { name: 'Run Gemini' })).toBeNull();
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Gemini' }));
    fireEvent.click(screen.getByRole('button', { name: 'summary' }));
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Run Gemini' })).toBeNull();
      expect(screen.queryByTestId('gemini-accordion')).toBeNull();
    });
    expect(body).toEqual({ template: 'summary', freestyle_prompt: null });
  });

  it('requires Freestyle text and surfaces an API error inline', async () => {
    setupMocks({ job: { ...JOB, status: 'transcript_done' } });
    server.use(http.get('/api/templates', () => HttpResponse.json([])), http.post('/api/jobs/:id/enrich', () => HttpResponse.json({ detail: 'Already claimed' }, { status: 409 })));
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Run Gemini' }));
    fireEvent.click(screen.getByRole('button', { name: 'Freestyle' }));
    const submit = screen.getByRole('button', { name: 'Run Freestyle' });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Freestyle instructions'), { target: { value: 'Find risks' } });
    fireEvent.click(submit);
    expect(await screen.findByRole('alert')).toHaveTextContent('Already claimed');
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Gemini' }));
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
    const runGemini = screen.getByRole('button', { name: 'Run Gemini' });
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
    fireEvent.click(screen.getByRole('button', { name: 'Run Gemini' }));
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
