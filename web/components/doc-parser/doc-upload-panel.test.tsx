// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { DocUploadPanel } from './doc-upload-panel';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  vi.restoreAllMocks();
});
afterAll(() => server.close());

function pickFile(container: HTMLElement, file: File) {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  fireEvent.change(input, { target: { files: [file] } });
}

describe('DocUploadPanel', () => {
  it('renders extracted links for an image upload instead of creating a job', async () => {
    server.use(
      http.post('/api/parsed/upload', () =>
        HttpResponse.json({ kind: 'links', links: [{ url: 'https://found.tld/x' }], summary: 's' }),
      ),
    );
    const onUploaded = vi.fn();
    const { container } = render(<DocUploadPanel onUploaded={onUploaded} flat />);

    pickFile(container, new File([new Uint8Array([1, 2, 3])], 'shot.png', { type: 'image/png' }));

    await waitFor(() => expect(screen.getByText('https://found.tld/x')).toBeInTheDocument());
    expect(screen.getByText('Image links')).toBeInTheDocument();
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it('calls onUploaded with the job id for a document upload', async () => {
    server.use(http.post('/api/parsed/upload', () => HttpResponse.json({ job_id: 'JOB1' })));
    const onUploaded = vi.fn();
    const { container } = render(<DocUploadPanel onUploaded={onUploaded} flat />);

    pickFile(container, new File([new Uint8Array([1])], 'report.docx'));

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('JOB1'));
  });

  it('clears image links before submitting a URL', async () => {
    let resolveUrl!: (value: Response) => void;
    server.use(
      http.post('/api/parsed/upload', () =>
        HttpResponse.json({ kind: 'links', links: [{ url: 'https://found.tld/x' }], summary: 's' }),
      ),
      http.post('/api/parsed/url', () => new Promise<Response>((resolve) => { resolveUrl = resolve; })),
    );
    const onUploaded = vi.fn();
    const { container } = render(<DocUploadPanel onUploaded={onUploaded} flat />);

    pickFile(container, new File([new Uint8Array([1, 2, 3])], 'shot.png', { type: 'image/png' }));
    await waitFor(() => expect(screen.getByText('https://found.tld/x')).toBeInTheDocument());

    fireEvent.change(screen.getByPlaceholderText('https://example.com/file.pdf'), {
      target: { value: 'https://example.com/report.pdf' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Fetch' }));

    await waitFor(() => expect(screen.queryByText('https://found.tld/x')).not.toBeInTheDocument());
    resolveUrl!(HttpResponse.json({ job_id: 'JOB2' }));
    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith('JOB2'));
  });

  it('accepts office + image formats on the file input', () => {
    const { container } = render(<DocUploadPanel onUploaded={vi.fn()} flat />);
    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    expect(input.accept).toContain('.docx');
    expect(input.accept).toContain('.xlsx');
    expect(input.accept).toContain('.pptx');
    expect(input.accept).not.toContain('.xls,');
    expect(input.accept).toContain('image/*');
  });
});
