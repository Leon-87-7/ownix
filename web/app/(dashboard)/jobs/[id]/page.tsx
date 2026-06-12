"use client";

import { useState } from "react";
import Link from "next/link";
import dynamic from "next/dynamic";
import TagPicker from "@/components/TagPicker";
import { useJobDetail } from "@/lib/hooks/useJobDetail";
import { useJobAnnotation } from "@/lib/hooks/useJobAnnotation";
import { useJobTags } from "@/lib/hooks/useJobTags";
import type { JobDetail } from "@/lib/hooks/useJobDetail";
import {
  type RenderType,
  ENRICHMENT_FIELDS,
  splitPipes,
  humanizeKey,
  isEmpty,
  templateAnalysisToMarkdown,
  fieldCopyText,
  buildMarkdown,
} from "@/lib/job-detail-utils";

const MarkdownEditor = dynamic(() => import("@/components/MarkdownEditor"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4 text-xs text-gray-500">
      Loading editor…
    </div>
  ),
});

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

// --- Icons ---

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M8,7 L8,8 L6.5,8 C5.67157288,8 5,8.67157288 5,9.5 L5,18.5 C5,19.3284271 5.67157288,20 6.5,20 L13.5,20 C14.3284271,20 15,19.3284271 15,18.5 L15,17 L16,17 L16,18.5 C16,19.8807119 14.8807119,21 13.5,21 L6.5,21 C5.11928813,21 4,19.8807119 4,18.5 L4,9.5 C4,8.11928813 5.11928813,7 6.5,7 L8,7 Z M16,4 L10.5,4 C9.67157288,4 9,4.67157288 9,5.5 L9,14.5 C9,15.3284271 9.67157288,16 10.5,16 L17.5,16 C18.3284271,16 19,15.3284271 19,14.5 L19,7 L16.5,7 C16.2238576,7 16,6.77614237 16,6.5 L16,4 Z M20,6.52797748 L20,14.5 C20,15.8807119 18.8807119,17 17.5,17 L10.5,17 C9.11928813,17 8,15.8807119 8,14.5 L8,5.5 C8,4.11928813 9.11928813,3 10.5,3 L16.4720225,3 C16.6047688,2.99158053 16.7429463,3.03583949 16.8535534,3.14644661 L19.8535534,6.14644661 C19.9641605,6.25705373 20.0084195,6.39523125 20,6.52797748 Z M17,6 L18.2928932,6 L17,4.70710678 L17,6 Z M11.5,13 C11.2238576,13 11,12.7761424 11,12.5 C11,12.2238576 11.2238576,12 11.5,12 L13.5,12 C13.7761424,12 14,12.2238576 14,12.5 C14,12.7761424 13.7761424,13 13.5,13 L11.5,13 Z M11.5,11 C11.2238576,11 11,10.7761424 11,10.5 C11,10.2238576 11.2238576,10 11.5,10 L16.5,10 C16.7761424,10 17,10.2238576 17,10.5 C17,10.7761424 16.7761424,11 16.5,11 L11.5,11 Z M11.5,9 C11.2238576,9 11,8.77614237 11,8.5 C11,8.22385763 11.2238576,8 11.5,8 L16.5,8 C16.7761424,8 17,8.22385763 17,8.5 C17,8.77614237 16.7761424,9 16.5,9 L11.5,9 Z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={className}>
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

// --- template_analysis: JSON → readable React tree ---

function JsonValue({ value }: { value: unknown }): JSX.Element | null {
  if (isEmpty(value)) return null;
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return <p className="whitespace-pre-wrap break-words text-sm text-gray-100">{String(value)}</p>;
  }
  if (Array.isArray(value)) {
    const allScalar = value.every((v) => typeof v !== "object" || v === null);
    if (allScalar) {
      return (
        <ul className="list-disc space-y-1 pl-5 text-sm text-gray-100">
          {value.filter((v) => !isEmpty(v)).map((v, i) => <li key={i}>{String(v)}</li>)}
        </ul>
      );
    }
    return (
      <ol className="list-decimal space-y-2 pl-5 text-sm text-gray-100">
        {value.map((v, i) => <li key={i}><JsonValue value={v} /></li>)}
      </ol>
    );
  }
  return <JsonObject obj={value as Record<string, unknown>} nested />;
}

function JsonObject({ obj, nested = false }: { obj: Record<string, unknown>; nested?: boolean }): JSX.Element | null {
  const entries = Object.entries(obj).filter(([, v]) => !isEmpty(v));
  if (entries.length === 0) return null;
  return (
    <div className={nested ? "space-y-1" : "space-y-3"}>
      {entries.map(([key, value]) => {
        const scalar = typeof value === "string" || typeof value === "number" || typeof value === "boolean";
        if (nested && scalar) {
          return (
            <p key={key} className="text-sm text-gray-100">
              <span className="font-medium text-gray-300">{humanizeKey(key)}:</span>{" "}{String(value)}
            </p>
          );
        }
        return (
          <div key={key} className="space-y-1">
            <h3 className={nested ? "text-xs font-medium text-gray-400" : "text-sm font-semibold text-gray-200"}>
              {humanizeKey(key)}
            </h3>
            <JsonValue value={value} />
          </div>
        );
      })}
    </div>
  );
}

function TemplateAnalysis({ raw }: { raw: string }) {
  let parsed: unknown;
  try { parsed = JSON.parse(raw); } catch {
    return <p className="whitespace-pre-wrap break-words text-sm text-gray-100">{raw}</p>;
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) return <JsonValue value={parsed} />;
  return <JsonObject obj={parsed as Record<string, unknown>} />;
}

// --- UI pieces ---

function Badge({ label, styleClass }: { label: string; styleClass: string }) {
  return <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${styleClass}`}>{label}</span>;
}

function CopyButton({ value, ariaLabel, label }: { value: string; ariaLabel: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = async () => {
    try { await navigator.clipboard.writeText(value); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch {}
  };
  return (
    <button onClick={handleCopy} aria-label={ariaLabel} title={ariaLabel} className="inline-flex items-center gap-1.5 rounded border border-gray-600 px-2 py-1 text-xs text-gray-400 transition-colors hover:border-gray-400 hover:text-white">
      {copied ? <CheckIcon className="h-3.5 w-3.5" /> : <CopyIcon className="h-3.5 w-3.5" />}
      {label && <span>{copied ? "Copied!" : label}</span>}
    </button>
  );
}

function FieldBody({ value, render }: { value: string; render: RenderType }) {
  if (render === "list") {
    const items = splitPipes(value);
    if (items.length === 0) return <p className="text-sm text-gray-100">{value}</p>;
    return <ul className="list-disc space-y-1 pl-5 text-sm text-gray-100">{items.map((item, i) => <li key={i}>{item}</li>)}</ul>;
  }
  if (render === "json") return <TemplateAnalysis raw={value} />;
  return <p className="whitespace-pre-wrap break-words text-sm text-gray-100">{value}</p>;
}

function FieldCard({ label, value, render }: { label: string; value: string; render: RenderType }) {
  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">{label}</span>
        <CopyButton value={fieldCopyText(value, render)} ariaLabel={`Copy ${label}`} />
      </div>
      <FieldBody value={value} render={render} />
    </div>
  );
}

function JobHeader({ job }: { job: JobDetail }) {
  const displayTitle = job.title ?? job.url;
  const statusStyle = STATUS_STYLES[job.status] ?? "bg-gray-700 text-gray-300";
  const contentTypeStyle = CONTENT_TYPE_STYLES[job.content_type] ?? "bg-gray-700 text-gray-300";
  return (
    <div>
      <Link href="/" className="mb-4 inline-flex items-center gap-1 text-xs text-gray-500 hover:text-gray-300">
        <span aria-hidden="true">&#8592;</span> Back to feed
      </Link>
      <div className="flex flex-wrap items-start gap-3">
        <h1 className="flex-1 text-xl font-semibold leading-snug break-all">{displayTitle}</h1>
        <div className="flex shrink-0 items-center gap-2 pt-0.5">
          <Badge label={job.content_type} styleClass={contentTypeStyle} />
          <Badge label={job.status} styleClass={statusStyle} />
        </div>
      </div>
      {/^https?:\/\//i.test(job.url) ? (
        <a href={job.url} target="_blank" rel="noopener noreferrer" className="mt-1 block text-xs text-gray-500 break-all hover:text-blue-400 hover:underline">{job.url}</a>
      ) : (
        <p className="mt-1 text-xs text-gray-500 break-all">{job.url}</p>
      )}
    </div>
  );
}

function JobActionsBar({ job, hasFields }: { job: JobDetail; hasFields: boolean }) {
  if (!job.drive_url && !hasFields) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      {job.drive_url && /^https?:\/\//i.test(job.drive_url) ? (
        <a href={job.drive_url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-md border border-gray-600 px-3 py-1.5 text-sm text-gray-300 transition-colors hover:border-gray-400 hover:text-white">
          Open in Drive &#8599;
        </a>
      ) : <span />}
      {hasFields && <CopyButton value={buildMarkdown(job)} ariaLabel="Copy all fields as Markdown" label="Copy all" />}
    </div>
  );
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const { job, fetchState } = useJobDetail(params.id);
  const { annotation, loaded, handleSave } = useJobAnnotation(params.id, fetchState);
  const { jobTags, allTags, refetchTags } = useJobTags(params.id, fetchState);

  if (fetchState === "loading") {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-gray-600 border-t-white" />
        Loading…
      </div>
    );
  }
  if (fetchState === "not_found") return <div className="text-sm text-gray-400">Job not found. <Link href="/" className="text-blue-400 hover:underline">Back to feed</Link></div>;
  if (fetchState === "forbidden") return <div className="text-sm text-gray-400">Access denied. <Link href="/" className="text-blue-400 hover:underline">Back to feed</Link></div>;
  if (fetchState === "error" || !job) return <div className="text-sm text-gray-400">Failed to load job. <Link href="/" className="text-blue-400 hover:underline">Back to feed</Link></div>;

  const presentFields = ENRICHMENT_FIELDS.filter(({ key }) => {
    const value = job[key];
    return value !== null && value !== undefined && String(value).trim() !== "";
  });

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <JobHeader job={job} />

      {job.status === "error" && job.error_msg && (
        <div className="rounded-lg border border-red-700 bg-red-950 px-4 py-3 text-sm text-red-300">
          <span className="font-semibold">Error: </span>{job.error_msg}
        </div>
      )}

      <JobActionsBar job={job} hasFields={presentFields.length > 0} />

      <div className="space-y-3">
        {presentFields.map(({ key, label, render }) => (
          <FieldCard key={key} label={label} value={String(job[key])} render={render} />
        ))}
      </div>

      {loaded && <MarkdownEditor initialMarkdown={annotation.notes} onSave={handleSave} />}

      <TagPicker jobId={params.id} jobTags={jobTags} allTags={allTags} onTagChange={refetchTags} />
    </div>
  );
}
