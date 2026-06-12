// @vitest-environment jsdom
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ExportModal from './ExportModal';

vi.mock('@/lib/hooks/useGdocExport', () => ({
  useGdocExport: () => ({
    trigger: vi.fn(),
    status: 'idle',
    error: null,
    resultUrl: null,
  }),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
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
});
