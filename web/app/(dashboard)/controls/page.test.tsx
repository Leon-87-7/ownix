// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor, within } from '@/test/render';
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
  { id: 't1', name: 'Alpha', meaning: 'first', color: '#ff0000', pinned: false },
  { id: 't2', name: 'Beta', meaning: '', color: '#00ff00', pinned: true },
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
    toggleTagPinned: vi.fn(),
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

  it('reflects each tag\'s pinned state and calls toggleTagPinned on click', () => {
    const toggleTagPinned = vi.fn().mockResolvedValue(undefined);
    setupTagsMock({ toggleTagPinned });
    render(<ControlsPage />);

    const unpinBeta = section('Tags').getByRole('button', {
      name: 'Unpin Beta from GoTo',
    });
    expect(unpinBeta).toHaveAttribute('aria-pressed', 'true');
    const pinAlpha = section('Tags').getByRole('button', {
      name: 'Pin Alpha for GoTo',
    });
    expect(pinAlpha).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(pinAlpha);
    expect(toggleTagPinned).toHaveBeenCalledWith('t1', true);

    fireEvent.click(unpinBeta);
    expect(toggleTagPinned).toHaveBeenCalledWith('t2', false);

    // Toggling pin must never open the edit panel.
    expect(section('Tags').queryByRole('button', { name: 'Save' })).toBeNull();
  });

  it('surfaces a pin-toggle failure instead of discarding it silently', async () => {
    const toggleTagPinned = vi.fn().mockRejectedValue(new Error('Pin request failed'));
    setupTagsMock({ toggleTagPinned });
    render(<ControlsPage />);

    fireEvent.click(
      section('Tags').getByRole('button', { name: 'Pin Alpha for GoTo' }),
    );

    await waitFor(() =>
      expect(section('Tags').getByText('Pin request failed')).toBeTruthy(),
    );
  });

  it('opens the edit panel pre-filled when a tag pill is clicked', () => {
    render(<ControlsPage />);
    const pill = section('Tags').getByRole('button', { name: 'Edit Alpha' });
    fireEvent.click(pill);
    expect(pill).toHaveAttribute('aria-pressed', 'true');
    const nameInputs = section('Tags').getAllByPlaceholderText(
      'Tag name',
    ) as HTMLInputElement[];
    expect(nameInputs[1].value).toBe('Alpha');
    expect(
      section('Tags').getByRole('button', { name: 'Save' }),
    ).toBeTruthy();
  });

  it('toggles the edit panel closed when the same pill is clicked again', () => {
    render(<ControlsPage />);
    const pill = section('Tags').getByRole('button', { name: 'Edit Alpha' });
    fireEvent.click(pill);
    fireEvent.click(pill);
    expect(pill).toHaveAttribute('aria-pressed', 'false');
    expect(
      section('Tags').queryByRole('button', { name: 'Save' }),
    ).toBeNull();
  });

  it('switches the edit panel to another tag when a different pill is clicked', () => {
    render(<ControlsPage />);
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Alpha' }));
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Beta' }));
    const nameInputs = section('Tags').getAllByPlaceholderText(
      'Tag name',
    ) as HTMLInputElement[];
    expect(nameInputs[1].value).toBe('Beta');
  });

  it('saves edits via updateTag and closes the panel', async () => {
    const updateTag = vi.fn().mockResolvedValue(undefined);
    setupTagsMock({ updateTag });
    render(<ControlsPage />);
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Alpha' }));
    const nameInputs = section('Tags').getAllByPlaceholderText(
      'Tag name',
    ) as HTMLInputElement[];
    fireEvent.change(nameInputs[1], { target: { value: 'Alpha2' } });
    fireEvent.click(section('Tags').getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(updateTag).toHaveBeenCalledWith(
        't1',
        expect.objectContaining({ name: 'Alpha2' }),
      ),
    );
    await waitFor(() =>
      expect(
        section('Tags').queryByRole('button', { name: 'Save' }),
      ).toBeNull(),
    );
  });

  it('closes the edit panel on Cancel', () => {
    render(<ControlsPage />);
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Alpha' }));
    fireEvent.click(section('Tags').getByRole('button', { name: 'Cancel' }));
    expect(
      section('Tags').queryByRole('button', { name: 'Save' }),
    ).toBeNull();
  });

  it('deletes the tag from the edit panel after confirmation', async () => {
    const deleteTag = vi.fn().mockResolvedValue(undefined);
    setupTagsMock({ deleteTag });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<ControlsPage />);
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Alpha' }));
    fireEvent.click(
      section('Tags').getByRole('button', { name: 'Delete Alpha' }),
    );
    await waitFor(() => expect(deleteTag).toHaveBeenCalledWith('t1'));
    await waitFor(() =>
      expect(
        section('Tags').queryByRole('button', { name: 'Save' }),
      ).toBeNull(),
    );
  });

  it('does not delete when the confirmation dialog is declined', () => {
    const deleteTag = vi.fn();
    setupTagsMock({ deleteTag });
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<ControlsPage />);
    fireEvent.click(section('Tags').getByRole('button', { name: 'Edit Alpha' }));
    fireEvent.click(
      section('Tags').getByRole('button', { name: 'Delete Alpha' }),
    );
    expect(deleteTag).not.toHaveBeenCalled();
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

  it('renders the account-deletion consequences before the delete button in DOM order', () => {
    render(<ControlsPage />);
    const zone = section('Danger zone');
    // Regex, not a literal substring: the exact consequences wording is
    // hoisted into a shared constant in a later task and may change slightly
    // — this only needs to keep matching "roughly this sentence", not an
    // exact string, so it doesn't go stale when that happens.
    const consequences = zone.getByText(/deletes every job.*brain link.*domain rule/i);
    const button = zone.getByRole('button', { name: 'Delete my account' });
    // Node.DOCUMENT_POSITION_FOLLOWING (4): button comes after consequences.
    expect(
      consequences.compareDocumentPosition(button) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });
});
