// @vitest-environment jsdom
import { fireEvent, render, screen } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { NewsletterContextList } from './newsletter-context-list';
import { useSpaceContext } from '@/lib/hooks/useSpaceContext';

vi.mock('next/dynamic', () => ({
  default: () =>
    function MockMarkdownEditor({
      initialMarkdown,
      label,
      onSave,
    }: {
      initialMarkdown: string;
      label: string;
      onSave: (markdown: string) => void;
    }) {
      return (
        <textarea
          aria-label={label}
          defaultValue={initialMarkdown}
          onChange={(event) => onSave(event.currentTarget.value)}
        />
      );
    },
}));

vi.mock('@/lib/hooks/useSpaceContext', () => ({ useSpaceContext: vi.fn() }));

const mockedUseSpaceContext = vi.mocked(useSpaceContext);

afterEach(() => {
  vi.restoreAllMocks();
});

describe('NewsletterContextList', () => {
  it('shows an empty state before a digest has generated context', () => {
    mockedUseSpaceContext.mockReturnValue({
      blobs: [],
      loading: false,
      blobError: null,
      setBlobError: vi.fn(),
      addBlob: vi.fn(),
      updateBlob: vi.fn(),
      deleteBlob: vi.fn(),
      reorderBlob: vi.fn(),
      patchBlobName: vi.fn(),
    });

    render(<NewsletterContextList spaceId="space_1" />);

    expect(screen.getByText('No context yet')).toBeInTheDocument();
  });

  it('saves edits through the existing space context hook', () => {
    const updateBlob = vi.fn();
    const patchBlobName = vi.fn();
    mockedUseSpaceContext.mockReturnValue({
      blobs: [
        {
          id: 'blob_1',
          space_id: 'space_1',
          name: 'Digest context',
          content: 'Initial summary',
          sort_order: 0,
          created_at: '2026-09-05 10:00:00',
          updated_at: '2026-09-05 10:00:00',
        },
      ],
      loading: false,
      blobError: null,
      setBlobError: vi.fn(),
      addBlob: vi.fn(),
      updateBlob,
      deleteBlob: vi.fn(),
      reorderBlob: vi.fn(),
      patchBlobName,
    });

    render(<NewsletterContextList spaceId="space_1" />);

    fireEvent.change(screen.getByDisplayValue('Digest context'), {
      target: { value: 'Updated context' },
    });
    fireEvent.change(screen.getByLabelText('Context'), { target: { value: 'New summary' } });

    expect(patchBlobName).toHaveBeenCalledWith('blob_1', 'Updated context');
    expect(updateBlob).toHaveBeenCalledWith('blob_1', 'Digest context', 'New summary');
  });
});
