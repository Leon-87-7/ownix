'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Check, Copy, Download, ExternalLink, Sparkles } from 'lucide-react';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';
import { downloadBlob } from '@/components/ExportModal';
import { PageShell } from '@/components/page-shell';

const RANDOM_PROMPTS = [
  'Summarize into the 5 most important takeaways',
  'Extract all actionable steps as a checklist',
  'Explain this to a non-technical person',
];

const FEEDBACK_RESET_MS = 1500;

type Job = { id: string; title?: string; url: string; status: string; telegram_delivery: 'off' | 'on' | 'retroactive'; sheets_row_id?: string | null };
type Output = { id: string; kind: string; title: string; preview: string; content_url: string; created_at: string };
type OutputActionState = 'idle' | 'copied' | 'copy_failed' | 'download_failed';

const FILENAME_FORBIDDEN = /[/\\:*?"<>|]/g;

function outputFilename(job: Job, output: Output) {
  const stem = (job.title || job.id).replace(FILENAME_FORBIDDEN, '_') || job.id;
  const kind = output.kind.replace(FILENAME_FORBIDDEN, '_');
  const ext = output.kind === 'raw_txt' ? 'txt' : 'md';
  return `vig-${stem}-${kind}.${ext}`;
}

async function fetchOutputContent(output: Output) {
  const accept = output.kind === 'raw_txt' ? 'text/plain' : 'text/markdown';
  const res = await fetch(output.content_url, { headers: { Accept: accept } });
  if (!res.ok) throw new Error(`Output request failed (${res.status})`);
  return res.text();
}

function OutputCard({ job, output }: { job: Job; output: Output }) {
  const [actionState, setActionState] = useState<OutputActionState>('idle');

  useEffect(() => {
    if (actionState === 'idle') return;
    const timer = window.setTimeout(() => setActionState('idle'), FEEDBACK_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [actionState]);

  async function copyFullOutput() {
    try {
      const fullText = await fetchOutputContent(output);
      await navigator.clipboard.writeText(fullText);
      setActionState('copied');
    } catch {
      setActionState('copy_failed');
    }
  }

  async function downloadFullOutput() {
    try {
      const fullText = await fetchOutputContent(output);
      const mime = output.kind === 'raw_txt' ? 'text/plain' : 'text/markdown';
      downloadBlob(fullText, outputFilename(job, output), mime);
      setActionState('idle');
    } catch {
      setActionState('download_failed');
    }
  }

  const copyLabel = actionState === 'copied' ? 'Copied' : actionState === 'copy_failed' ? 'Copy failed' : 'Copy full output';
  const downloadLabel = actionState === 'download_failed' ? 'Download failed' : 'Download full output';
  const liveMessage =
    actionState === 'copied' ? 'Copied' : actionState === 'copy_failed' ? 'Copy failed' : actionState === 'download_failed' ? 'Download failed' : '';

  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-signal" />
        <h2 className="flex-1 text-sm font-semibold text-ink">{output.title || output.kind}</h2>
        <button
          type="button"
          onClick={copyFullOutput}
          aria-label="Copy full output"
          title={copyLabel}
          className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded-md transition-ui hover:text-ink active:scale-[0.96] ${actionState === 'copy_failed' ? 'text-status-error' : 'text-muted'}`}
        >
          {actionState === 'copied' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
        </button>
        <button
          type="button"
          onClick={downloadFullOutput}
          aria-label="Download full output"
          title={downloadLabel}
          className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded-md transition-ui hover:text-ink active:scale-[0.96] ${actionState === 'download_failed' ? 'text-status-error' : 'text-muted'}`}
        >
          <Download className="h-4 w-4" />
        </button>
        <a
          href={output.content_url}
          target="_blank"
          rel="noopener noreferrer"
          aria-label="Open full output"
          className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-ui hover:text-ink active:scale-[0.96]"
        >
          <ExternalLink className="h-4 w-4" />
        </a>
      </div>
      <span role="status" className="sr-only">{liveMessage}</span>
      <pre className="max-h-44 overflow-auto whitespace-pre-wrap rounded bg-canvas p-3 font-mono text-xs text-body">{output.preview}</pre>
    </article>
  );
}

export default function DocDetail() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [outs, setOuts] = useState<Output[]>([]);
  const [prompt, setPrompt] = useState(RANDOM_PROMPTS[0]);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

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

  async function runAction(send: () => Promise<Response>) {
    setErr('');
    setBusy(true);
    try {
      const r = await send();
      if (!r.ok) {
        const detail = await r.json().catch(() => null);
        setErr(detail?.detail?.message || 'Action failed. Please try again.');
        return;
      }
      await load();
    } catch {
      setErr('Network error. Please try again.');
    } finally {
      setBusy(false);
    }
  }
  async function clean() {
    await runAction(() => fetch(`/api/parsed/${id}/clean`, { method: 'POST' }));
  }
  async function freestyle() {
    setOpen(false);
    await runAction(() => fetch(`/api/parsed/${id}/freestyle`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt }) }));
  }

  if (!job) return null;

  // "Get Markdown" serves the raw parse artifact, not the JSON outputs index.
  const rawParse = outs.find((o) => o.kind === 'raw_txt');

  return (
    <PageShell>
      <header>
        <h1 className="text-2xl font-semibold text-ink">{job.title || 'Document job'}</h1>
        <p className="font-mono text-xs text-muted">{job.id}</p>
      </header>

      {err && <p className="text-sm text-status-error" role="alert">{err}</p>}

      <div className="flex flex-wrap gap-2">
        <TelegramToggle jobId={job.id} value={job.telegram_delivery} />
        <button onClick={clean} disabled={busy} className="rounded-md bg-signal px-4 py-2 text-sm text-onsignal disabled:opacity-50">Clean</button>
        <button onClick={() => setOpen(true)} disabled={busy} className="rounded-md border border-line px-4 py-2 text-sm text-ink disabled:opacity-50">Freestyle</button>
        {rawParse && <a href={rawParse.content_url} target="_blank" rel="noopener noreferrer" className="rounded-md border border-line px-4 py-2 text-sm text-ink">Get Markdown</a>}
        {job.url && <span className="rounded-md border border-line px-4 py-2 font-mono text-xs text-muted">{job.url}</span>}
      </div>

      <section className="grid gap-3 md:grid-cols-2">
        {outs.map((o) => <OutputCard key={o.id} job={job} output={o} />)}
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
    </PageShell>
  );
}
