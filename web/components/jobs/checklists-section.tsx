'use client';

import { useState } from 'react';
import { Check, Copy, Download, Trash2 } from 'lucide-react';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { Tooltip } from '@/components/ui/tooltip';
import {
  CardAction,
  CardCopyAction,
  CARD_ACTION_BUTTON,
} from '@/components/ui/card-action';
import { useChecklists } from '@/lib/hooks/useChecklists';
import { useCopyFeedback } from '@/lib/hooks/useCopyFeedback';
import { usePressFeedback } from '@/lib/hooks/usePressFeedback';
import { downloadMarkdownFile } from '@/lib/download';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

// The escape hatch inside the delete dialog. `checklists_md` is the only stored
// copy (src/processors/checklists.py writes no Drive/Sheets/Brain side effects),
// so the way out is offered at the moment of the decision rather than requiring
// the foresight to have used the header buttons. Amber icons carry the emphasis
// - `.ownix-shimmer` is reserved for in-flight states (DESIGN.md), and this
// section already spends it on the "Generating..." run label.
const DIALOG_PILL_BUTTON =
  'inline-flex min-h-10 min-w-10 items-center justify-center rounded-full text-signal transition-ui hover:bg-raised hover:text-signal-bright';

function ChecklistEscapePills({
  markdown,
  jobId,
}: {
  markdown: string;
  jobId: string;
}) {
  const { copied, copy } = useCopyFeedback(markdown);
  const copyPress = usePressFeedback();
  const downloadPress = usePressFeedback();

  return (
    <div className="inline-flex items-center gap-1 rounded-full border border-line p-1">
      <Tooltip content={copied ? 'Copied' : 'Copy'}>
        <button
          type="button"
          onClick={copy}
          aria-label="Copy checklist before deleting"
          className={DIALOG_PILL_BUTTON}
          {...copyPress}
        >
          {copied ? (
            <Check className="h-4 w-4" />
          ) : (
            <Copy className="h-4 w-4" />
          )}
        </button>
      </Tooltip>
      <Tooltip content="Download .md">
        <button
          type="button"
          onClick={() =>
            downloadMarkdownFile(`checklist_${jobId.slice(-4)}.md`, markdown)
          }
          aria-label="Download checklist before deleting"
          className={DIALOG_PILL_BUTTON}
          {...downloadPress}
        >
          <Download className="h-4 w-4" />
        </button>
      </Tooltip>
    </div>
  );
}

export function ChecklistsSection({ job }: { job: JobDetail }) {
  const { generating, deleting, error, run, remove } = useChecklists(job.id);
  const [markdown, setMarkdown] = useState(job.checklists_md);
  // Tracked only to pin the delete to the checklist on screen (409 if it moved).
  const [generatedAt, setGeneratedAt] = useState(job.checklists_generated_at);

  if (
    !['short', 'long'].includes(job.content_type) ||
    !['transcript_done', 'done'].includes(job.status)
  )
    return null;

  const handleRun = async () => {
    const result = await run();
    if (result) {
      setMarkdown(result.checklists_md);
      setGeneratedAt(result.checklists_generated_at);
    }
  };

  const handleDelete = async () => {
    if (await remove(generatedAt ?? null)) {
      setMarkdown(null);
      setGeneratedAt(null);
    }
  };

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-sm font-semibold text-ink">Checklists</h2>
        {markdown && (
          <>
            <CardCopyAction value={markdown} label="Copy checklist" />
            <CardAction
              icon={Download}
              label="Download checklist"
              onClick={() =>
                downloadMarkdownFile(
                  `checklist_${job.id.slice(-4)}.md`,
                  markdown,
                )
              }
            />
          </>
        )}
        <button
          type="button"
          onClick={handleRun}
          disabled={generating || deleting}
          className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
        >
          {generating ? (
            // `.ownix-shimmer` only takes effect under
            // `prefers-reduced-motion: no-preference` - otherwise it inherits
            // the button's own `disabled:text-muted`.
            <span className="ownix-shimmer">Generating…</span>
          ) : markdown ? (
            'Regenerate'
          ) : (
            'Run Checklists'
          )}
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
      {markdown && (
        // The trash sits on this wrapper, not inside the <pre> - anchored to
        // the scroll box it would scroll out of reach on a long checklist,
        // which is exactly when it's wanted.
        <div className="relative">
          <ConfirmDialog
            title="Delete this checklist?"
            description="This clears the generated checklist and returns the job to its no-checklist state. It's the only stored copy - take it with you first."
            confirmLabel="Delete permanently"
            pending={deleting}
            onConfirm={handleDelete}
            trigger={
              <button
                type="button"
                aria-label="Delete checklist"
                // A generate in flight would write its result back over the
                // delete, silently undoing it - the POST resolves after the
                // DELETE and has no idea it raced. ponytail: same-tab guard
                // only; two tabs can still race, which needs an expected-version
                // precondition on the DELETE to close properly.
                disabled={generating}
                className={`absolute right-2 top-2 z-10 bg-canvas disabled:text-line ${CARD_ACTION_BUTTON}`}
              >
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              </button>
            }
          >
            <ChecklistEscapePills markdown={markdown} jobId={job.id} />
          </ConfirmDialog>
          <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-line bg-canvas p-4 pr-12 font-mono text-xs text-body">
            {markdown}
          </pre>
        </div>
      )}
    </section>
  );
}
