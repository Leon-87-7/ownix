// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react';
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
});

describe('ControlsPage', () => {
  it('renders Controls heading', () => {
    render(<ControlsPage />);
    expect(screen.getByText('Controls')).toBeTruthy();
  });

  it('renders tab buttons', () => {
    render(<ControlsPage />);
    expect(screen.getByRole('button', { name: 'Tags' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Allowed Domains' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ignored Domains' })).toBeTruthy();
  });

  it('shows Tags tab content by default', () => {
    render(<ControlsPage />);
    expect(screen.getByText('Create tag')).toBeTruthy();
  });

  it('renders tag list', () => {
    render(<ControlsPage />);
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
  });

  it('shows loading state in TagsTab', () => {
    setupTagsMock({ loading: true, tags: [] });
    render(<ControlsPage />);
    expect(screen.getByText(/loading tags/i)).toBeTruthy();
  });

  it('shows fetchError in TagsTab', () => {
    setupTagsMock({ fetchError: 'Failed to load tags', tags: [] });
    render(<ControlsPage />);
    expect(screen.getByText('Failed to load tags')).toBeTruthy();
  });

  it('shows empty message when no tags', () => {
    setupTagsMock({ tags: [] });
    render(<ControlsPage />);
    expect(screen.getByText(/no tags yet/i)).toBeTruthy();
  });

  it('switches to Allowed Domains tab', () => {
    render(<ControlsPage />);
    const allowedBtn = screen.getByRole('button', { name: 'Allowed Domains' });
    fireEvent.click(allowedBtn);
    expect(screen.getByText('Add domain')).toBeTruthy();
    expect(screen.getByText('example.com')).toBeTruthy();
  });

  it('shows domains in DomainTab', () => {
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    expect(screen.getByText('test.org')).toBeTruthy();
  });

  it('shows loading state in DomainTab', () => {
    setupDomainsMock({ loading: true, domains: [] });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    expect(screen.getByText(/loading allowed domains/i)).toBeTruthy();
  });

  it('shows fetchError in DomainTab', () => {
    setupDomainsMock({ fetchError: 'Network error', domains: [] });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    expect(screen.getByText('Network error')).toBeTruthy();
  });

  it('shows empty message in DomainTab when no domains', () => {
    setupDomainsMock({ domains: [] });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    expect(screen.getByText(/no allowed domains yet/i)).toBeTruthy();
  });

  it('switches to Ignored Domains tab', () => {
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Ignored Domains' }));
    expect(screen.getByText('Add domain')).toBeTruthy();
  });

  it('calls addDomain on form submit in DomainTab', async () => {
    const addDomain = vi.fn(async () => {});
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    const input = screen.getByPlaceholderText('example.com');
    fireEvent.change(input, { target: { value: 'newdomain.com' } });
    const form = input.closest('form')!;
    fireEvent.submit(form);
    await new Promise(r => setTimeout(r, 10));
    expect(addDomain).toHaveBeenCalledWith('newdomain.com');
  });

  it('does not call addDomain when input is blank', async () => {
    const addDomain = vi.fn(async () => {});
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    const input = screen.getByPlaceholderText('example.com');
    // leave blank
    const form = input.closest('form')!;
    fireEvent.submit(form);
    await new Promise(r => setTimeout(r, 10));
    expect(addDomain).not.toHaveBeenCalled();
  });

  it('calls removeDomain when Remove is clicked in DomainTab', async () => {
    const removeDomain = vi.fn(async () => {});
    setupDomainsMock({ removeDomain });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    const removeBtns = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeBtns[0]);
    await new Promise(r => setTimeout(r, 10));
    expect(removeDomain).toHaveBeenCalledWith('example.com');
  });

  it('shows addError when addDomain rejects', async () => {
    const addDomain = vi.fn(async () => { throw new Error('Duplicate domain'); });
    setupDomainsMock({ addDomain });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    const input = screen.getByPlaceholderText('example.com');
    fireEvent.change(input, { target: { value: 'dup.com' } });
    const form = input.closest('form')!;
    fireEvent.submit(form);
    const { waitFor: wf } = await import('@testing-library/react');
    await wf(() => expect(screen.getByText('Duplicate domain')).toBeTruthy());
  });

  it('shows removeError when removeDomain rejects', async () => {
    const removeDomain = vi.fn(async () => { throw new Error('Remove failed'); });
    setupDomainsMock({ removeDomain });
    render(<ControlsPage />);
    fireEvent.click(screen.getByRole('button', { name: 'Allowed Domains' }));
    const removeBtns = screen.getAllByRole('button', { name: /remove/i });
    fireEvent.click(removeBtns[0]);
    const { waitFor: wf } = await import('@testing-library/react');
    await wf(() => expect(screen.getByText('Remove failed')).toBeTruthy());
  });
});
