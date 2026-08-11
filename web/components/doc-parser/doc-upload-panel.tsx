'use client';

import { useRef, useState } from 'react';
import { ChevronDown, Upload } from 'lucide-react';
import { IntakeLinksList, type IntakeLink } from '@/components/intake/intake-links-list';
import { DOCUMENT_UPLOAD_ACCEPT } from '@/lib/document-formats';

// FastAPI puts the reason in `detail` (a string, or {field, message} for our
// 400/422s). Surface it instead of a generic "failed" so real causes are visible.
async function errorMessage(r: Response, fallback: string): Promise<string> {
  try {
    const d = await r.json();
    const detail = d?.detail;
    if (typeof detail === 'string') return detail;
    if (detail?.message) return detail.message;
  } catch { /* non-JSON (e.g. a 500 HTML page) — fall through */ }
  return `${fallback} (${r.status})`;
}

// onUploaded receives the accepted job's id (null if the API omitted it) so
// callers can route to its detail page; the doc-parser page ignores the arg.
export function DocUploadPanel({
  onUploaded,
  flat = false,
}: {
  onUploaded: (jobId: string | null) => void;
  flat?: boolean;
}) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [compact, setCompact] = useState(true);
  const [busy, setBusy] = useState(false);
  const [links, setLinks] = useState<IntakeLink[] | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function uploadFile(file: File) {
    if (busy) return;
    setError('');
    setLinks(null);
    setBusy(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const r = await fetch('/api/parsed/upload', { method: 'POST', body: fd });
      if (!r.ok) { setError(await errorMessage(r, 'Upload failed')); return; }
      const data = await r.json();
      // An image forks to photo-OCR and returns extracted links, not a job.
      if (data?.kind === 'links') { setLinks(data.links ?? []); return; }
      onUploaded(data?.job_id ?? null);
    } finally {
      setBusy(false);
    }
  }
  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setError('');
    setLinks(null);
    setBusy(true);
    try {
      const r = await fetch('/api/parsed/url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
      if (!r.ok) { setError(await errorMessage(r, 'URL upload failed')); return; }
      setUrl('');
      onUploaded((await r.json())?.job_id ?? null);
    } finally {
      setBusy(false);
    }
  }

  // flat: no card chrome and no mobile collapse — it lives inside a dialog.
  const Wrapper = flat ? 'div' : 'section';
  return (
    <Wrapper className={flat ? 'mt-4' : `${compact ? 'max-lg:max-h-16 max-lg:overflow-hidden' : ''} rounded-lg border border-line bg-surface p-4`}>
      {!flat && (
        <button
          type="button"
          onClick={() => setCompact(!compact)}
          aria-expanded={!compact}
          className="mb-3 flex w-full items-center justify-between gap-2 rounded-md border border-line bg-raised px-3 py-2 text-sm font-medium text-ink transition-ui hover:border-line-strong hover:text-ink active:scale-[0.96] motion-reduce:active:scale-100 lg:hidden"
        >
          <span className="flex items-center gap-2">
            <Upload className="h-4 w-4 shrink-0 text-signal" aria-hidden="true" />
            Upload documents
          </span>
          <ChevronDown
            aria-hidden="true"
            className={`h-4 w-4 shrink-0 text-muted transition-transform duration-200 ease-out motion-reduce:transition-none ${compact ? '' : 'rotate-180'}`}
          />
        </button>
      )}
      <form onSubmit={submitUrl} className="flex gap-2">
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com/file.pdf" className="min-w-0 flex-1 rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink" />
        <button disabled={busy} className="rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-transform active:scale-[0.96] disabled:opacity-50 motion-reduce:active:scale-100">Fetch</button>
      </form>
      <button
        type="button"
        disabled={busy}
        onDragOver={e => e.preventDefault()}
        onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }}
        onClick={() => fileRef.current?.click()}
        className="mt-4 flex min-h-48 w-full cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-line-strong bg-canvas text-body transition-ui hover:border-signal hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
      >
        <Upload />
        <span>Drop a document to create a job, or an image to extract links</span>
        <input
          ref={fileRef}
          type="file"
          accept={DOCUMENT_UPLOAD_ACCEPT}
          hidden
          onChange={e => { const f = e.target.files?.[0]; if (f) uploadFile(f); }}
        />
      </button>
      {error && <p className="mt-2 text-sm text-status-error">{error}</p>}
      {links !== null && (
        links.length > 0
          ? (
              <div className="mt-3">
                <p className="mb-2 text-xs font-medium uppercase text-muted">Image links</p>
                <IntakeLinksList links={links} />
              </div>
            )
          : <p className="mt-2 text-sm text-muted">No links found in that image.</p>
      )}
    </Wrapper>
  );
}
