'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FileCode2, Sparkles, Upload } from 'lucide-react';
import { StatusBadge } from '@/components/badges';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';

type Job = { id: string; title?: string | null; url: string; status: string; created_at: string; telegram_delivery?: 'off' | 'on' | 'retroactive' };
const statuses = ['', 'done', 'pending', 'processing', 'error'];

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
    if (!r.ok) { setError('Upload failed'); return; }
    await load();
  }
  async function submitUrl(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    const r = await fetch('/api/parsed/url', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) });
    if (!r.ok) { setError('URL upload failed'); return; }
    setUrl('');
    await load();
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header>
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-ink"><FileCode2 className="text-signal" />Doc Parser</h1>
        <p className="text-sm text-body">Upload PDFs, watch status live, and generate Gemini-transformed Markdown outputs.</p>
      </header>

      <div className="rounded-lg border border-line bg-surface p-3">
        <div className="flex flex-wrap items-center gap-2">
          <button className="rounded-md bg-signal px-3 py-1.5 text-sm text-onsignal">PDF <span className="font-mono">{jobs.length}</span></button>
          {['Word', 'Spreadsheet', 'Presentation', 'Image'].map(x => <button key={x} disabled className="rounded-md border border-line px-3 py-1.5 text-sm text-muted">{x} 0</button>)}
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search documents…" className="ml-auto h-9 rounded-md border border-line bg-canvas px-3 text-sm text-ink" />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {statuses.map(s => <button key={s || 'all'} onClick={() => setStatus(s)} className={`rounded-md px-3 py-1.5 text-sm ${status === s ? 'bg-signal text-onsignal' : 'bg-canvas text-body'}`}>{s || 'all'}</button>)}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
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
            className="mt-4 flex min-h-48 w-full cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-line-strong bg-canvas text-body"
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
    </div>
  );
}
