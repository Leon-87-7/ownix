import Link from "next/link";
import { StatusBadge } from "@/components/ui/badges";
import { PlatformBadge } from "@/components/ui/platform-icon";
import { DateTime } from "@/components/ui/date-time";
import { GeneratedBadge } from "@/components/ui/generated-badge";
import { JobCardTags } from "@/components/feed/job-card-tags";
import { ShareLinkButton } from "@/components/ui/share-link-button";
import { buildJobHref, type FeedScope } from "@/lib/job-detail-utils";
import type { TagSummary } from "@/lib/hooks/useLinkTags";

export interface JobSummary {
  id: string;
  title?: string | null;
  url: string;
  content_type: string;
  status: string;
  created_at: string;
  thumbnail_url?: string | null;
  thumbnail_kind?: "landscape" | "portrait" | null;
  checklists_generated_at?: string | null;
  link_id?: string;
  /** Effective tags (job_tags ∪ link_tags), embedded by GET /api/jobs for the
   * feed's client-mode tag filter — read-only snapshot, not kept in sync with
   * live attach/detach (JobCardTags fetches its own copy for that). */
  tags?: TagSummary[];
}

interface JobCardProps {
  job: JobSummary;
  /** The Feed's active narrowing, carried into the job URL so Back can rebuild
   * it — including from a new tab, which has no history to go back to. */
  scope?: FeedScope;
}

export function JobCard({ job, scope }: JobCardProps) {
  const href = buildJobHref(job.id, scope ?? {});
  const display = job.title?.trim() || job.url;

  // Overlay link: the anchor covers the whole card (full-card click/navigate),
  // while the tag dropdown sits above it (pointer-events-auto) so its button
  // isn't an interactive descendant of the anchor (invalid HTML).
  return (
    <div className="relative rounded-lg border border-line bg-surface px-4 py-3 transition-ui hover:bg-raised">
      <Link
        href={href}
        aria-label={display}
        className="absolute inset-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-inset"
      />
      <div className="pointer-events-none flex items-start justify-between gap-3">
        <span className="flex min-w-0 flex-1 items-center gap-1.5">
          <p className="min-w-0 truncate text-sm text-ink">{display}</p>
          {job.content_type === "link" && <ShareLinkButton url={job.url} />}
        </span>
        <div className="flex shrink-0 items-center gap-1.5">
          <StatusBadge label={job.status} />
          <PlatformBadge url={job.url} contentType={job.content_type} />
          {job.checklists_generated_at && (
            <span className="pointer-events-auto">
              <GeneratedBadge />
            </span>
          )}
        </div>
      </div>
      {/* Footer: timestamp left, tag badges + dropdown right, one dense line. */}
      <div className="pointer-events-none mt-2 flex items-center justify-between gap-3">
        <p className="pointer-events-none font-mono text-xs text-muted">
          <DateTime iso={job.created_at} />
        </p>
        <div className="pointer-events-auto relative z-10">
          <JobCardTags jobId={job.id} contentType={job.content_type} linkId={job.link_id} />
        </div>
      </div>
    </div>
  );
}
