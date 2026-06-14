import { PreviewCard } from "@/components/feed/preview-card";
import type { JobSummary } from "@/components/job-card";

export function PreviewGrid({ jobs }: { jobs: JobSummary[] }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
      {jobs.map((job) => (
        <PreviewCard key={job.id} job={job} />
      ))}
    </div>
  );
}
