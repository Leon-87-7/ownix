import Link from "next/link";

export interface JobSummary {
  id: string;
  title?: string | null;
  url: string;
  content_type: string;
  status: string;
  created_at: string;
}

const CONTENT_TYPE_COLORS: Record<string, string> = {
  short: "bg-purple-900 text-purple-200",
  long: "bg-blue-900 text-blue-200",
  article: "bg-teal-900 text-teal-200",
  repo: "bg-orange-900 text-orange-200",
};

const STATUS_COLORS: Record<string, string> = {
  done: "bg-green-900 text-green-200",
  pending: "bg-yellow-900 text-yellow-200",
  processing: "bg-blue-900 text-blue-200",
  enriching: "bg-indigo-900 text-indigo-200",
  transcript_done: "bg-cyan-900 text-cyan-200",
  error: "bg-red-900 text-red-200",
  cancelled: "bg-gray-700 text-gray-400",
};

function Badge({
  label,
  colorClass,
}: {
  label: string;
  colorClass: string;
}) {
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${colorClass}`}
    >
      {label}
    </span>
  );
}

interface JobCardProps {
  job: JobSummary;
}

export function JobCard({ job }: JobCardProps) {
  const display = job.title?.trim() || job.url;
  const ctColor =
    CONTENT_TYPE_COLORS[job.content_type] ?? "bg-gray-700 text-gray-300";
  const stColor = STATUS_COLORS[job.status] ?? "bg-gray-700 text-gray-300";

  return (
    <Link
      href={`/jobs/${job.id}`}
      className="block rounded-lg bg-gray-800 px-4 py-3 hover:bg-gray-750 transition-colors"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="flex-1 text-sm text-gray-100 truncate" title={display}>
          {display}
        </p>
        <div className="flex shrink-0 gap-1.5">
          <Badge label={job.content_type} colorClass={ctColor} />
          <Badge label={job.status} colorClass={stColor} />
        </div>
      </div>
      <p className="mt-1 text-xs text-gray-500">
        {new Date(job.created_at).toLocaleString()}
      </p>
    </Link>
  );
}
