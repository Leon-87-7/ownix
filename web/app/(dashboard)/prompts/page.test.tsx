// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@/test/render';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import PromptsPage from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/prompts',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useTemplateList', () => ({
  useTemplateList: vi.fn(),
}));

import { useTemplateList } from '@/lib/hooks/useTemplateList';
const mockUseTemplateList = vi.mocked(useTemplateList);

const BUILTIN_TEMPLATE = {
  id: 'b1',
  name: 'default',
  description: 'Default analysis',
  extra_instructions: '',
  is_builtin: true,
};
const USER_TEMPLATE = {
  id: 'u1',
  name: 'my-template',
  description: 'Custom template',
  extra_instructions: 'Focus on startups',
  is_builtin: false,
};

function setupMocks(overrides: Partial<ReturnType<typeof useTemplateList>> = {}) {
  mockUseTemplateList.mockReturnValue({
    templates: [BUILTIN_TEMPLATE, USER_TEMPLATE],
    loading: false,
    fetchError: null,
    createTemplate: vi.fn(),
    deleteTemplate: vi.fn(),
    updateTemplate: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useTemplateList>);
}

beforeEach(() => { setupMocks(); });

describe('PromptsPage', () => {
  it('renders Recipes heading', () => {
    render(<PromptsPage />);
    expect(screen.getByText('Recipes')).toBeTruthy();
  });

  it('shows loading message when loading', () => {
    setupMocks({ loading: true, templates: [] });
    render(<PromptsPage />);
    expect(screen.getByText(/loading templates/i)).toBeTruthy();
  });

  it('shows fetchError when present', () => {
    setupMocks({ fetchError: 'Failed to load', templates: [] });
    render(<PromptsPage />);
    expect(screen.getByText('Failed to load')).toBeTruthy();
  });

  it('renders built-in template section', () => {
    render(<PromptsPage />);
    expect(screen.getByText(/built-in recipes/i)).toBeTruthy();
  });

  it('renders user template section', () => {
    render(<PromptsPage />);
    expect(screen.getByText(/your recipes/i)).toBeTruthy();
  });

  it('renders built-in template name', () => {
    render(<PromptsPage />);
    expect(screen.getByText('/default')).toBeTruthy();
  });

  it('renders user template name', () => {
    render(<PromptsPage />);
    expect(screen.getByText('-my-template')).toBeTruthy();
  });

  it('shows built-in badge', () => {
    render(<PromptsPage />);
    expect(screen.getByText('built-in')).toBeTruthy();
  });

  it('shows no built-in templates message when none', () => {
    setupMocks({ templates: [USER_TEMPLATE] });
    render(<PromptsPage />);
    expect(screen.getByText(/no built-in recipes/i)).toBeTruthy();
  });

  it('shows no custom templates message when none', () => {
    setupMocks({ templates: [BUILTIN_TEMPLATE] });
    render(<PromptsPage />);
    expect(screen.getByText(/no custom recipes yet/i)).toBeTruthy();
  });

  it('shows Create recipe form', () => {
    render(<PromptsPage />);
    expect(screen.getByText('Create recipe')).toBeTruthy();
  });

  it('shows user template description', () => {
    render(<PromptsPage />);
    expect(screen.getByText('Custom template')).toBeTruthy();
  });

  it('shows Edit and Delete buttons for user templates', () => {
    render(<PromptsPage />);
    const editButtons = screen.getAllByRole('button', { name: /edit/i });
    const deleteButtons = screen.getAllByRole('button', { name: /delete/i });
    expect(editButtons.length).toBeGreaterThanOrEqual(1);
    expect(deleteButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('shows editing form when Edit is clicked', () => {
    render(<PromptsPage />);
    const editButton = screen.getAllByRole('button', { name: /edit/i })[0];
    fireEvent.click(editButton);
    expect(screen.getByText('Save')).toBeTruthy();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeTruthy();
  });

  it('returns to normal view after Cancel in edit mode', () => {
    render(<PromptsPage />);
    fireEvent.click(screen.getAllByRole('button', { name: /edit/i })[0]);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));
    expect(screen.getByText('-my-template')).toBeTruthy();
  });
});

// ApplyRecipeForm — covers the cloud-patch fix for the missing Recipes apply
// path (docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md Task 8).
describe('ApplyRecipeForm', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('posts the recipe name and pasted URL to /api/jobs', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 'job123', job_id: 'job123' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<PromptsPage />);

    const urlInput = screen.getByLabelText(/link to apply my-template/i);
    fireEvent.change(urlInput, {
      target: { value: 'https://example.com/x' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /apply to a link/i }),
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: 'https://example.com/x',
          template: 'my-template',
        }),
      });
    });
    expect(await screen.findByText('Link queued')).toBeTruthy();
    expect((urlInput as HTMLInputElement).value).toBe('');
  });

  it('shows the server error and keeps the URL when the request fails', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ detail: 'Unsupported URL' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<PromptsPage />);

    const urlInput = screen.getByLabelText(/link to apply my-template/i);
    fireEvent.change(urlInput, {
      target: { value: 'https://example.com/bad' },
    });
    fireEvent.click(
      screen.getByRole('button', { name: /apply to a link/i }),
    );

    expect(await screen.findByText('Unsupported URL')).toBeTruthy();
    expect((urlInput as HTMLInputElement).value).toBe(
      'https://example.com/bad',
    );
  });

  it('disables the submit button while the request is in flight', async () => {
    let resolveFetch: (value: unknown) => void = () => {};
    const fetchMock = vi.fn(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve;
        }),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<PromptsPage />);

    fireEvent.change(screen.getByLabelText(/link to apply my-template/i), {
      target: { value: 'https://example.com/x' },
    });
    const submitButton = screen.getByRole('button', {
      name: /apply to a link/i,
    });
    fireEvent.click(submitButton);

    expect(
      await screen.findByRole('button', { name: /applying/i }),
    ).toBeDisabled();

    resolveFetch({ ok: true, json: async () => ({ id: 'job123' }) });
    await waitFor(() => {
      expect(screen.getByText('Link queued')).toBeTruthy();
    });
  });
});
