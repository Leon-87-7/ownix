'use client';

import { useEffect, useState } from 'react';
import { RotateCcw } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { DriveTextLink } from '@/components/jobs/drive-text-link';
import { useHoldConfirm } from '@/lib/hooks/useHoldConfirm';
import { apiPost } from '@/lib/fetch-utils';
import { startPolling } from '@/lib/polling';
import type { JobDetail } from '@/lib/hooks/useJobDetail';

/** Videos past this length are too long to frame-extract within the job budget. */
const MAX_CAPTURE_SECONDS = 5400;

function ScreenshotsRetryButton({
  generating,
  onConfirm,
}: {
  generating: boolean;
  onConfirm: () => void;
}) {
  const { holding, startHold, cancelHold } = useHoldConfirm(500, onConfirm);

  return (
    <Tooltip content={generating ? 'Capturing…' : 'Hold to retry'}>
      <button
        type="button"
        aria-label="Retry screenshot capture"
        disabled={generating}
        onPointerDown={startHold}
        onPointerUp={cancelHold}
        onPointerLeave={cancelHold}
        onKeyDown={(e) => {
          if (e.key !== 'Enter' && e.key !== ' ') return;
          e.preventDefault();
          if (!e.repeat) startHold();
        }}
        onKeyUp={(e) => {
          if (e.key === 'Enter' || e.key === ' ') cancelHold();
        }}
        className={`relative flex h-8 w-8 items-center justify-center rounded-full border border-line text-ink transition-ui hover:bg-raised disabled:cursor-not-allowed disabled:opacity-60 ${holding ? 'retry-hold' : ''}`}
      >
        <RotateCcw
          className={`h-5 w-5 ${generating ? 'motion-safe:animate-[spin_1s_linear_infinite_reverse,ownix-logo-cycle_7s_linear_infinite]' : ''}`}
          aria-hidden="true"
        />
      </button>
    </Tooltip>
  );
}

export function ScreenshotsSection({
  job,
  reload,
}: {
  job: JobDetail;
  reload: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const generating = job.screenshots_status === 'generating';
  const hasRun = job.screenshots_status != null;
  const overLimit =
    job.video_duration_seconds != null &&
    job.video_duration_seconds > MAX_CAPTURE_SECONDS;

  useEffect(() => {
    if (!generating) return;
    return startPolling(
      reload,
      () => job.screenshots_status !== 'generating',
      2000,
    );
  }, [generating, reload, job.screenshots_status]);

  if (
    job.content_type !== 'long' ||
    !['transcript_done', 'done'].includes(job.status)
  )
    return null;

  const run = async () => {
    setError(null);
    const result = await apiPost<{ screenshots_status: string }>(
      `/api/jobs/${job.id}/screenshots`,
      {},
      'Screenshot capture failed',
    );
    if (!result.ok) setError(result.detail);
    await reload();
  };

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-title font-semibold text-ink">Screenshots</h2>
          <p className="mt-1 text-label text-muted">
            {generating
              ? 'Capturing…'
              : hasRun
                ? 'Hold the retry button to capture again.'
                : 'Informative diagrams, code, slides, and product views.'}
          </p>
        </div>
        {hasRun ? (
          <div className="flex items-center gap-2">
            {job.screenshots_drive_url && (
              <DriveTextLink
                href={job.screenshots_drive_url}
                label="Open in Drive"
                ariaLabel="Open screenshots in Drive"
              />
            )}
            <ScreenshotsRetryButton generating={generating} onConfirm={run} />
          </div>
        ) : (
          <Tooltip
            content={
              overLimit
                ? 'Available for videos up to 90 minutes'
                : 'Capture informative frames'
            }
          >
            <button
              type="button"
              onClick={run}
              disabled={generating || overLimit}
              className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
            >
              {generating ? (
                <span className="ownix-shimmer">Capturing…</span>
              ) : (
                'Capture'
              )}
            </button>
          </Tooltip>
        )}
      </div>
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
      {job.screenshots_status === 'error' && !error && (
        <p role="alert" className="text-sm text-status-error">
          Capture failed. Try again.
        </p>
      )}
    </section>
  );
}
