"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import TagPicker from "@/components/TagPicker";

// Load Milkdown (heavy) only on the client, never during SSR.
const MarkdownEditor = dynamic(() => import("@/components/MarkdownEditor"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-xs text-gray-500">
      Loading editor…
    </div>
  ),
});

interface TagSummary {
  id: string;
  name: string;
  color: string;
  meaning: string;
}

interface Annotation {
  notes: string;
  updated_at: string | null;
}

interface JobDetail {
  id: string;
  url: string;
  content_type: string;
  status: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_msg: string | null;
  drive_url: string | null;
  ai_topic: string | null;
  ai_objective: string | null;
  ai_action_points: string | null;
  ai_tools: string | null;
  ai_market_data: string | null;
  promise_gap: string | null;
  template: string | null;
  template_analysis: string | null;
}

type FetchState = "loading" | "ok" | "not_found" | "forbidden" | "error";

const STATUS_STYLES: Record<string, string> = {
  done: "bg-green-900 text-green-300",
  processing: "bg-blue-900 text-blue-300",
  queued: "bg-yellow-900 text-yellow-300",
  error: "bg-red-900 text-red-300",
};

const CONTENT_TYPE_STYLES: Record<string, string> = {
  short: "bg-purple-900 text-purple-300",
  long: "bg-indigo-900 text-indigo-300",
};

function Badge({
  label,
  styleClass,
}: {
  label: string;
  styleClass: string;
}) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${styleClass}`}
    >
      {label}
    </span>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard API unavailable — silently fail
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="rounded border border-gray-600 px-2 py-0.5 text-xs text-gray-400 hover:border-gray-400 hover:text-white transition-colors"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

function FieldCard({
  label,
  value,
  preformatted = false,
}: {
  label: string;
  value: string;
  preformatted?: boolean;
}) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">
          {label}
        </span>
        <CopyButton value={value} />
      </div>
      {preformatted ? (
        <pre className="whitespace-pre-wrap break-words text-sm text-gray-100 font-mono">
          {value}
        </pre>
      ) : (
        <p className="text-sm text-gray-100">{value}</p>
      )}
    </div>
  );
}

const ENRICHMENT_FIELDS: Array<{
  key: keyof JobDetail;
  label: string;
  preformatted?: boolean;
}> = [
  { key: "ai_topic", label: "Topic" },
  { key: "ai_objective", label: "Objective" },
  { key: "ai_action_points", label: "Action Points", preformatted: true },
  { key: "ai_tools", label: "Tools" },
  { key: "ai_market_data", label: "Market Data" },
  { key: "promise_gap", label: "Promise Gap" },
  { key: "template_analysis", label: "Template Analysis", preformatted: true },
];

export default function JobDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const [job, setJob] = useState<JobDetail | null>(null);
  const [fetchState, setFetchState] = useState<FetchState>("loading");
  const [annotation, setAnnotation] = useState<Annotation>({ notes: "", updated_at: null });
  const [annotationLoaded, setAnnotationLoaded] = useState(false);
  const [jobTags, setJobTags] = useState<TagSummary[]>([]);
  const [allTags, setAllTags] = useState<TagSummary[]>([]);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`/api/jobs/${params.id}`, { signal: controller.signal })
      .then(async (res) => {
        if (res.status === 404) {
          setFetchState("not_found");
          return;
        }
        if (res.status === 403 || res.status === 401) {
          setFetchState("forbidden");
          return;
        }
        if (!res.ok) {
          setFetchState("error");
          return;
        }
        const data: JobDetail = await res.json();
        setJob(data);
        setFetchState("ok");
      })
      .catch((err) => {
        if ((err as Error).name !== "AbortError") {
          setFetchState("error");
        }
      });

    return () => controller.abort();
  }, [params.id]);

  // Fetch annotation, job tags, and full tag library once job loads.
  useEffect(() => {
    if (fetchState !== "ok") return;
    const id = params.id;

    fetch(`/api/jobs/${id}/annotations`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (data) setAnnotation(data); setAnnotationLoaded(true); })
      .catch(() => { setAnnotationLoaded(true); });

    fetch(`/api/jobs/${id}/tags`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : [])
      .then(setJobTags)
      .catch(() => {});

    fetch("/api/controls/tags", { credentials: "include" })
      .then((r) => r.ok ? r.json() : [])
      .then(setAllTags)
      .catch(() => {});
  }, [fetchState, params.id]);

  const handleSave = useCallback(async (md: string) => {
    try {
      const res = await fetch(`/api/jobs/${params.id}/annotations`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: md }),
      });
      if (res.ok) {
        const saved: Annotation = await res.json();
        setAnnotation(saved);
      }
    } catch {
      // silently ignore network errors during auto-save
    }
  }, [params.id]);

  const refetchTags = useCallback(() => {
    fetch(`/api/jobs/${params.id}/tags`, { credentials: "include" })
      .then((r) => r.ok ? r.json() : [])
      .then(setJobTags)
      .catch(() => {});
  }, [params.id]);

  // --- Loading ---
  if (fetchState === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
        Loading…
      </div>
    );
  }

  // --- Error states ---
  if (fetchState === "not_found") {
    return (
      <div className="text-sm text-gray-400">
        Job not found.{" "}
        <Link href="/" className="text-blue-400 hover:underline">
          Back to feed
        </Link>
      </div>
    );
  }

  if (fetchState === "forbidden") {
    return (
      <div className="text-sm text-gray-400">
        Access denied.{" "}
        <Link href="/" className="text-blue-400 hover:underline">
          Back to feed
        </Link>
      </div>
    );
  }

  if (fetchState === "error" || !job) {
    return (
      <div className="text-sm text-gray-400">
        Failed to load job.{" "}
        <Link href="/" className="text-blue-400 hover:underline">
          Back to feed
        </Link>
      </div>
    );
  }

  // --- Loaded ---
  const displayTitle = job.title ?? job.url;
  const statusStyle =
    STATUS_STYLES[job.status] ?? "bg-gray-700 text-gray-300";
  const contentTypeStyle =
    CONTENT_TYPE_STYLES[job.content_type] ?? "bg-gray-700 text-gray-300";

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {/* Header */}
      <div>
        <Link
          href="/"
          className="mb-4 inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300"
        >
          <span aria-hidden="true">&#8592;</span> Back to feed
        </Link>

        <div className="flex flex-wrap items-start gap-3">
          <h1 className="flex-1 text-xl font-semibold leading-snug break-all">
            {displayTitle}
          </h1>
          <div className="flex shrink-0 items-center gap-2 pt-0.5">
            <Badge label={job.content_type} styleClass={contentTypeStyle} />
            <Badge label={job.status} styleClass={statusStyle} />
          </div>
        </div>

        <p className="mt-1 text-xs text-gray-500 break-all">{job.url}</p>
      </div>

      {/* Error message banner */}
      {job.status === "error" && job.error_msg && (
        <div className="rounded-lg border border-red-700 bg-red-950 px-4 py-3 text-sm text-red-300">
          <span className="font-semibold">Error: </span>
          {job.error_msg}
        </div>
      )}

      {/* Drive link */}
      {job.drive_url && (
        <a
          href={job.drive_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-gray-600 px-3 py-1.5 text-sm text-gray-300 hover:border-gray-400 hover:text-white transition-colors"
        >
          Open in Drive &#8599;
        </a>
      )}

      {/* Enrichment fields */}
      <div className="space-y-3">
        {ENRICHMENT_FIELDS.map(({ key, label, preformatted }) => {
          const value = job[key];
          if (value === null || value === undefined) return null;
          return (
            <FieldCard
              key={key}
              label={label}
              value={String(value)}
              preformatted={preformatted}
            />
          );
        })}
      </div>

      {/* Notes (WYSIWYG Milkdown editor — issue #88 / S5) */}
      {annotationLoaded && <MarkdownEditor initialMarkdown={annotation.notes} onSave={handleSave} />}

      {/* Tag picker (issue #88 / S5) */}
      <TagPicker
        jobId={params.id}
        jobTags={jobTags}
        allTags={allTags}
        onTagChange={refetchTags}
      />
    </div>
  );
}
