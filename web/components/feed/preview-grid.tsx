import { PreviewCard } from "@/components/feed/preview-card";
import type { JobSummary } from "@/components/feed/job-card";

// CONTEXT.md: `Bento feed grid` / `Short grid`.
// - uniform: the 3-up grid every typed tab (long/article/repo) uses.
// - bento:   All-tab grid mode — one dense 3-col grid mixing all types;
//            landscape spans 2 row-units, portrait spans 4 (exactly two
//            landscape cards tall). `grid-flow-dense` back-fills holes, so a
//            card may render a slot or two ahead of strict newest-first order
//            — deliberate, won't-fix (timestamps carry exact order). Spans
//            only apply from `sm` up; mobile is a plain 1-col stack.
// - shorts:  Short tab — uncropped 9:16 at a 2 → 3 → 5 column ladder.
export type PreviewGridVariant = "uniform" | "bento" | "shorts";

const GRID_CLASS: Record<PreviewGridVariant, string> = {
  uniform: "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3",
  bento:
    "grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 sm:grid-flow-dense sm:auto-rows-[116px]",
  shorts: "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5",
};

export function PreviewGrid({
  jobs,
  contentType,
  status,
  variant = "uniform",
  preloadIndexes,
}: {
  jobs: JobSummary[];
  contentType?: string;
  status?: string;
  variant?: PreviewGridVariant;
  /** Positions in the unfiltered feed used by the server's preload hints. */
  preloadIndexes?: ReadonlyMap<string, number>;
}) {
  return (
    <div className={GRID_CLASS[variant]}>
      {jobs.map((job, index) => (
        <PreviewCard
          key={job.id}
          job={job}
          index={
            preloadIndexes?.get(job.id) ??
            (preloadIndexes ? Number.MAX_SAFE_INTEGER : index)
          }
          contentType={contentType}
          status={status}
          variant={variant === "shorts" ? "compact" : variant === "bento" ? "bento" : "default"}
          className={
            variant === "bento"
              ? job.thumbnail_kind === "portrait"
                ? "sm:row-span-4"
                : "sm:row-span-2"
              : ""
          }
        />
      ))}
    </div>
  );
}
