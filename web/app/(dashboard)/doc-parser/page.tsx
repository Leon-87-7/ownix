'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { FileCode2, Sparkles, Upload } from 'lucide-react';
import { StatusBadge } from '@/components/badges';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';
import { PageShell, PageHeader } from '@/components/page-shell';

type Job = { id: string; title?: string | null; url: string; status: string; created_at: string; telegram_delivery?: 'off' | 'on' | 'retroactive' };
const statuses = ['', 'done', 'pending', 'processing', 'error'];

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

// One filter pill, two jobs: the active type/status (signal) and the toggles.
// Color + press are the smoothness — clicks animate instead of snapping, and
// scale(0.97) gives the tap feedback. min-h-9 keeps the mobile hit area honest.
function Chip({
  active,
  disabled,
  onClick,
  children,
}: {
  active?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      aria-pressed={onClick ? active : undefined}
      className={`inline-flex min-h-9 items-center gap-1 rounded-md px-3.5 py-1.5 text-sm tabular-nums transition-[transform,background-color,color,border-color] duration-150 ease-out-quart active:scale-[0.97] disabled:pointer-events-none disabled:opacity-60 ${
        active
          ? 'bg-signal text-onsignal'
          : disabled
            ? 'border border-line text-muted'
            : 'bg-canvas text-body hover:bg-raised hover:text-ink'
      }`}
    >
      {children}
    </button>
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
        description="Upload PDFs, watch status live, and generate Gemini-transformed Markdown outputs."
      />

      <div className="rounded-lg border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Chip active>PDF <span className="font-mono">{jobs.length}</span></Chip>
          {['Word', 'Spreadsheet', 'Presentation', 'Image'].map(x => (
            <Chip key={x} disabled>{x} 0</Chip>
          ))}
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search documents…" className="h-9 w-full min-w-0 rounded-md border border-line bg-canvas px-3 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none sm:ml-auto sm:w-64" />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {statuses.map(s => (
            <Chip key={s || 'all'} active={status === s} onClick={() => setStatus(s)}>
              {s || 'all'}
            </Chip>
          ))}
        </div>
      </div>

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
