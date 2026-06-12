// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SpacesPage from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/spaces',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useSpaceList', () => ({
  useSpaceList: vi.fn(),
}));
vi.mock('@/lib/hooks/useCreateSpace', () => ({
  useCreateSpace: vi.fn(),
}));

import { useSpaceList } from '@/lib/hooks/useSpaceList';
import { useCreateSpace } from '@/lib/hooks/useCreateSpace';

const mockUseSpaceList = vi.mocked(useSpaceList);
const mockUseCreateSpace = vi.mocked(useCreateSpace);

const SPACES = [
  { id: 's1', name: 'Alpha Space', color: '#ff0000', chat_id: 1, created_at: '', updated_at: '' },
  { id: 's2', name: 'Beta Space', color: '#00ff00', chat_id: 1, created_at: '', updated_at: '' },
];

function setupMocks(
  spaceListOverrides: Partial<ReturnType<typeof useSpaceList>> = {},
  createSpaceOverrides: Partial<ReturnType<typeof useCreateSpace>> = {},
) {
  mockUseSpaceList.mockReturnValue({
    spaces: SPACES,
    loading: false,
    error: null,
    reload: vi.fn(),
    ...spaceListOverrides,
  } as ReturnType<typeof useSpaceList>);

  mockUseCreateSpace.mockReturnValue({
    showForm: false,
    openForm: vi.fn(),
    newName: '',
    setNewName: vi.fn(),
    newColor: '#6366f1',
    setNewColor: vi.fn(),
    submitting: false,
    formError: null,
    handleCreate: vi.fn(),
    resetForm: vi.fn(),
    ...createSpaceOverrides,
  } as ReturnType<typeof useCreateSpace>);
}

beforeEach(() => { setupMocks(); });

describe('SpacesPage', () => {
  it('renders Spaces heading', () => {
    render(<SpacesPage />);
    expect(screen.getByText('Spaces')).toBeTruthy();
  });

  it('shows loading spinner when loading', () => {
    setupMocks({ loading: true, spaces: [] });
    render(<SpacesPage />);
    expect(screen.getByText('Loading…')).toBeTruthy();
  });

  it('shows error message on error', () => {
    setupMocks({ error: 'Failed to load spaces', spaces: [] });
    render(<SpacesPage />);
    expect(screen.getByText('Failed to load spaces')).toBeTruthy();
  });

  it('renders space cards when spaces exist', () => {
    render(<SpacesPage />);
    expect(screen.getByText('Alpha Space')).toBeTruthy();
    expect(screen.getByText('Beta Space')).toBeTruthy();
  });

  it('shows empty message when no spaces and no form', () => {
    setupMocks({ spaces: [] });
    render(<SpacesPage />);
    expect(screen.getByText(/no spaces yet/i)).toBeTruthy();
  });

  it('shows New Space button', () => {
    render(<SpacesPage />);
    expect(screen.getByRole('button', { name: /new space/i })).toBeTruthy();
  });

  it('shows Cancel button when showForm is true', () => {
    setupMocks({}, { showForm: true });
    render(<SpacesPage />);
    // Both the "Cancel" toggle button and the form's "Cancel" button appear
    const cancelBtns = screen.getAllByRole('button', { name: /cancel/i });
    expect(cancelBtns.length).toBeGreaterThanOrEqual(1);
  });

  it('shows form when showForm is true', () => {
    setupMocks({}, { showForm: true });
    render(<SpacesPage />);
    expect(screen.getByText('Create Space')).toBeTruthy();
  });

  it('shows form error when formError is set', () => {
    setupMocks({}, { showForm: true, formError: 'A space with that name already exists.' });
    render(<SpacesPage />);
    expect(screen.getByText('A space with that name already exists.')).toBeTruthy();
  });

  it('shows submitting state on button', () => {
    setupMocks({}, { showForm: true, submitting: true });
    render(<SpacesPage />);
    expect(screen.getByText('Creating…')).toBeTruthy();
  });
});
