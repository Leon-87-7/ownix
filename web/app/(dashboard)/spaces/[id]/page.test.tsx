// @vitest-environment jsdom
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import SpaceDetailPage from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({ id: 's1' }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/spaces/s1',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useSpaceDetail', () => ({
  useSpaceDetail: vi.fn(),
}));
vi.mock('@/lib/hooks/useSpaceEdit', () => ({
  useSpaceEdit: vi.fn(),
}));
vi.mock('./UrlsTab', () => ({
  UrlsTab: () => <div data-testid="urls-tab">URLs Tab</div>,
}));
vi.mock('./ContextTab', () => ({
  ContextTab: () => <div data-testid="context-tab">Context Tab</div>,
}));
vi.mock('@/components/ExportModal', () => ({
  default: ({ onClose }: { onClose: () => void }) => (
    <div data-testid="export-modal"><button onClick={onClose}>Close Export</button></div>
  ),
}));

import { useSpaceDetail } from '@/lib/hooks/useSpaceDetail';
import { useSpaceEdit } from '@/lib/hooks/useSpaceEdit';

const mockUseSpaceDetail = vi.mocked(useSpaceDetail);
const mockUseSpaceEdit = vi.mocked(useSpaceEdit);

const SPACE = {
  id: 's1',
  chat_id: 1234,
  name: 'My Space',
  color: '#ff0000',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

function setupMocks(
  spaceDetailOverrides: Partial<ReturnType<typeof useSpaceDetail>> = {},
  spaceEditOverrides: Partial<ReturnType<typeof useSpaceEdit>> = {},
) {
  mockUseSpaceDetail.mockReturnValue({
    space: SPACE,
    setSpace: vi.fn(),
    fetchState: 'ok',
    ...spaceDetailOverrides,
  } as ReturnType<typeof useSpaceDetail>);

  mockUseSpaceEdit.mockReturnValue({
    editing: false,
    editName: SPACE.name,
    setEditName: vi.fn(),
    editColor: SPACE.color,
    setEditColor: vi.fn(),
    editError: null,
    editSaving: false,
    startEdit: vi.fn(),
    cancelEdit: vi.fn(),
    handleEditSave: vi.fn(),
    ...spaceEditOverrides,
  } as ReturnType<typeof useSpaceEdit>);
}

beforeEach(() => { setupMocks(); });

describe('SpaceDetailPage', () => {
  it('shows loading spinner when fetchState is loading', () => {
    setupMocks({ fetchState: 'loading', space: null });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('Loading…')).toBeTruthy();
  });

  it('shows not found message', () => {
    setupMocks({ fetchState: 'not_found', space: null });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText(/space not found/i)).toBeTruthy();
  });

  it('shows forbidden message', () => {
    setupMocks({ fetchState: 'forbidden', space: null });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText(/access denied/i)).toBeTruthy();
  });

  it('shows error message on error fetch state', () => {
    setupMocks({ fetchState: 'error', space: null });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText(/failed to load space/i)).toBeTruthy();
  });

  it('renders space name when loaded', () => {
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('My Space')).toBeTruthy();
  });

  it('renders tab buttons', () => {
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('URLs')).toBeTruthy();
    expect(screen.getByText('Context')).toBeTruthy();
  });

  it('renders URLs tab by default', () => {
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByTestId('urls-tab')).toBeTruthy();
  });

  it('renders Edit and Export and Delete buttons', () => {
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByRole('button', { name: /edit/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /export/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /delete/i })).toBeTruthy();
  });

  it('shows edit form when editing is true', () => {
    setupMocks({}, { editing: true });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('Edit Space')).toBeTruthy();
  });

  it('shows edit error when editError is set', () => {
    setupMocks({}, { editing: true, editError: 'A space with that name already exists.' });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('A space with that name already exists.')).toBeTruthy();
  });

  it('shows saving state in edit form', () => {
    setupMocks({}, { editing: true, editSaving: true });
    render(<SpaceDetailPage params={{ id: 's1' }} />);
    expect(screen.getByText('Saving…')).toBeTruthy();
  });
});
