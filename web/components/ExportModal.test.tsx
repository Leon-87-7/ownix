// @vitest-environment jsdom
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ExportModal from './ExportModal';

const gdocTrigger = vi.hoisted(() => vi.fn());
const gdocState = vi.hoisted(() => ({
  status: 'idle',
  error: null as string | null,
  errorCode: null as string | null,
  resultUrl: null as string | null,
}));

vi.mock('@/lib/hooks/useGdocExport', () => ({
  useGdocExport: () => ({
    trigger: gdocTrigger,
    ...gdocState,
  }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  gdocState.status = 'idle';
  gdocState.error = null;
  gdocState.errorCode = null;
  gdocState.resultUrl = null;
});

const defaultProps = {
  spaceId: 's1',
  spaceName: 'Test Space',
  onClose: vi.fn(),
};

describe('ExportModal', () => {
  it('shows loading spinner while fetch is in flight', async () => {
    // fetch never resolves during this test
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<ExportModal {...defaultProps} />);
    expect(screen.getByText(/composing export/i)).toBeTruthy();
  });

  it('shows error message when markdown fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: false, json: async () => ({}) }) as Response));

    render(<ExportModal {...defaultProps} />);
    await waitFor(() => expect(screen.getByText(/failed to compose export/i)).toBeTruthy());
  });

  it('shows export buttons after successful fetch', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ markdown: '# Hello' }) }) as Response));

    render(<ExportModal {...defaultProps} />);
    await waitFor(() => expect(screen.getByText(/download .md/i)).toBeTruthy());
    expect(screen.getByText(/download .txt/i)).toBeTruthy();
    expect(screen.getByText(/save as pdf/i)).toBeTruthy();
    expect(screen.getByText(/create google doc/i)).toBeTruthy();
  });

  it('calls onClose when close button is clicked', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ markdown: '# Hello' }) }) as Response));

    const onClose = vi.fn();
    render(<ExportModal {...defaultProps} onClose={onClose} />);

    // Wait for content to load
    await waitFor(() => screen.getByText(/download .md/i));

    const closeBtn = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalled();
  });

  it('shows space name in heading', async () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise(() => {})));
    render(<ExportModal {...defaultProps} spaceName="My Cool Space" />);
    expect(screen.getByText(/my cool space/i)).toBeTruthy();
  });

  it('shows description text when loaded', async () => {
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ markdown: '# Content' }) }) as Response));

    render(<ExportModal {...defaultProps} />);
    await waitFor(() => expect(screen.getByText(/markdown, plain text, and pdf/i)).toBeTruthy());
  });

  it('offers a user-initiated PDF fallback when Drive is not configured', async () => {
    gdocState.status = 'error';
    gdocState.error = 'Google Drive is not configured. Use the .md, .txt, or PDF buttons above.';
    gdocState.errorCode = 'drive_not_configured';
    vi.stubGlobal('fetch', vi.fn(async () =>
      ({ ok: true, json: async () => ({ markdown: '# Content' }) }) as Response));

    const print = vi.fn();
    const focus = vi.fn();
    const appendChild = vi.fn();
    const createElement = vi.fn((tag: string) => {
      if (tag === 'style') {
        return { textContent: '' };
      }
      return { textContent: '' };
    });
    const open = vi.fn(() => ({
      document: {
        createElement,
        head: { appendChild },
        body: { appendChild },
        title: '',
      },
      focus,
      print,
    }));
    vi.stubGlobal('open', open);

    render(<ExportModal {...defaultProps} />);

    await waitFor(() => expect(screen.getByText(/google drive is not configured/i)).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: /save as pdf instead/i }));

    expect(open).toHaveBeenCalledWith('', '_blank');
    expect(print).toHaveBeenCalled();
  });
});
