import Link from "next/link";
import { StatusBadge } from "@/components/badges";
import { PlatformBadge } from "@/components/platform-icon";
import { DateTime } from "@/components/date-time";
import { JobCardTags } from "@/components/job-card-tags";

export interface JobSummary {
  id: string;
  title?: string | null;
  url: string;
  content_type: string;
  status: string;
  created_at: string;
  thumbnail_url?: string | null;
  thumbnail_kind?: "landscape" | "portrait" | null;
}

interface JobCardProps {
  job: JobSummary;
}

export function JobCard({ job }: JobCardProps) {
  const display = job.title?.trim() || job.url;

  // Overlay link: the anchor covers the whole card (full-card click/navigate),
  // while the tag dropdown sits above it (pointer-events-auto) so its button
  // isn't an interactive descendant of the anchor (invalid HTML).
  return (
    <div className="relative rounded-lg border border-line bg-surface px-4 py-3 transition-ui hover:bg-raised">
      <Link href={`/jobs/${job.id}`} aria-label={display} className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset" />
      <div className="pointer-events-none flex items-start justify-between gap-3">
        <p className="min-w-0 flex-1 truncate text-sm text-ink">
          {display}
        </p>
        <div className="flex shrink-0 items-center gap-1.5">
          <StatusBadge label={job.status} />
          <PlatformBadge url={job.url} contentType={job.content_type} />
        </div>
      </div>
      {/* Footer: timestamp left, tag badges + dropdown right, one dense line. */}
      <div className="pointer-events-none mt-2 flex items-center justify-between gap-3">
        <p className="pointer-events-none font-mono text-xs text-muted">
          <DateTime iso={job.created_at} />
        </p>
        <div className="pointer-events-auto relative z-10">
          <JobCardTags jobId={job.id} />
        </div>
      </div>
    </div>
  );
}
