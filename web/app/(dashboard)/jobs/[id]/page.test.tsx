// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import JobDetailPage from './page';

const routerBack = vi.fn();
const routerPush = vi.fn();

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
  setupMocks();
  mockUseRestrictedMode.mockReturnValue({ restricted: false, showRestrictedToast: vi.fn() });
  routerBack.mockReset();
  routerPush.mockReset();
  vi.unstubAllGlobals();
});

describe('CopyButton', () => {
  it('does not warn about setState after unmount when copy timer is pending', async () => {
    const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });

    // CopyButton is page-local (Next.js forbids extra page exports); reach it through the page.
    const { unmount } = render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: /copy all/i }));
    await waitFor(() => expect(screen.getByText('Copied!')).toBeInTheDocument());

    unmount();
    await new Promise((r) => setTimeout(r, 1600));

    expect(errorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
    errorSpy.mockRestore();
  });
});

describe('JobDetailPage', () => {
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
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);
    window.history.pushState({}, '', '/feed');
    window.history.pushState({}, '', '/jobs/j1');
    render(<JobDetailPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Delete job' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete permanently' }));
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/jobs/j1', { method: 'DELETE' });
      expect(routerBack).toHaveBeenCalledOnce();
    });
  });

  it('shows the inline failure and closes the dialog', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));
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
