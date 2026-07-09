// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import ControlsPage from './page';

vi.mock('next/navigation', () => ({
  useParams: () => ({}),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
  usePathname: () => '/controls',
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock('@/lib/hooks/useTagList', () => ({
  useTagList: vi.fn(),
}));
vi.mock('@/lib/hooks/useDomainList', () => ({
  useDomainList: vi.fn(),
}));

import { useTagList } from '@/lib/hooks/useTagList';
import { useDomainList } from '@/lib/hooks/useDomainList';

const mockUseTagList = vi.mocked(useTagList);
const mockUseDomainList = vi.mocked(useDomainList);

const TAGS = [
  { id: 't1', name: 'Alpha', meaning: 'first', color: '#ff0000' },
  { id: 't2', name: 'Beta', meaning: '', color: '#00ff00' },
];
const DOMAINS = ['example.com', 'test.org'];

function setupTagsMock(overrides: Partial<ReturnType<typeof useTagList>> = {}) {
  mockUseTagList.mockReturnValue({
    tags: TAGS,
    loading: false,
    fetchError: null,
    createTag: vi.fn(),
    deleteTag: vi.fn(),
    updateTag: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useTagList>);
}

function setupDomainsMock(overrides: Partial<ReturnType<typeof useDomainList>> = {}) {
  mockUseDomainList.mockReturnValue({
    domains: DOMAINS,
    loading: false,
    fetchError: null,
    addDomain: vi.fn(),
    removeDomain: vi.fn(),
    ...overrides,
  } as ReturnType<typeof useDomainList>);
}

beforeEach(() => {
  setupTagsMock();
  setupDomainsMock();
  vi.stubGlobal('fetch', vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
    if (init?.method === 'PUT') {
      return new Response(JSON.stringify({ telegram_notifications: false }), { status: 200 });
    }
    return new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 });
  }));
});

// Each section is a native <details>; all mount at once, so scope queries to
// the relevant section to avoid cross-section duplicates.
function section(title: string) {
  return within(screen.getByText(title).closest('details') as HTMLElement);
}

// Allowed/Ignored share one "Domains" section; scope by the column heading.
function domainColumn(name: 'Allowed' | 'Ignored') {
  return within(screen.getByRole('heading', { name }).closest('div') as HTMLElement);
}

describe('ControlsPage', () => {
  it('renders Settings heading', () => {
    render(<ControlsPage />);
    expect(screen.getByText('Settings')).toBeTruthy();
  });

  it('renders section headers', () => {
    render(<ControlsPage />);
    expect(screen.getByText('Tags')).toBeTruthy();
    expect(screen.getByText('Domains')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Allowed' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Ignored' })).toBeTruthy();
  });

  it('shows Tags section content', () => {
    render(<ControlsPage />);
    expect(section('Tags').getByText('Create tag')).toBeTruthy();
  });

  it('renders tag list', () => {
    render(<ControlsPage />);
    expect(section('Tags').getByText('Alpha')).toBeTruthy();
    expect(section('Tags').getByText('Beta')).toBeTruthy();
  });

  it('shows loading state in TagsTab', () => {
    setupTagsMock({ loading: true, tags: [] });
    render(<ControlsPage />);
    expect(section('Tags').getByText(/loading tags/i)).toBeTruthy();
  });

  it('shows fetchError in TagsTab', () => {
    setupTagsMock({ fetchError: 'Failed to load tags', tags: [] });
    render(<ControlsPage />);
    expect(section('Tags').getByText('Failed to load tags')).toBeTruthy();
  });

  it('shows empty message when no tags', () => {
    setupTagsMock({ tags: [] });
    render(<ControlsPage />);
    expect(section('Tags').getByText(/no tags yet/i)).toBeTruthy();
  });

  it('shows Allowed Domains content', () => {
    render(<ControlsPage />);
    const allowed = domainColumn('Allowed');
    expect(allowed.getByText('Add domain')).toBeTruthy();
    expect(allowed.getByText('example.com')).toBeTruthy();
  });

  it('shows domains in DomainTab', () => {
    render(<ControlsPage />);
    expect(domainColumn('Allowed').getByText('test.org')).toBeTruthy();
  });

  it('shows loading state in DomainTab', () => {
    setupDomainsMock({ loading: true, domains: [] });
    render(<ControlsPage />);
    expect(domainColumn('Allowed').getByText(/loading allowed domains/i)).toBeTruthy();
  });

  it('shows fetchError in DomainTab', () => {
    setupDomainsMock({ fetchError: 'Network error', domains: [] });
    render(<ControlsPage />);
    expect(domainColumn('Allowed').getByText('Network error')).toBeTruthy();
  });

  it('shows empty message in DomainTab when no domains', () => {
    setupDomainsMock({ domains: [] });
    render(<ControlsPage />);
    expect(domainColumn('Allowed').getByText(/no allowed domains yet/i)).toBeTruthy();
  });

  it('renders Ignored Domains content', () => {
    render(<ControlsPage />);
    expect(domainColumn('Ignored').getByText('Add domain')).toBeTruthy();
  });

  it('calls addDomain on form submit in DomainTab', async () => {
    const addDomain = vi.fn(async () => {});
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    const input = domainColumn('Allowed').getByPlaceholderText('example.com');
    fireEvent.change(input, { target: { value: 'newdomain.com' } });
    fireEvent.submit(input.closest('form')!);
    await new Promise(r => setTimeout(r, 10));
    expect(addDomain).toHaveBeenCalledWith('newdomain.com');
  });

  it('does not call addDomain when input is blank', async () => {
    const addDomain = vi.fn(async () => {});
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    const input = domainColumn('Allowed').getByPlaceholderText('example.com');
    // leave blank
    fireEvent.submit(input.closest('form')!);
    await new Promise(r => setTimeout(r, 10));
    expect(addDomain).not.toHaveBeenCalled();
  });

  it('calls removeDomain when Remove is clicked in DomainTab', async () => {
    const removeDomain = vi.fn(async () => {});
    setupDomainsMock({ removeDomain });
    render(<ControlsPage />);
    const removeBtns = domainColumn('Allowed').getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeBtns[0]);
    await new Promise(r => setTimeout(r, 10));
    expect(removeDomain).toHaveBeenCalledWith('example.com');
  });

  it('shows addError when addDomain rejects', async () => {
    const addDomain = vi.fn(async () => { throw new Error('Duplicate domain'); });
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    const input = domainColumn('Allowed').getByPlaceholderText('example.com');
    fireEvent.change(input, { target: { value: 'dup.com' } });
    fireEvent.submit(input.closest('form')!);
    await waitFor(() => expect(domainColumn('Allowed').getByText('Duplicate domain')).toBeTruthy());
  });

  it('shows removeError when removeDomain rejects', async () => {
    const removeDomain = vi.fn(async () => { throw new Error('Remove failed'); });
    setupDomainsMock({ removeDomain });
    render(<ControlsPage />);
    const removeBtns = domainColumn('Allowed').getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeBtns[0]);
    await waitFor(() => expect(domainColumn('Allowed').getByText('Remove failed')).toBeTruthy());
  });

  it('shows the recovery Telegram notification preference', async () => {
    render(<ControlsPage />);
    const checkbox = await screen.findByRole('checkbox', {
      name: /feed recovery telegram notifications/i,
    });
    expect(checkbox).toBeChecked();
  });

  it('persists the recovery Telegram notification preference', async () => {
    render(<ControlsPage />);
    const checkbox = await screen.findByRole('checkbox', {
      name: /feed recovery telegram notifications/i,
    });
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith(
        '/api/controls/recovery-settings',
        expect.objectContaining({
          method: 'PUT',
          body: JSON.stringify({ telegram_notifications: false }),
        }),
      );
    });
  });
});
