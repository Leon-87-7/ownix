// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { ContextTab } from './ContextTab';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 's1' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/spaces/s1',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useSpaceContext', () => ({
  useSpaceContext: vi.fn(),
}));

// Mock next/dynamic to avoid dynamic import issues in tests
vi.mock('next/dynamic', () => ({
  default: () => {
    const Component = () => <div data-testid="markdown-editor">MarkdownEditor</div>;
    return Component;
  },
}));

import { useSpaceContext } from '@/lib/hooks/useSpaceContext';
const mockUseSpaceContext = vi.mocked(useSpaceContext);

const BLOBS = [
  { id: 'b1', space_id: 's1', name: 'Research Notes', content: 'Some notes', sort_order: 1, created_at: '', updated_at: '' },
  { id: 'b2', space_id: 's1', name: 'Summary', content: 'Summary content', sort_order: 2, created_at: '', updated_at: '' },
];

function setupMocks(overrides: Partial<ReturnType<typeof useSpaceContext>> = {}) {
  mockUseSpaceContext.mockReturnValue({
    blobs: BLOBS,
    loading: false,
    blobError: null,
    setBlobError: vi.fn(),
    addBlob: vi.fn(),
    updateBlob: vi.fn(),
    deleteBlob: vi.fn(),
    reorderBlob: vi.fn(),
    patchBlobName: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useSpaceContext>);
}

beforeEach(() => { setupMocks(); });

describe('ContextTab', () => {
  it('shows loading spinner when loading', () => {
    setupMocks({ loading: true, blobs: [] });
    render(<ContextTab spaceId="s1" />);
    expect(screen.getByText('Loading…')).toBeTruthy();
  });

  it('shows empty message when no blobs', () => {
    setupMocks({ blobs: [] });
    render(<ContextTab spaceId="s1" />);
    expect(screen.getByText(/no context documents yet/i)).toBeTruthy();
  });

  it('renders blob names when blobs exist', () => {
    render(<ContextTab spaceId="s1" />);
    // Blob names are in text inputs
    const inputs = screen.getAllByPlaceholderText('Context name') as HTMLInputElement[];
    expect(inputs.some(input => input.value === 'Research Notes')).toBe(true);
    expect(inputs.some(input => input.value === 'Summary')).toBe(true);
  });

  it('renders Remove buttons for each blob', () => {
    render(<ContextTab spaceId="s1" />);
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    expect(removeButtons).toHaveLength(2);
  });

  it('calls deleteBlob when Remove is clicked', () => {
    const deleteBlob = vi.fn();
    setupMocks({ deleteBlob });
    render(<ContextTab spaceId="s1" />);
    const removeButtons = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeButtons[0]);
    expect(deleteBlob).toHaveBeenCalledWith('b1');
  });

  it('renders Add context button', () => {
    render(<ContextTab spaceId="s1" />);
    expect(screen.getByRole('button', { name: /add context/i })).toBeTruthy();
  });

  it('renders move up/down buttons', () => {
    render(<ContextTab spaceId="s1" />);
    const upBtns = screen.getAllByRole('button', { name: /move up/i });
    const downBtns = screen.getAllByRole('button', { name: /move down/i });
    expect(upBtns.length).toBeGreaterThan(0);
    expect(downBtns.length).toBeGreaterThan(0);
  });

  it('shows blobError when set', () => {
    setupMocks({ blobError: 'Failed to save' });
    render(<ContextTab spaceId="s1" />);
    expect(screen.getByText('Failed to save')).toBeTruthy();
  });

  it('calls addBlob when Add context is clicked with default name', async () => {
    const addBlob = vi.fn(async () => {});
    setupMocks({ addBlob });
    render(<ContextTab spaceId="s1" />);

    const addBtn = screen.getByRole('button', { name: /add context/i });
    fireEvent.click(addBtn);

    await waitFor(() => expect(addBlob).toHaveBeenCalledWith('New context'));
  });

  it('calls addBlob with custom name when name is entered', async () => {
    const addBlob = vi.fn(async () => {});
    setupMocks({ addBlob });
    render(<ContextTab spaceId="s1" />);

    const nameInput = screen.getByPlaceholderText('Context document name…');
    fireEvent.change(nameInput, { target: { value: 'My Context' } });

    const addBtn = screen.getByRole('button', { name: /add context/i });
    fireEvent.click(addBtn);

    await waitFor(() => expect(addBlob).toHaveBeenCalledWith('My Context'));
  });

  it('calls reorderBlob when Move down is clicked', () => {
    const reorderBlob = vi.fn();
    setupMocks({ reorderBlob });
    render(<ContextTab spaceId="s1" />);
    const downBtns = screen.getAllByRole('button', { name: /move down/i });
    fireEvent.click(downBtns[0]);
    expect(reorderBlob).toHaveBeenCalledWith(0, 'down');
  });
});
