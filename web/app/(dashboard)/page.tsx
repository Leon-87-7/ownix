"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Fuse from "fuse.js";

import { JobCard, type JobSummary } from "@/components/job-card";
import { StatCard } from "@/components/stat-card";
import { startPolling } from "@/lib/polling";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Stats {
  total: number;
  by_status: Record<string, number>;
  by_content_type: Record<string, number>;
}

interface JobsResponse {
  items: JobSummary[];
  total: number;
  page: number;
  limit: number;
}

// Statuses that mean "still in flight"
const IN_FLIGHT_STATUSES = new Set([
  "pending",
  "processing",
  "enriching",
  "transcript_done",
]);

// ---------------------------------------------------------------------------
// Filter options
// ---------------------------------------------------------------------------

const CONTENT_TYPE_FILTERS = [
  { label: "All", value: "" },
  { label: "Short", value: "short" },
  { label: "Long", value: "long" },
  { label: "Article", value: "article" },
  { label: "Repo", value: "repo" },
];

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Done", value: "done" },
  { label: "Pending", value: "pending" },
  { label: "Processing", value: "processing" },
  { label: "Error", value: "error" },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
        active
          ? "bg-indigo-600 text-white"
          : "bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white"
      }`}
    >
      {label}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function FeedPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [contentTypeFilter, setContentTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [searchQuery, setSearchQuery] = useState("");

  // Keep fuse instance in sync with jobs list
  const fuseRef = useRef<Fuse<JobSummary> | null>(null);
  useEffect(() => {
    fuseRef.current = new Fuse(jobs, {
      keys: ["title", "url"],
      threshold: 0.4,
    });
  }, [jobs]);

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------

  const fetchStats = useCallback(async () => {
    const res = await fetch("/api/jobs/stats");
    if (!res.ok) throw new Error("Failed to load stats");
    return (await res.json()) as Stats;
  }, []);

  const fetchJobs = useCallback(
    async (ctFilter: string, stFilter: string) => {
      const params = new URLSearchParams();
      if (ctFilter) params.set("content_type", ctFilter);
      if (stFilter) params.set("status", stFilter);
      params.set("limit", "50");
      const res = await fetch(`/api/jobs?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to load jobs");
      return (await res.json()) as JobsResponse;
    },
    [],
  );

  const loadAll = useCallback(
    async (ctFilter: string, stFilter: string) => {
      setLoading(true);
      setError(null);
      try {
        const [statsData, jobsData] = await Promise.all([
          fetchStats(),
          fetchJobs(ctFilter, stFilter),
        ]);
        setStats(statsData);
        setJobs(jobsData.items);
        setTotal(jobsData.total);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    [fetchStats, fetchJobs],
  );

  const refreshJobs = useCallback(
    async () => {
      try {
        const [statsData, jobsData] = await Promise.all([
          fetchStats(),
          fetchJobs(contentTypeFilter, statusFilter),
        ]);
        setStats(statsData);
        setJobs(jobsData.items);
        setTotal(jobsData.total);
      } catch {
        // swallow during background polling
      }
    },
    [fetchStats, fetchJobs, contentTypeFilter, statusFilter],
  );

  // Initial load
  useEffect(() => {
    loadAll(contentTypeFilter, statusFilter);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-fetch when filters change (skip first mount — handled above)
  const isFirstMount = useRef(true);
  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    loadAll(contentTypeFilter, statusFilter);
  }, [contentTypeFilter, statusFilter, loadAll]);

  // ---------------------------------------------------------------------------
  // Polling
  // ---------------------------------------------------------------------------

  const jobsRef = useRef(jobs);
  jobsRef.current = jobs;

  useEffect(() => {
    const isIdle = () =>
      jobsRef.current.every((j) => !IN_FLIGHT_STATUSES.has(j.status));

    const cancel = startPolling(refreshJobs, isIdle, 10_000);
    return cancel;
  }, [refreshJobs]);

  // ---------------------------------------------------------------------------
  // Client-side fuzzy search
  // ---------------------------------------------------------------------------

  const displayedJobs =
    searchQuery.trim() && fuseRef.current
      ? fuseRef.current.search(searchQuery).map((r) => r.item)
      : jobs;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="space-y-6">
      {/* Hero stats */}
      {stats && (
        <section>
          <h2 className="mb-3 text-lg font-semibold text-white">Overview</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Total" value={stats.total} />
            <StatCard label="Done" value={stats.by_status.done ?? 0} />
            <StatCard label="Pending" value={stats.by_status.pending ?? 0} />
            <StatCard label="Error" value={stats.by_status.error ?? 0} />
            <StatCard
              label="Processing"
              value={
                (stats.by_status.processing ?? 0) +
                (stats.by_status.enriching ?? 0) +
                (stats.by_status.transcript_done ?? 0)
              }
            />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <StatCard label="Short" value={stats.by_content_type.short ?? 0} />
            <StatCard label="Long" value={stats.by_content_type.long ?? 0} />
            <StatCard
              label="Article"
              value={stats.by_content_type.article ?? 0}
            />
            <StatCard label="Repo" value={stats.by_content_type.repo ?? 0} />
          </div>
        </section>
      )}

      {/* Search */}
      <section>
        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search by title or URL…"
          className="w-full rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
        />
      </section>

      {/* Content-type filter */}
      <section>
        <p className="mb-2 text-xs uppercase tracking-wide text-gray-500">
          Content type
        </p>
        <div className="flex flex-wrap gap-2">
          {CONTENT_TYPE_FILTERS.map(({ label, value }) => (
            <FilterButton
              key={value}
              label={label}
              active={contentTypeFilter === value}
              onClick={() => setContentTypeFilter(value)}
            />
          ))}
        </div>
      </section>

      {/* Status filter */}
      <section>
        <p className="mb-2 text-xs uppercase tracking-wide text-gray-500">
          Status
        </p>
        <div className="flex flex-wrap gap-2">
          {STATUS_FILTERS.map(({ label, value }) => (
            <FilterButton
              key={value}
              label={label}
              active={statusFilter === value}
              onClick={() => setStatusFilter(value)}
            />
          ))}
        </div>
      </section>

      {/* Job list */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">
            {searchQuery.trim()
              ? `${displayedJobs.length} result${displayedJobs.length === 1 ? "" : "s"}`
              : `${total} job${total === 1 ? "" : "s"}`}
          </h3>
          {loading && (
            <span className="text-xs text-gray-500 animate-pulse">
              Loading…
            </span>
          )}
        </div>

        {error && (
          <p className="rounded-md bg-red-900/40 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        {!loading && !error && displayedJobs.length === 0 && (
          <p className="text-sm text-gray-500">No jobs found.</p>
        )}

        <div className="space-y-2">
          {displayedJobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      </section>
    </div>
  );
}
