import Link from "next/link";
import { useState, type ReactNode } from "react";
import { StatusBadge } from "@/components/ui/badges";
import { DateTime } from "@/components/ui/date-time";
import type { JobSummary } from "@/components/feed/job-card";
import { JobCardTags } from "@/components/feed/job-card-tags";
import { PlatformGlyph } from "@/components/ui/platform-icon";
import { NoPreviewRing } from "@/components/ui/no-preview-ring";
import { buildJobHref } from "@/lib/job-detail-utils";

// CONTEXT.md: `Bento feed grid` / `Short grid`.
// - default: fixed aspect thumbnail (9:16 portrait / 16:9 landscape), full meta.
// - bento:   thumbnail stretches to fill the row-spanned cell (~15% vertical
//            crop on portrait — deliberate); 16:9 fallback below `sm` where
//            the grid collapses to one column and spans are off.
// - compact: Short grid at 5-up — uncropped 9:16, status badge dropped
//            (status lives in the filter pills, list view, and detail page).
export type PreviewCardVariant = "default" | "bento" | "compact";

interface PreviewCardProps {
  job: JobSummary;
  platformGlyph?: ReactNode;
  contentType?: string;
  status?: string;
  variant?: PreviewCardVariant;
  className?: string;
}

function Thumbnail({
  job,
  variant,
}: {
  job: JobSummary;
  variant: PreviewCardVariant;
}) {
  const [failed, setFailed] = useState(false);
  const display = job.title?.trim() || job.url;
  // compact = Short grid: force 9:16 regardless of thumbnail_kind so a short
  // with a failed/missing OG fetch can't break the uniform portrait wall.
  const aspectClass =
    variant === "bento"
      ? "aspect-video sm:aspect-auto sm:h-full"
      : variant === "compact" || job.thumbnail_kind === "portrait"
        ? "aspect-[9/16]"
        : "aspect-video";
  const showImage = Boolean(job.thumbnail_url) && !failed;

  return (
    <div
      className={`${aspectClass} overflow-hidden rounded-md border border-line bg-canvas`}
    >
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
        <div className="relative flex h-full w-full flex-col items-center justify-center gap-2 px-4 text-center">
          <NoPreviewRing seed={job.id} label={job.content_type} />
          {/* relative: paint above the absolutely-positioned ring */}
          <PlatformGlyph
            url={job.url}
            contentType={job.content_type}
            size={22}
            className="relative text-muted"
          />
          <span className="relative font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
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
  contentType,
  status,
  variant = "default",
  className = "",
}: PreviewCardProps) {
  const href = buildJobHref(job.id, { contentType, status });
  const display = job.title?.trim() || job.url;
  const titleText = display.length > 30 ? `${display.slice(0, 30)}…` : display;
  const compact = variant === "compact";
  const glyph =
    platformGlyph ??
    (job.content_type === "short" && !compact ? (
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
    <div
      className={`group relative flex h-full flex-col rounded-lg border border-line bg-surface p-3 transition-ui hover:border-line-strong hover:bg-raised ${className}`}
    >
      <Link
        href={href}
        aria-label={display}
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset"
      />

      <div
        className={`pointer-events-none ${
          variant === "bento" ? "sm:min-h-0 sm:flex-1" : ""
        }`}
      >
        <Thumbnail job={job} variant={variant} />
      </div>

      {/* bento: the thumbnail wrapper is the flexible region; elsewhere the
          meta block flexes so footers align across a stretched row. */}
      <div
        className={`pointer-events-none mt-3 flex min-h-0 flex-col gap-2 ${
          variant === "bento" ? "" : "flex-1"
        }`}
      >
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
            className={`min-w-0 flex-1 truncate font-medium leading-5 text-ink ${
              compact ? "text-xs" : "text-sm"
            }`}
          >
            {titleText}
          </p>
          {!compact && (
            <span className="shrink-0">
              <StatusBadge label={job.status} />
            </span>
          )}
        </div>

        {/* date&time ; tags btn (count-only, no chips) */}
        <div className="mt-auto flex items-center justify-between gap-3">
          <span className="truncate font-mono text-xs text-muted">
            <DateTime iso={job.created_at} />
          </span>
          <span className="pointer-events-auto relative z-10 shrink-0">
            <JobCardTags jobId={job.id} countOnly />
          </span>
        </div>
      </div>
    </div>
  );
}
