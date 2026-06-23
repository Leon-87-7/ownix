import Link from 'next/link';
import { useState, type ReactNode } from 'react';
import { StatusBadge } from '@/components/badges';
import { DateTime } from '@/components/date-time';
import type { JobSummary } from '@/components/job-card';
import { JobCardTags } from '@/components/job-card-tags';
import { PlatformGlyph } from '@/components/platform-icon';

interface PreviewCardProps {
  job: JobSummary;
  platformGlyph?: ReactNode;
}

function Thumbnail({ job }: { job: JobSummary }) {
  const [failed, setFailed] = useState(false);
  const display = job.title?.trim() || job.url;
  const aspectClass =
    job.thumbnail_kind === 'portrait'
      ? 'aspect-[9/16]'
      : 'aspect-video';
  const showImage = Boolean(job.thumbnail_url) && !failed;

  return (
    <div
      className={`${aspectClass} overflow-hidden rounded-md border border-line bg-canvas`}
    >
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={job.thumbnail_url ?? ''}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
          <PlatformGlyph
            url={job.url}
            contentType={job.content_type}
            size={22}
            className="text-muted"
          />
          <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
            {job.content_type || display}
          </span>
        </div>
      )}
    </div>
  );
}

export function PreviewCard({
  job,
  platformGlyph,
}: PreviewCardProps) {
  const display = job.title?.trim() || job.url;
  const titleText =
    display.length > 30 ? `${display.slice(0, 30)}…` : display;
  const glyph =
    platformGlyph ??
    (job.content_type === 'short' ? (
      <PlatformGlyph
        url={job.url}
        contentType={job.content_type}
        size={16}
        className="text-muted"
      />
    ) : null);

  // Overlay link covers the card; the tag dropdown sits above it
  // (pointer-events-auto) so its button isn't nested inside the anchor.
  return (
    <div className="group relative flex h-full flex-col rounded-lg border border-line bg-surface p-3 transition-ui hover:border-line-strong hover:bg-raised">
      <Link
        href={`/jobs/${job.id}`}
        aria-label={display}
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset"
      />

      <div className="pointer-events-none">
        <Thumbnail job={job} />
      </div>

      <div className="pointer-events-none mt-3 flex min-h-0 flex-1 flex-col gap-2">
        {/* title ; status */}
        <div className="flex items-start gap-2">
          {glyph && (
            <span
              className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center text-muted"
              aria-hidden="true"
            >
              {glyph}
            </span>
          )}
          <p
            className="flex-1 truncate text-sm font-medium leading-5 text-ink"
            title={display}
          >
            {titleText}
          </p>
          <span className="shrink-0">
            <StatusBadge label={job.status} />
          </span>
        </div>

        {/* date&time ; tags btn (count-only, no chips) */}
        <div className="mt-auto flex items-center justify-between gap-3">
          <span
            className="truncate font-mono text-xs text-muted"
            title={job.created_at}
          >
            <DateTime iso={job.created_at} />
          </span>
          <span className="pointer-events-auto relative z-10 shrink-0">
            <JobCardTags
              jobId={job.id}
              countOnly
            />
          </span>
        </div>
      </div>
    </div>
  );
}
