'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ExternalLink, Sparkles } from 'lucide-react';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';

const RANDOM_PROMPTS = [
  'Summarize into the 5 most important takeaways',
  'Extract all actionable steps as a checklist',
  'Explain this to a non-technical person',
];

type Job = { id: string; title?: string; url: string; status: string; telegram_delivery?: 'off' | 'on' | 'retroactive'; sheets_row_id?: string | null };
type Output = { id: string; kind: string; title: string; preview: string; content_url: string; created_at: string };

export default function DocDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [outs, setOuts] = useState<Output[]>([]);
  const [prompt, setPrompt] = useState(RANDOM_PROMPTS[0]);
  const [open, setOpen] = useState(false);

  async function load() {
    const [j, o] = await Promise.all([
      fetch(`/api/jobs/${id}`).then((r) => r.json()),
      fetch(`/api/parsed/${id}/outputs`).then((r) => r.json()),
    ]);
    setJob(j);
    setOuts(o);
  }
  useEffect(() => {
    load();
  }, [id]);

  async function clean() {
    await fetch(`/api/parsed/${id}/clean`, { method: 'POST' });
    load();
  }
  async function freestyle() {
    await fetch(`/api/parsed/${id}/freestyle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) });
    setOpen(false);
    load();
  }

  if (!job) return null;

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="flex items-start gap-3">
        <div className="flex-1">
          <h1 className="text-2xl font-semibold text-ink">{job.title || 'Document job'}</h1>
          <p className="font-mono text-xs text-muted">{job.id}</p>
        </div>
        <TelegramToggle jobId={job.id} value={job.telegram_delivery || 'off'} />
      </header>

      <div className="flex flex-wrap gap-2">
        <button onClick={clean} className="rounded-md bg-signal px-4 py-2 text-sm text-onsignal">Clean</button>
        <button onClick={() => setOpen(true)} className="rounded-md border border-line px-4 py-2 text-sm text-ink">Freestyle</button>
        <a href={`/api/parsed/${id}/outputs`} className="rounded-md border border-line px-4 py-2 text-sm text-ink">Get Markdown</a>
        {job.url && <span className="rounded-md border border-line px-4 py-2 font-mono text-xs text-muted">{job.url}</span>}
      </div>

      <section className="grid gap-3 md:grid-cols-2">
        {outs.map((o) => (
          <article key={o.id} className="rounded-lg border border-line bg-surface p-4">
            <div className="mb-2 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-signal" />
              <h2 className="flex-1 text-sm font-semibold text-ink">{o.title || o.kind}</h2>
              <a href={o.content_url} target="_blank" className="text-muted hover:text-ink"><ExternalLink className="h-4 w-4" /></a>
            </div>
            <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded bg-canvas p-3 font-mono text-xs text-body">{o.preview}</pre>
          </article>
        ))}
      </section>

      {open && (
        <div role="dialog" aria-modal="true" className="fixed inset-0 z-50 grid place-items-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-lg border border-line bg-surface p-4">
            <h2 className="text-lg font-semibold text-ink">Freestyle prompt</h2>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} className="mt-3 h-36 w-full rounded-md border border-line bg-canvas p-3 text-sm text-ink" />
            <div className="mt-3 flex justify-between">
              <button onClick={() => setPrompt(RANDOM_PROMPTS[Math.floor(Math.random() * RANDOM_PROMPTS.length)])} className="text-sm text-body">Shuffle random</button>
              <div className="flex gap-2">
                <button onClick={() => setOpen(false)} className="rounded-md px-3 py-2 text-sm text-body">Cancel</button>
                <button onClick={freestyle} className="rounded-md bg-signal px-3 py-2 text-sm text-onsignal">Run</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
