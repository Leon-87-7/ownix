// @vitest-environment jsdom
import { render, screen, fireEvent } from '@/test/render';
import { describe, expect, it, vi, beforeEach } from 'vitest';
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
  it('renders Prompts heading', () => {
    render(<PromptsPage />);
    expect(screen.getByText('Prompts')).toBeTruthy();
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
    expect(screen.getByText(/built-in templates/i)).toBeTruthy();
  });

  it('renders user template section', () => {
    render(<PromptsPage />);
    expect(screen.getByText(/your templates/i)).toBeTruthy();
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
    expect(screen.getByText(/no built-in templates/i)).toBeTruthy();
  });

  it('shows no custom templates message when none', () => {
    setupMocks({ templates: [BUILTIN_TEMPLATE] });
    render(<PromptsPage />);
    expect(screen.getByText(/no custom templates yet/i)).toBeTruthy();
  });

  it('shows Create template form', () => {
    render(<PromptsPage />);
    // "Create template" appears as h4 heading and button label
    expect(screen.getAllByText('Create template').length).toBeGreaterThanOrEqual(1);
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
