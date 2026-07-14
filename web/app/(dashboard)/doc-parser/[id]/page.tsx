'use client';

import { useParams } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Check, Copy, Download, ExternalLink, Sparkles } from 'lucide-react';
import { DocumentSourceChip } from '@/components/doc-parser/document-source-chip';
import { TelegramToggle } from '@/components/doc-parser/telegram-toggle';
import { downloadBlob } from '@/components/ui/export-modal';
import { PageShell } from '@/components/shell/page-shell';
import { Tooltip } from '@/components/ui/tooltip';

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
  return `ownix-${stem}-${kind}.${ext}`;
}

async function fetchOutputContent(output: Output) {
  const accept = output.kind === 'raw_txt' ? 'text/plain' : 'text/markdown';
  const res = await fetch(output.content_url, { headers: { Accept: accept } });
  if (!res.ok) throw new Error(`Output request failed (${res.status})`);
  return res.text();
}

function responseDetail(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) {
    return undefined;
  }
  return (payload as { detail?: unknown }).detail;
}

function extractErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === 'string') return message;
  }
  return fallback;
}

async function fetchJsonOrThrow<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (res.ok) return res.json();

  const payload = await res.json().catch(() => null);
  throw new Error(
    extractErrorMessage(responseDetail(payload), `Request failed (${res.status})`),
  );
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
        <Tooltip content={copyLabel}>
          <button
            type="button"
            onClick={copyFullOutput}
            aria-label="Copy full output"
            className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded-md transition-ui hover:text-ink active:scale-[0.96] ${actionState === 'copy_failed' ? 'text-status-error' : 'text-muted'}`}
          >
            {actionState === 'copied' ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </button>
        </Tooltip>
        <Tooltip content={downloadLabel}>
          <button
            type="button"
            onClick={downloadFullOutput}
            aria-label="Download full output"
            className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded-md transition-ui hover:text-ink active:scale-[0.96] ${actionState === 'download_failed' ? 'text-status-error' : 'text-muted'}`}
          >
            <Download className="h-4 w-4" />
          </button>
        </Tooltip>
        <Tooltip content="Open full output">
          <a
            href={output.content_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open full output"
            className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-ui hover:text-ink active:scale-[0.96]"
          >
            <ExternalLink className="h-4 w-4" />
          </a>
        </Tooltip>
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
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setErr('');
    async function load() {
      try {
        const [j, o] = await Promise.all([
          fetchJsonOrThrow<Job>(`/api/jobs/${id}`),
          fetchJsonOrThrow<Output[]>(`/api/parsed/${id}/outputs`),
        ]);
        if (cancelled) return;
        setJob(j);
        setOuts(o);
      } catch (error) {
        if (!cancelled) {
          const message =
            error instanceof Error && error.message
              ? error.message
              : 'Failed to load document. Please refresh.';
          setErr(`Failed to load document: ${message}`);
        }
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [id, reloadKey]);

  async function runAction(send: () => Promise<Response>) {
    setErr('');
    setBusy(true);
    try {
      const r = await send();
      if (!r.ok) {
        const payload = await r.json().catch(() => null);
        setErr(
          extractErrorMessage(
            responseDetail(payload),
            'Action failed. Please try again.',
          ),
        );
        return;
      }
      setReloadKey((key) => key + 1);
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

  if (!job) {
    if (err) return <p className="text-sm text-status-error" role="alert">{err}</p>;
    return null;
  }

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
        <Tooltip content="Rewrite the raw parse into a clean, structured markdown version">
          <button onClick={clean} disabled={busy} className="rounded-md bg-signal px-4 py-2 text-sm text-onsignal disabled:opacity-50">Clean</button>
        </Tooltip>
        <Tooltip content="Run your own custom prompt against this document">
          <button onClick={() => setOpen(true)} disabled={busy} className="rounded-md border border-line px-4 py-2 text-sm text-ink disabled:opacity-50">Freestyle</button>
        </Tooltip>
        {rawParse && <a href={rawParse.content_url} target="_blank" rel="noopener noreferrer" className="rounded-md border border-line px-4 py-2 text-sm text-ink">Get Markdown</a>}
        {job.url && <DocumentSourceChip source={job.url} />}
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
