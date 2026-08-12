// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import JobDetailPage from './page';

const routerBack = vi.fn();
const routerPush = vi.fn();
const server = setupServer();

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

const mockUseJobDetail = vi.mocked(useJobDetail);
const mockUseJobAnnotation = vi.mocked(useJobAnnotation);
const mockUseJobTags = vi.mocked(useJobTags);
const mockUseRestrictedMode = vi.mocked(useRestrictedMode);

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
    expect(screen.getByRole('button', { name: 'Download .md' })).toBeInTheDocument();
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
