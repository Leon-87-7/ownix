'use client';

import { useCallback, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog';
import { GhostButton } from '@/components/ui/ghost-button';
import { apiPost, describeError } from '@/lib/fetch-utils';
import { parseBatchLinkInput } from '@/lib/parse-batch-links';
import { runWithConcurrency } from '@/lib/run-with-concurrency';
import { useHapticFeedback } from '@/lib/hooks/useHapticFeedback';
import type { AcceptedJob, SubmittedJob } from '@/components/feed/accepted-job';
import { toAcceptedJob } from '@/components/feed/accepted-job';

/** One row of live batch-paste progress (CONTEXT.md "Batch link paste"). */
interface BatchLinkResult {
  token: string;
  status: 'pending' | 'success' | 'error';
  message?: string;
}

const BATCH_LINK_CONCURRENCY = 6;

function BatchProgressRow({ row }: { row: BatchLinkResult }) {
  const paint =
    row.status === 'success'
      ? 'text-status-done'
      : row.status === 'error'
        ? 'text-status-error'
        : 'text-muted';
  const glyph =
    row.status === 'success' ? '✓' : row.status === 'error' ? '✕' : '…';

  return (
    <li className="flex items-start gap-2">
      <span aria-hidden="true" className={paint}>
        {glyph}
      </span>
      <span className="min-w-0 flex-1 truncate text-body">
        {row.token}
        {row.message && (
          <span className="ml-2 text-status-error">{row.message}</span>
        )}
      </span>
    </li>
  );
}

/**
 * "Ingest Link": files one or more pasted URLs as-is, without running them
 * through a pipeline. Owns the whole batch flow — parse, bounded-concurrency
 * submit, per-row progress — so the provider only has to hold the open flag.
 */
export function IngestLinkDialog({
  open,
  onOpenChange,
  onAccepted,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  onAccepted: (job: AcceptedJob) => void;
}) {
  const haptic = useHapticFeedback();
  const [url, setUrl] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<BatchLinkResult[]>([]);

  const patchRow = useCallback(
    (index: number, patch: Partial<BatchLinkResult>) =>
      setResults((current) =>
        current.map((row, i) => (i === index ? { ...row, ...patch } : row)),
      ),
    [],
  );

  /** Submits one already-parsed token, updating its row. Returns true on
   * success — a plain return value, not React state, so the caller can tally
   * the batch outcome without racing setState's batching. */
  const submitOne = useCallback(
    async (token: string, index: number): Promise<boolean> => {
      const result = await apiPost<SubmittedJob>(
        '/api/jobs',
        { url: token, content_type: 'link' },
        'Could not add link',
      );
      if (!result.ok) {
        patchRow(index, { status: 'error', message: result.detail });
        haptic('error');
        return false;
      }
      onAccepted(toAcceptedJob(result.data, token, 'link'));
      patchRow(index, { status: 'success' });
      haptic('success');
      return true;
    },
    [haptic, onAccepted, patchRow],
  );

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const tokens = parseBatchLinkInput(url);
    if (tokens.length === 0 || submitting) return;
    setError(null);
    setSubmitting(true);
    setResults(tokens.map((token) => ({ token, status: 'pending' as const })));

    const outcomes = await runWithConcurrency(
      tokens,
      BATCH_LINK_CONCURRENCY,
      submitOne,
    );

    setSubmitting(false);
    // A partial failure keeps the dialog open on its progress rows, so the
    // user can see which links didn't land.
    if (outcomes.every(Boolean)) {
      setUrl('');
      setResults([]);
      onOpenChange(false);
    }
  };

  const tokenCount = useMemo(
    () => parseBatchLinkInput(url).length,
    [url],
  );
  const settled = results.filter((r) => r.status !== 'pending').length;
  const buttonLabel = submitting
    ? `Ingesting ${settled}/${results.length}…`
    : tokenCount > 1
      ? `Ingest ${tokenCount} Links`
      : 'Ingest Link';

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (next) setResults([]);
        onOpenChange(next);
      }}
    >
      <DialogContent>
        <DialogTitle>Ingest Link</DialogTitle>
        <form onSubmit={submit} className="mt-4 space-y-4">
          <label className="block text-sm font-medium text-ink">
            URL
            <textarea
              value={url}
              onChange={(event) => setUrl(event.target.value)}
              rows={4}
              placeholder={
                'https://example.com\nhttps://example.com/two\n…one per line, or paste a whole list'
              }
              aria-describedby={error ? 'add-link-error' : undefined}
              className="mt-2 w-full resize-y rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm text-ink outline-none transition-ui placeholder:font-sans placeholder:text-muted focus:border-signal focus:ring-1 focus:ring-signal"
            />
          </label>
          <p className="text-xs text-muted">
            Ingest Link files each link as-is, without running it through a
            pipeline. Paste as many as you like. Each one becomes its own entry.
          </p>
          {error && (
            <p id="add-link-error" role="alert" className="text-sm text-red-400">
              {error}
            </p>
          )}
          {results.length > 0 && (
            <ul className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-line bg-canvas p-2 font-mono text-xs">
              {results.map((row, i) => (
                <BatchProgressRow key={`${row.token}-${i}`} row={row} />
              ))}
            </ul>
          )}
          <GhostButton
            type="submit"
            accent="signal"
            disabled={submitting || tokenCount === 0}
            className="h-9 bg-canvas px-3 text-sm font-medium text-signal"
          >
            {buttonLabel}
          </GhostButton>
        </form>
      </DialogContent>
    </Dialog>
  );
}
