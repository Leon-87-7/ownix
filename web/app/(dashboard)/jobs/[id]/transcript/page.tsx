'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useParams } from 'next/navigation';
import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobTranscript } from '@/lib/hooks/useJobTranscript';
import { useRestrictedMode } from '@/lib/restricted/context';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { Tooltip } from '@/components/ui/tooltip';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';

const MarkdownEditor = dynamic(
  () => import('@/components/ui/markdown-editor'),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-lg border border-line bg-surface p-4 text-xs text-muted">
        Loading editor…
      </div>
    ),
  },
);

const BackLink = ({ id }: { id: string }) => (
  <Link
    href={`/jobs/${id}`}
    className="inline-flex items-center gap-1 text-xs text-muted transition-ui hover:text-ink"
  >
    <OwnixChevronRight className="h-3.5 w-3.5 rotate-180" />
    Back to job
  </Link>
);

// Full-page transcript editor - split out from the job-detail card (see
// TranscriptCard in ../page.tsx) so the mobile job feed stays a glanceable
// capped preview and editing is an explicit, opt-in destination instead of
// blowing out every card's height.
export default function TranscriptEditPage() {
  const { id } = useParams<{ id: string }>();
  const { restricted } = useRestrictedMode();
  const { job, fetchState } = useJobDetail(id, restricted);
  const { transcript, handleSave } = useJobTranscript(
    id,
    job?.transcript ?? '',
  );

  if (fetchState === 'loading') {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-8 w-32" />
          <SkeletonBlock className="h-64" />
        </div>
      </PageShell>
    );
  }
  if (fetchState !== 'ok' || !job) {
    return (
      <div className="text-sm text-body">
        Couldn&apos;t load this job.{' '}
        <Link
          href="/feed"
          className="text-signal hover:underline"
        >
          Back to feed
        </Link>
      </div>
    );
  }

  return (
    <PageShell width="narrow">
      <BackLink id={id} />
      <h1 className="text-xl font-semibold text-ink">Transcript</h1>
      {restricted ? (
        <Tooltip content="Restricted mode on">
          <pre
            aria-disabled="true"
            className="max-h-[70vh] overflow-y-auto whitespace-pre-wrap rounded-lg border border-line bg-surface p-4 font-mono text-sm text-body"
          >
            {transcript}
          </pre>
        </Tooltip>
      ) : (
        <MarkdownEditor
          initialMarkdown={transcript}
          onSave={handleSave}
          label="Transcript"
        />
      )}
    </PageShell>
  );
}
