// @vitest-environment jsdom
import { render, screen, fireEvent, waitFor, within, act, cleanup } from '@/test/render';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import ControlsPage from './page';
import { resetAccessibilitySettingsForTests } from '@/lib/hooks/useAccessibilitySettings';

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
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    if (String(input).includes('accessibility-settings')) {
      if (init?.method === 'PUT') {
        return new Response(init.body as string, { status: 200 });
      }
      return new Response(JSON.stringify({
        visual_motion: true,
        haptic_motion: true,
        voice_uri: null,
      }), { status: 200 });
    }
    if (init?.method === 'PUT') {
      return new Response(JSON.stringify({ telegram_notifications: false }), { status: 200 });
    }
    return new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 });
  }));
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  resetAccessibilitySettingsForTests();
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
    expect(screen.getByText('Accessibility')).toBeTruthy();
    expect(screen.getByText('Press animation')).toBeTruthy();
  });

  it('hides the Voice row when speech synthesis is unsupported', () => {
    // Explicit regardless of prior test ordering/global stub leakage — vitest
    // doesn't auto-clear vi.stubGlobal between tests in this file (its
    // beforeEach only re-stubs fetch), so a speechSynthesis stub set by a
    // later-defined test must never be relied on to be absent here.
    delete (window as unknown as { speechSynthesis?: SpeechSynthesis }).speechSynthesis;
    render(<ControlsPage />);
    expect(section('Accessibility').queryByText('Voice')).toBeNull();
  });

  it('shows the Voice row grouped by language and lets the operator pick a voice', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
      { voiceURI: 'uk', name: 'Daniel', lang: 'en-GB' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    render(<ControlsPage />);

    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;
    expect(within(select).getByText('System default')).toBeTruthy();
    // Derive the expected label from the same API groupVoicesByLanguage uses
    // at runtime, rather than hardcoding "American English" — Intl's
    // resolved display name for a locale isn't guaranteed portable across
    // ICU implementations/versions (see useSpeechVoices.test.ts).
    const expectedLabel = new Intl.DisplayNames(['en'], { type: 'language' }).of('en-US');
    expect(within(select).getByRole('group', { name: expectedLabel })).toBeTruthy();
    expect(within(select).getByText('Google US English')).toBeTruthy();
    expect(within(select).getByText('Daniel')).toBeTruthy();

    fireEvent.change(select, { target: { value: 'uk' } });
    await waitFor(() => expect(select.value).toBe('uk'));
  });

  it('shows an unavailable-voice placeholder and lets the operator clear it to System default', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    // Override this test's GET response with a voice_uri from a machine/browser
    // that doesn't have that voice installed.
    vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('accessibility-settings')) {
        if (init?.method === 'PUT') return new Response(init.body as string, { status: 200 });
        return new Response(JSON.stringify({
          visual_motion: true,
          haptic_motion: true,
          voice_uri: 'a-voice-from-another-machine',
        }), { status: 200 });
      }
      return new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 });
    }));
    render(<ControlsPage />);

    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;
    // Showing "" here (silently) would be a dead end: the same-value click
    // wouldn't fire onChange, so the stale URI could never be cleared. It
    // must show the missing URI as its own (disabled) option instead.
    await waitFor(() => expect(select.value).toBe('a-voice-from-another-machine'));
    expect(within(select).getByText('Unavailable voice')).toBeTruthy();

    fireEvent.change(select, { target: { value: '' } });
    await waitFor(() => expect(select.value).toBe(''));
  });

  it('keeps the newer voice pick when its PUT resolves before an older overlapping one', async () => {
    // Regression test for the generationRef guard: pick 'us' (PUT deferred),
    // then pick 'uk' before the first PUT resolves (PUT also deferred).
    // Resolve the OLDER ('us') request last — without the guard, its
    // response would land last and roll the UI back to 'us'.
    //
    // Note: a mouse/keyboard user can't literally trigger this — the select
    // is disabled while saving={true}, so a real second pick can't happen
    // before the first PUT settles. fireEvent.change bypasses the disabled
    // attribute (it dispatches the DOM event directly), which is exactly
    // what's needed here: this test exercises the generationRef guard logic
    // itself, the same logic Task 3's "external write invalidates a slower
    // in-flight load" test exercises from the other direction — not a
    // literal two-click scenario.
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
      { voiceURI: 'uk', name: 'Daniel', lang: 'en-GB' },
    ] as SpeechSynthesisVoice[];
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak: vi.fn(),
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));

    let resolveFirstPut!: (response: Response) => void;
    let resolveSecondPut!: (response: Response) => void;
    const firstPut = new Promise<Response>((done) => { resolveFirstPut = done; });
    const secondPut = new Promise<Response>((done) => { resolveSecondPut = done; });
    let putCount = 0;
    vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      if (String(input).includes('accessibility-settings')) {
        if (init?.method === 'PUT') {
          putCount += 1;
          return putCount === 1 ? firstPut : secondPut;
        }
        return Promise.resolve(new Response(JSON.stringify({
          visual_motion: true,
          haptic_motion: true,
          voice_uri: null,
        }), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify({ telegram_notifications: true }), { status: 200 }));
    }));

    render(<ControlsPage />);
    const select = await section('Accessibility').findByLabelText('Voice') as HTMLSelectElement;

    fireEvent.change(select, { target: { value: 'us' } });
    await waitFor(() => expect(select.value).toBe('us'));
    fireEvent.change(select, { target: { value: 'uk' } });
    await waitFor(() => expect(select.value).toBe('uk'));

    await act(async () => {
      // Older request resolves LAST.
      resolveSecondPut(new Response(JSON.stringify({
        visual_motion: true, haptic_motion: true, voice_uri: 'uk',
      }), { status: 200 }));
      await secondPut;
      resolveFirstPut(new Response(JSON.stringify({
        visual_motion: true, haptic_motion: true, voice_uri: 'us',
      }), { status: 200 }));
      await firstPut;
    });

    expect(select.value).toBe('uk');
  });

  it('previews the selected voice via the Listen affordance', async () => {
    const voices = [
      { voiceURI: 'us', name: 'Google US English', lang: 'en-US' },
    ] as SpeechSynthesisVoice[];
    const speak = vi.fn();
    vi.stubGlobal('speechSynthesis', {
      cancel: vi.fn(),
      speak,
      getVoices: vi.fn(() => voices),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    });
    vi.stubGlobal('SpeechSynthesisUtterance', vi.fn(function (this: { text: string }, text: string) {
      this.text = text;
    }));
    render(<ControlsPage />);

    // Wait for the exact element being clicked, not a sibling: the select's
    // visibility is gated on useSpeechVoices' own supported flag, but the
    // preview button's is gated on ListenButton's *own* internal useSpeech
    // effect — a separate hook instance with its own tick. Waiting on the
    // select alone doesn't guarantee the button is mounted yet.
    const previewButton = await section('Accessibility').findByRole('button', { name: 'Preview voice' });
    fireEvent.click(previewButton);
    expect(speak).toHaveBeenCalledOnce();
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

  it('shows the server-provided error detail when account deletion fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Cannot delete: Google disconnect failed' }), { status: 502 }),
    ));
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
    const dialog = within(screen.getByRole('dialog'));
    fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
    fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));
    // The error renders inside the dialog (Radix portals dialog content out
    // of the "Danger zone" <details> subtree), so it's queried via `dialog`.
    await waitFor(() =>
      expect(dialog.getByText('Cannot delete: Google disconnect failed')).toBeTruthy(),
    );
  });

  it('keeps the account-delete confirm button disabled until "delete" is typed', async () => {
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));

    const dialog = within(screen.getByRole('dialog'));
    const confirmButton = dialog.getByRole('button', { name: 'Yes, delete my account' });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(dialog.getByLabelText('Type delete to confirm'), {
      target: { value: 'delete' },
    });
    expect(confirmButton).not.toBeDisabled();
  });

  it('clears the type-to-confirm text after cancel, so reopening requires typing it again', async () => {
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));

    let dialog = within(screen.getByRole('dialog'));
    fireEvent.change(dialog.getByLabelText('Type delete to confirm'), {
      target: { value: 'delete' },
    });
    expect(dialog.getByRole('button', { name: 'Yes, delete my account' })).not.toBeDisabled();

    fireEvent.click(dialog.getByRole('button', { name: 'Cancel' }));
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));

    dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByLabelText('Type delete to confirm')).toHaveValue('');
    expect(dialog.getByRole('button', { name: 'Yes, delete my account' })).toBeDisabled();
  });

  it('announces the account-delete error as an alert', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Cannot delete right now' }), { status: 502 }),
    ));
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
    const dialog = within(screen.getByRole('dialog'));
    fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
    fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));
    // The error now renders inside the dialog itself (not a page-body
    // sibling), so it stays in the accessible subtree while the dialog's
    // modal overlay is open — a plain getByRole('alert') is enough.
    await waitFor(() => expect(dialog.getByRole('alert')).toHaveTextContent('Cannot delete right now'));
  });

  it('keeps the confirm dialog open when account deletion fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      new Response(JSON.stringify({ detail: 'Cannot delete: 3 jobs still processing' }), { status: 409 }),
    ));
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
    const dialog = within(screen.getByRole('dialog'));
    fireEvent.change(dialog.getByLabelText('Type delete to confirm'), { target: { value: 'delete' } });
    fireEvent.click(dialog.getByRole('button', { name: 'Yes, delete my account' }));

    await waitFor(() =>
      expect(dialog.getByText('Cannot delete: 3 jobs still processing')).toBeTruthy(),
    );
    // The dialog itself must still be mounted — a silent close would read as
    // "nothing happened" on the highest-stakes destructive action in the app.
    expect(screen.getByRole('dialog')).toBeTruthy();
    expect(screen.getByText('Permanently delete your account?')).toBeTruthy();
  });

  it('uses the same consequences copy in the dialog description and the static paragraph', () => {
    render(<ControlsPage />);
    const zone = section('Danger zone');
    fireEvent.click(zone.getByRole('button', { name: 'Delete my account' }));
    const dialogText = screen.getByRole('dialog').textContent ?? '';
    const staticParagraph = zone.getByText(/deletes every job, brain link, tag, and domain rule/i);
    expect(dialogText).toContain(staticParagraph.textContent);
  });

  it('gives the Danger zone section title a distinct text treatment', () => {
    render(<ControlsPage />);
    const title = screen.getByText('Danger zone');
    expect(title.className).toContain('text-status-error');

    const otherTitle = screen.getByText('Chrome Extension');
    expect(otherTitle.className).not.toContain('text-status-error');
  });

});
