'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import dynamic from 'next/dynamic';
import { TagMenu, TagChips } from '@/components/ui/tag-picker';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { Tooltip } from '@/components/ui/tooltip';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { FolderTagForm } from '@/components/feed/folder-tag-form';
import { RepoFollowupPanel } from '@/components/ui/repo-followup-panel';
import { JobHeader } from '@/components/jobs/job-header';
import { JobActionsBar } from '@/components/jobs/job-actions-bar';
import { TranscriptCard } from '@/components/jobs/transcript-card';
import { ChecklistsSection } from '@/components/jobs/checklists-section';
import { ScreenshotsSection } from '@/components/jobs/screenshots-section';
import {
  EnrichmentStatusCard,
  RunGeminiPanel,
} from '@/components/jobs/run-gemini-panel';
import { FieldCard } from '@/components/jobs/field-card';
import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobAnnotation } from '@/lib/hooks/useJobAnnotation';
import { useMergedTags } from '@/lib/hooks/useMergedTags';
import { useRestrictedMode } from '@/lib/restricted/context';
import { apiPost } from '@/lib/fetch-utils';
import { toast } from '@/lib/toast';
import { startPolling } from '@/lib/polling';
import { useHapticFeedback } from '@/lib/hooks/useHapticFeedback';
import { ENRICHMENT_FIELDS, SHORT_FIELDS } from '@/lib/job-markdown';

const MarkdownEditor = dynamic(() => import('@/components/ui/markdown-editor'), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-line bg-surface p-4 text-xs text-muted">
      Loading editor…
    </div>
  ),
});

function LoadFailure({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-sm text-body">
      {children}{' '}
      <Link href="/feed" className="text-signal hover:underline">
        Back to feed
      </Link>
    </div>
  );
}

export default function JobDetailPage() {
  // Next 16 passes `params` as a Promise to page props; reading it as a plain
  // object yields `undefined`, which sent every detail fetch to
  // /api/jobs/undefined → 404 "Job not found". useParams() is the client-side
  // hook that resolves the route id synchronously (matches doc-parser/[id]).
  const { id } = useParams<{ id: string }>();
  const { restricted } = useRestrictedMode();
  const router = useRouter();
  const haptic = useHapticFeedback();
  const enrichmentTriggered = useRef(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);
  const [withLinks, setWithLinks] = useState(false);
  const [folderTagFormOpen, setFolderTagFormOpen] = useState(false);
  const [runGeminiOpen, setRunGeminiOpen] = useState(false);
  const [runGeminiError, setRunGeminiError] = useState<string>();
  const { job, setData, fetchState, reload } = useJobDetail(id, restricted);
  const jobRef = useRef(job);
  useEffect(() => {
    jobRef.current = job;
  }, [job]);
  useEffect(() => {
    if (job?.status !== 'enriching') return;
    return startPolling(
      reload,
      () => jobRef.current?.status !== 'enriching',
      10_000,
    );
  }, [job?.status, reload]);
  useEffect(() => {
    if (!enrichmentTriggered.current || job?.status === 'enriching') return;
    if (job?.status === 'done') haptic('success');
    else if (job?.status === 'error') haptic('error');
    else return;
    enrichmentTriggered.current = false;
  }, [haptic, job?.status]);
  const { annotation, loaded, handleSave } = useJobAnnotation(
    id,
    fetchState,
    restricted,
  );
  const { jobTags, allTags, toggleTag, createTag } = useMergedTags(
    id,
    job?.content_type ?? '',
    job?.link_id,
    fetchState,
    restricted,
  );

  if (fetchState === 'loading') {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-16" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
      </PageShell>
    );
  }
  if (fetchState === 'not_found')
    return <LoadFailure>Job not found.</LoadFailure>;
  if (fetchState === 'forbidden')
    return <LoadFailure>Access denied.</LoadFailure>;
  if (fetchState === 'error' || !job)
    return <LoadFailure>Failed to load job.</LoadFailure>;

  const fieldSet =
    job.content_type === 'short' ? SHORT_FIELDS : ENRICHMENT_FIELDS;
  // Transcript renders as its own preview card (see TranscriptCard); Topic is
  // folded into the merged Title | Topic card below - drop both from the
  // generic field loop to avoid showing them twice.
  const presentFields = fieldSet.filter(({ key }) => {
    if (key === 'transcript' || key === 'ai_topic') return false;
    const value = job[key];
    return (
      value !== null && value !== undefined && String(value).trim() !== ''
    );
  });
  const titleTopicValue = [job.title?.trim(), job.ai_topic?.trim()]
    .filter(Boolean)
    .join('\n\n');
  const showRunGemini =
    !restricted &&
    job.content_type === 'long' &&
    job.status === 'transcript_done';

  async function submitRunGemini(
    template: string,
    freestylePrompt?: string,
  ) {
    setRunGeminiError(undefined);
    const result = await apiPost<{ status: string }>(
      `/api/jobs/${id}/enrich`,
      {
        template,
        freestyle_prompt:
          template === 'freestyle' ? freestylePrompt : null,
      },
      'Enrichment failed',
    );
    if (!result.ok) {
      setRunGeminiError(result.detail);
      haptic('error');
      return;
    }
    enrichmentTriggered.current = true;
    setData((current) =>
      current ? { ...current, status: 'enriching' } : current,
    );
  }

  async function handleDelete() {
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const response = await fetch(
        `/api/jobs/${id}${withLinks ? '?with_links=1' : ''}`,
        { method: 'DELETE' },
      );
      if (!response.ok) throw new Error('Job delete failed');
      haptic('success');
      toast('Job deleted');
      if (window.history.length > 1) router.back();
      else router.push('/feed');
    } catch {
      setDeleteFailed(true);
      haptic('error');
    } finally {
      setDeleting(false);
    }
  }

  return (
    <PageShell width="narrow">
      <JobHeader
        job={job}
        onTitleSaved={(title) =>
          setData((prev) => (prev ? { ...prev, title } : prev))
        }
        tags={
          <>
            <TagChips
              jobTags={jobTags}
              onRemove={(id) => toggleTag(id, true)}
            />
            <TagMenu
              jobTags={jobTags}
              allTags={allTags}
              onToggle={toggleTag}
              onCreate={createTag}
            />
          </>
        }
      />

      {job.status === 'error' && job.error_msg && (
        <div className="rounded-lg border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          <span className="font-semibold">Error: </span>
          {job.error_msg}
        </div>
      )}

      <JobActionsBar
        job={job}
        hasFields={presentFields.length > 0 || !!job.transcript?.trim()}
        enrich={
          showRunGemini
            ? {
                open: runGeminiOpen,
                onToggle: () => setRunGeminiOpen((value) => !value),
              }
            : undefined
        }
      />

      {showRunGemini && (
        <RunGeminiPanel
          open={runGeminiOpen}
          setOpen={setRunGeminiOpen}
          error={runGeminiError}
          submit={submitRunGemini}
        />
      )}
      {!restricted &&
        job.content_type === 'long' &&
        job.status === 'enriching' && <EnrichmentStatusCard />}

      {!restricted &&
        job.status === 'done' &&
        (job.content_type === 'long' || job.content_type === 'short') && (
          <RepoFollowupPanel jobId={job.id} />
        )}

      {!restricted && <ChecklistsSection job={job} />}
      {!restricted && <ScreenshotsSection job={job} reload={reload} />}

      <TranscriptCard key={job.id} job={job} restricted={restricted} />

      <div className="space-y-3">
        {titleTopicValue && (
          <FieldCard
            label="Title | Topic"
            value={titleTopicValue}
            render="text"
          />
        )}
        {presentFields.map(({ key, label, render }) => (
          <FieldCard
            key={key}
            label={
              key === 'code' && job.code_lang
                ? `${label} (${job.code_lang})`
                : label
            }
            value={String(job[key])}
            render={render}
          />
        ))}
      </div>

      {loaded &&
        (restricted ? (
          <Tooltip content="Restricted mode on">
            <div
              aria-disabled="true"
              className="rounded-lg border border-line bg-surface p-4 text-sm text-muted"
            >
              Notes stay with your own Index - sign in to write them.
            </div>
          </Tooltip>
        ) : (
          <MarkdownEditor
            initialMarkdown={annotation.notes}
            onSave={handleSave}
          />
        ))}
      {!restricted &&
        job.content_type === 'link' &&
        job.url?.startsWith('bookmarks:') && (
          <div className="border-t border-line pt-5">
            <div className="flex items-stretch gap-4 max-[620px]:flex-col">
              <div className="flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setFolderTagFormOpen(true)}
                  className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised"
                >
                  Create tags from folders
                </button>
              </div>
              <div className="border-l border-line max-[620px]:hidden" />
              <p className="text-sm text-body">
                Turn this import&apos;s bookmark folders into link tags,
                applied to every link in that folder. Safe to run any time -
                nothing is lost by skipping it now.
              </p>
            </div>
            <FolderTagForm
              jobId={id}
              open={folderTagFormOpen}
              onOpenChange={setFolderTagFormOpen}
            />
          </div>
        )}
      {!restricted && (
        <div className="border-t border-line pt-5">
          <div className="flex items-stretch gap-4 max-[620px]:flex-col">
            <div className="flex-shrink-0 space-y-2">
              <ConfirmDialog
                title="Permanently delete this job?"
                description="This removes the job and schedules its cloud files for deletion. This can't be undone."
                confirmLabel="Delete permanently"
                pending={deleting}
                onConfirm={handleDelete}
                trigger={
                  <button className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised">
                    Delete job
                  </button>
                }
              >
                {/* ADR-0046: links outlive the job by default - this is the
                    opt-in back into the old cascade. */}
                {typeof job.link_count === 'number' && job.link_count > 0 && (
                  <label className="flex items-start gap-2 text-xs text-body">
                    <input
                      type="checkbox"
                      checked={withLinks}
                      onChange={(event) => setWithLinks(event.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      Also remove the {job.link_count}{' '}
                      {job.link_count === 1 ? 'link' : 'links'} this job added
                      to your Brain
                    </span>
                  </label>
                )}
              </ConfirmDialog>
              {deleteFailed && (
                <p className="text-xs text-status-error">
                  Couldn&apos;t delete - try again.
                </p>
              )}
            </div>
            <div className="border-l border-line max-[620px]:hidden" />
            <p className="text-sm text-body">
              Permanently removes this job, its notes and tags, and its files
              in Drive, Sheets and storage. Its Brain links stay in your Index
              unless you choose to remove them below. This can&apos;t be
              undone.
            </p>
          </div>
        </div>
      )}
    </PageShell>
  );
}
