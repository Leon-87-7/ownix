'use client';

import { useMemo } from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobTranscript } from '@/lib/hooks/useJobTranscript';
import { useRestrictedMode } from '@/lib/restricted/context';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { Tooltip } from '@/components/ui/tooltip';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { jobScopeQuery } from '@/lib/job-detail-utils';

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

// Carries the job-list's active filter scope (content_type/status) back to
// the job detail page, matching JobHeader's own scopeQuery in ../page.tsx -
// otherwise a user who opened this from a filtered feed loses that filter.
const BackLink = ({ id }: { id: string }) => {
  const router = useRouter();
  const searchParams = useSearchParams();
  const scopeQuery = useMemo(
    () =>
      new URLSearchParams(
        jobScopeQuery({
          contentType: searchParams.get('content_type') ?? undefined,
          status: searchParams.get('status') ?? undefined,
        }),
      ).toString(),
    [searchParams],
  );
  const jobHref = `/jobs/${id}${scopeQuery ? `?${scopeQuery}` : ''}`;
  const handleBack = (event: React.MouseEvent) => {
    // Modified/non-primary clicks are the browser's own "open in new
    // tab/window" gesture - let the plain <Link href> handle those instead
    // of hijacking navigation.
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey)
      return;
    // Pushing a fresh /jobs/[id] entry here (a plain Link click) stacks a
    // duplicate on top of the one already in history - Detail's own back
    // button then pops back to Transcript instead of Feed, looping forever.
    // Popping history (like Detail's handleBackToFeed) keeps the stack flat.
    event.preventDefault();
    if (window.history.length > 1) router.back();
    else router.push(jobHref);
  };
  return (
    <Link
      href={jobHref}
      onClick={handleBack}
      className="inline-flex items-center gap-1 text-xs text-muted transition-ui hover:text-ink"
    >
      <OwnixChevronRight className="h-3.5 w-3.5 rotate-180" />
      Back to job
    </Link>
  );
};

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
