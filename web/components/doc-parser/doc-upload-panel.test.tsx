// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DocUploadPanel } from './doc-upload-panel';

beforeEach(() => vi.restoreAllMocks());
afterEach(() => vi.restoreAllMocks());

function pickFile(container: HTMLElement, file: File) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

describe('DocUploadPanel', () => {
  it('renders extracted links for an image upload instead of creating a job', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ kind: 'links', links: [{ url: 'https://found.tld/x' }], summary: 's' }),
      ),
    );
    const onUploaded = vi.fn();
    const { container } = render(<DocUploadPanel onUploaded={onUploaded} flat />);

    pickFile(container, new File([new Uint8Array([1, 2, 3])], 'shot.png', { type: 'image/png' }));

    await waitFor(() => expect(screen.getByText('https://found.tld/x')).toBeInTheDocument());
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it('calls onUploaded with the job id for a document upload', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response(JSON.stringify({ job_id: 'JOB1' })));
    const onUploaded = vi.fn();
    const { container } = render(<DocUploadPanel onUploaded={onUploaded} flat />);

    pickFile(container, new File([new Uint8Array([1])], 'report.docx'));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('JOB1'));
  });

  it('accepts office + image formats on the file input', () => {
    const { container } = render(<DocUploadPanel onUploaded={vi.fn()} flat />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.accept).toContain('.docx');
    expect(input.accept).toContain('.xlsx');
    expect(input.accept).toContain('.pptx');
    expect(input.accept).toContain('image/*');
  });
});
