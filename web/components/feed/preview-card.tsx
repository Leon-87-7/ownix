import Link from "next/link";
import { useState, type ReactNode } from "react";
import { StatusBadge } from "@/components/badges";
import type { JobSummary } from "@/components/job-card";
import { PlatformGlyph } from "@/components/platform-icon";

interface PreviewCardProps {
  job: JobSummary;
  platformGlyph?: ReactNode;
}

function Thumbnail({ job }: { job: JobSummary }) {
  const [failed, setFailed] = useState(false);
  const display = job.title?.trim() || job.url;
  const aspectClass = job.thumbnail_kind === "portrait" ? "aspect-[9/16]" : "aspect-video";
  const showImage = Boolean(job.thumbnail_url) && !failed;

  return (
    <div className={`${aspectClass} overflow-hidden rounded-md border border-line bg-canvas`}>
      {showImage ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={job.thumbnail_url ?? ""}
          alt=""
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      ) : (
        <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
          <PlatformGlyph url={job.url} contentType={job.content_type} size={22} className="text-muted" />
          <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
            {job.content_type || display}
          </span>
        </div>
      )}
    </div>
  );
}

export function PreviewCard({ job, platformGlyph }: PreviewCardProps) {
  const display = job.title?.trim() || job.url;
  const glyph = platformGlyph ?? (
    job.content_type === "short"
      ? <PlatformGlyph url={job.url} contentType={job.content_type} size={16} className="text-muted" />
      : null
  );

  return (
    <Link
      href={`/jobs/${job.id}`}
      className="group flex h-full flex-col rounded-lg border border-line bg-surface p-3 transition-ui hover:border-line-strong hover:bg-raised"
    >
      <Thumbnail job={job} />

      <div className="mt-3 flex min-h-0 flex-1 flex-col gap-2">
        <div className="flex items-start gap-2">
          {glyph && (
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center text-muted" aria-hidden="true">
              {glyph}
            </span>
          )}
          <p className="line-clamp-2 flex-1 text-sm font-medium leading-5 text-ink" title={display}>
            {display}
          </p>
        </div>

        <div className="mt-auto flex items-center justify-between gap-3">
          <span className="truncate font-mono text-xs text-muted" title={job.created_at}>
            {new Date(job.created_at).toLocaleString()}
          </span>
          <StatusBadge label={job.status} />
        </div>
      </div>
    </Link>
  );
}
