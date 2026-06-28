'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileCode2, Sparkles, Upload, CircleQuestionMark } from 'lucide-react';
import { StatusBadge } from '@/components/badges';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';
import { FilterBar } from '@/components/filter-bar';
import { PageShell, PageHeader } from '@/components/page-shell';

type Job = { id: string; title?: string | null; url: string; status: string; created_at: string; telegram_delivery?: 'off' | 'on' | 'retroactive' };

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

// Full format list (LlamaParse multi-format). All-inline markup so it stays
// valid nested inside the header <p>; reveals on hover OR keyboard focus.
function FormatHelp() {
  return (
    <span className="group relative inline-flex">
      <button
        type="button"
        aria-label="Show all supported formats"
        aria-describedby="doc-formats-tip"
        className="inline-flex h-5 w-5 items-center justify-center rounded text-muted transition-ui hover:text-ink"
      >
        <CircleQuestionMark className="h-4 w-4" aria-hidden="true" />
      </button>
      <span
        id="doc-formats-tip"
        role="tooltip"
        className="pointer-events-none absolute left-0 top-full z-20 mt-2 w-72 max-w-[calc(100vw-2rem)] rounded-md border border-line bg-surface p-3 font-sans text-xs leading-relaxed text-body opacity-0 shadow-overlay transition-opacity duration-150 ease-out-quart group-hover:opacity-100 group-focus-within:opacity-100"
      >
        <span className="block font-medium text-ink">All supported formats</span>
        <span className="mt-2 grid gap-1.5">
          {[
            ['PDF', '.pdf'],
            ['Word', '.doc .docx .docm .odt .rtf .pages'],
            ['PowerPoint', '.ppt .pptx .pptm .odp .key'],
            ['Spreadsheet', '.xls .xlsx .xlsm .ods .csv .tsv .numbers'],
            ['Images', '.jpg .jpeg .png .gif .bmp .tiff .webp .svg'],
          ].map(([label, exts]) => (
            <span key={label} className="block">
              <span className="text-muted">{label}</span>{' '}
              <span className="font-mono text-[11px] text-body">{exts}</span>
            </span>
          ))}
        </span>
      </span>
    </span>
  );
}

export default function DocParserPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [status, setStatus] = useState('');
  const [q, setQ] = useState('');
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');
  const [compact, setCompact] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const r = await fetch(`/api/jobs?content_type=document&limit=100${status ? `&status=${status}` : ''}`);
    const d = await r.json();
    setJobs(d.items ?? []);
  }, [status]);

  useEffect(() => { load(); }, [load]);

  // Keep the SSE handler pointed at the latest load (with current status filter)
  // without tearing down the EventSource on every filter change.
  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    const es = new EventSource('/api/parsed/events');
    const onJobs = () => loadRef.current();
    es.addEventListener('jobs', onJobs);
    return () => es.close();
  }, []);

  const filtered = useMemo(() => jobs.filter(j => (j.title || j.url).toLowerCase().includes(q.toLowerCase())), [jobs, q]);

  async function uploadFile(file: File) {
    setError('');
    const fd = new FormData();
    fd.append('file', file);
    const r = await fetch('/api/parsed/upload', { method: 'POST', body: fd });
    if (!r.ok) { setError(await errorMessage(r, 'Upload failed')); return; }
    await load();
  }
  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    const r = await fetch('/api/parsed/url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    if (!r.ok) { setError(await errorMessage(r, 'URL upload failed')); return; }
    setUrl('');
    await load();
  }

  return (
    <PageShell>
      <PageHeader
        icon={FileCode2}
        title="Doc Parser"
        description={
          <>
            Upload PDFs, Microsoft Office formats and Images.
            <span className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 font-mono text-xs text-muted">
              <span>.pdf | .docx | .xlsx | .pptx | .png | …</span>
              <FormatHelp />
            </span>
          </>
        }
      />

      <FilterBar
        tabs={[
          { label: 'PDF', value: 'pdf', count: jobs.length },
          { label: 'Word', value: 'word', disabled: true, badge: 'soon', dividerBefore: true },
          { label: 'Spreadsheet', value: 'spreadsheet', disabled: true, badge: 'soon', dividerBefore: true },
          { label: 'Presentation', value: 'presentation', disabled: true, badge: 'soon', dividerBefore: true },
          { label: 'Image', value: 'image', disabled: true, badge: 'soon', dividerBefore: true },
        ]}
        tabValue="pdf"
        onTabChange={() => {}}
        tabsLabel="Document format"
        query={q} setQuery={setQ} searchPlaceholder="Search documents…" searchLabel="Search documents"
        statusValue={status} onStatusChange={setStatus}
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <section className={`${compact ? 'max-lg:max-h-12 max-lg:overflow-hidden' : ''} rounded-lg border border-line bg-surface p-4`}>
          <button onClick={() => setCompact(!compact)} className="mb-3 w-full text-left text-sm font-medium text-ink lg:hidden">Upload documents</button>
          <form onSubmit={submitUrl} className="flex gap-2">
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://example.com/file.pdf" className="min-w-0 flex-1 rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink" />
            <button className="rounded-md bg-signal px-4 text-sm text-onsignal">Fetch</button>
          </form>
          <button
            type="button"
            onDragOver={e => e.preventDefault()}
            onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if (f) uploadFile(f); }}
            onClick={() => fileRef.current?.click()}
            className="mt-4 flex min-h-48 w-full cursor-pointer flex-col items-center justify-center rounded-md border border-dashed border-line-strong bg-canvas text-body transition-ui hover:border-signal hover:text-ink"
          >
            <Upload />
            <span>Drop a PDF here or click to choose</span>
            <input ref={fileRef} type="file" accept="application/pdf" hidden onChange={e => { const f = e.target.files?.[0]; if (f) uploadFile(f); }} />
          </button>
          {error && <p className="mt-2 text-sm text-status-error">{error}</p>}
        </section>

        <section className="space-y-2">
          {filtered.map(j => (
            <div key={j.id} className="rounded-lg border border-line bg-surface p-4 hover:bg-raised">
              <div className="flex items-center gap-3">
                <Link href={`/doc-parser/${j.id}`} className="min-w-0 flex-1 truncate text-sm font-medium text-ink">{j.title || j.url}</Link>
                <Sparkles className="h-4 w-4 text-signal" />
                <StatusBadge label={j.status} />
                <TelegramToggle jobId={j.id} value={j.telegram_delivery || 'off'} />
              </div>
              <p className="mt-2 font-mono text-xs text-muted">{j.id}</p>
            </div>
          ))}
        </section>
      </div>
    </PageShell>
  );
}
