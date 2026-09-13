'use client';

import { useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { Download, Pencil } from 'lucide-react';
import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';
import { CardAction, CardCopyAction } from '@/components/ui/card-action';
import { isSafeHttpUrl } from '@/lib/url-utils';
import { downloadMarkdownFile } from '@/lib/download';
import { jobUrlQuery, parseJobScope } from '@/lib/feed-scope';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

/** Transcript preview card - mirrors the doc-parser detail page's output cards
 * (rounded surface, capped scroll region, header actions), minus the leading
 * glyph so the title anchors the row on its own. Capped/read-only here so the
 * mobile job feed stays glanceable (PRODUCT.md "state at a glance") - editing
 * lives on its own page (see TranscriptEditPage) behind an explicit Edit tap. */
export function TranscriptCard({
  job,
  restricted,
}: {
  job: JobDetail;
  restricted: boolean;
}) {
  const searchParams = useSearchParams();
  const scopeQuery = useMemo(
    () =>
      new URLSearchParams(
        jobUrlQuery(parseJobScope(new URLSearchParams(searchParams))),
      ).toString(),
    [searchParams],
  );
  const transcript = job.transcript;
  if (!transcript || !transcript.trim()) return null;

  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="flex-1 text-sm font-semibold text-ink">Transcript</h2>
        {!restricted && (
          <CardAction
            icon={Pencil}
            href={`/jobs/${job.id}/transcript${scopeQuery ? `?${scopeQuery}` : ''}`}
            label="Edit transcript"
          />
        )}
        <CardCopyAction value={transcript} label="Copy transcript" />
        <CardAction
          icon={Download}
          label="Download transcript"
          onClick={() =>
            downloadMarkdownFile(
              `transcript_${job.id.slice(-4)}.md`,
              transcript,
            )
          }
        />
        {job.transcript_drive_url &&
          isSafeHttpUrl(job.transcript_drive_url) && (
            <CardAction
              icon={OwnixShareIcon}
              href={job.transcript_drive_url}
              external
              label="Open transcript in Drive"
            />
          )}
      </div>
      <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words rounded bg-canvas p-3 font-mono text-xs text-body">
        {transcript}
      </pre>
    </article>
  );
}
