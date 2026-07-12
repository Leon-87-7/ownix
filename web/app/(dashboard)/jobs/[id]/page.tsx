"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { TagMenu, TagChips } from "@/components/TagPicker";
import { StatusBadge, TypeBadge } from "@/components/badges";
import { useJobDetail } from "@/lib/hooks/useJobDetail";
import { useJobAnnotation } from "@/lib/hooks/useJobAnnotation";
import { useJobTags } from "@/lib/hooks/useJobTags";
import type { JobDetail } from "@/lib/hooks/useJobDetail";
import {
  type RenderType,
  ENRICHMENT_FIELDS,
  SHORT_FIELDS,
  splitPipes,
  humanizeKey,
  isEmpty,
  templateAnalysisToMarkdown,
  fieldCopyText,
  buildMarkdown,
  parseLinks,
  jobScopeQuery,
} from "@/lib/job-detail-utils";
import { PageShell } from "@/components/page-shell";
import { SkeletonBlock } from "@/components/feed/feed-states";
import { Tooltip } from "@/components/ui/tooltip";
import { useRestrictedMode } from "@/lib/restricted/context";

const MarkdownEditor = dynamic(() => import("@/components/MarkdownEditor"), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-line bg-surface p-4 text-xs text-muted">
      Loading editor…
    </div>
  ),
});

// --- Icons ---

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={className}
    >
      <path d="M8,7 L8,8 L6.5,8 C5.67157288,8 5,8.67157288 5,9.5 L5,18.5 C5,19.3284271 5.67157288,20 6.5,20 L13.5,20 C14.3284271,20 15,19.3284271 15,18.5 L15,17 L16,17 L16,18.5 C16,19.8807119 14.8807119,21 13.5,21 L6.5,21 C5.11928813,21 4,19.8807119 4,18.5 L4,9.5 C4,8.11928813 5.11928813,7 6.5,7 L8,7 Z M16,4 L10.5,4 C9.67157288,4 9,4.67157288 9,5.5 L9,14.5 C9,15.3284271 9.67157288,16 10.5,16 L17.5,16 C18.3284271,16 19,15.3284271 19,14.5 L19,7 L16.5,7 C16.2238576,7 16,6.77614237 16,6.5 L16,4 Z M20,6.52797748 L20,14.5 C20,15.8807119 18.8807119,17 17.5,17 L10.5,17 C9.11928813,17 8,15.8807119 8,14.5 L8,5.5 C8,4.11928813 9.11928813,3 10.5,3 L16.4720225,3 C16.6047688,2.99158053 16.7429463,3.03583949 16.8535534,3.14644661 L19.8535534,6.14644661 C19.9641605,6.25705373 20.0084195,6.39523125 20,6.52797748 Z M17,6 L18.2928932,6 L17,4.70710678 L17,6 Z M11.5,13 C11.2238576,13 11,12.7761424 11,12.5 C11,12.2238576 11.2238576,12 11.5,12 L13.5,12 C13.7761424,12 14,12.2238576 14,12.5 C14,12.7761424 13.7761424,13 13.5,13 L11.5,13 Z M11.5,11 C11.2238576,11 11,10.7761424 11,10.5 C11,10.2238576 11.2238576,10 11.5,10 L16.5,10 C16.7761424,10 17,10.2238576 17,10.5 C17,10.7761424 16.7761424,11 16.5,11 L11.5,11 Z M11.5,9 C11.2238576,9 11,8.77614237 11,8.5 C11,8.22385763 11.2238576,8 11.5,8 L16.5,8 C16.7761424,8 17,8.22385763 17,8.5 C17,8.77614237 16.7761424,9 16.5,9 L11.5,9 Z" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      <path d="M5 13l4 4L19 7" />
    </svg>
  );
}

// --- template_analysis: JSON → readable React tree ---

function JsonValue({ value }: { value: unknown }): JSX.Element | null {
  if (isEmpty(value)) return null;
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink">
        {String(value)}
      </p>
    );
  }
  if (Array.isArray(value)) {
    const allScalar = value.every((v) => typeof v !== "object" || v === null);
    if (allScalar) {
      return (
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
          {value
            .filter((v) => !isEmpty(v))
            .map((v, i) => (
              <li key={i}>{String(v)}</li>
            ))}
        </ul>
      );
    }
    return (
      <ol className="list-decimal space-y-2 pl-5 text-sm text-ink">
        {value.map((v, i) => (
          <li key={i}>
            <JsonValue value={v} />
          </li>
        ))}
      </ol>
    );
  }
  return <JsonObject obj={value as Record<string, unknown>} nested />;
}

function JsonObject({
  obj,
  nested = false,
}: {
  obj: Record<string, unknown>;
  nested?: boolean;
}): JSX.Element | null {
  const entries = Object.entries(obj).filter(([, v]) => !isEmpty(v));
  if (entries.length === 0) return null;
  return (
    <div className={nested ? "space-y-1" : "space-y-3"}>
      {entries.map(([key, value]) => {
        const scalar =
          typeof value === "string" ||
          typeof value === "number" ||
          typeof value === "boolean";
        if (nested && scalar) {
          return (
            <p key={key} className="text-sm text-ink">
              <span className="font-medium text-body">{humanizeKey(key)}:</span>{" "}
              {String(value)}
            </p>
          );
        }
        return (
          <div key={key} className="space-y-1">
            <h3
              className={
                nested
                  ? "text-xs font-medium text-muted"
                  : "text-sm font-semibold text-ink"
              }
            >
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
  try {
    parsed = JSON.parse(raw);
  } catch {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink">{raw}</p>
    );
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed))
    return <JsonValue value={parsed} />;
  return <JsonObject obj={parsed as Record<string, unknown>} />;
}

// --- UI pieces ---

function CopyButton({
  value,
  ariaLabel,
  label,
}: {
  value: string;
  ariaLabel: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {}
  };
  return (
    <Tooltip content={ariaLabel}>
      <button
        onClick={handleCopy}
        aria-label={ariaLabel}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {copied ? (
          <CheckIcon className="h-3.5 w-3.5" />
        ) : (
          <CopyIcon className="h-3.5 w-3.5" />
        )}
        {label && <span>{copied ? "Copied!" : label}</span>}
      </button>
    </Tooltip>
  );
}

function FieldBody({ value, render }: { value: string; render: RenderType }) {
  if (render === "list") {
    const items = splitPipes(value);
    if (items.length === 0) return <p className="text-sm text-ink">{value}</p>;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    );
  }
  if (render === "links") {
    const links = parseLinks(value);
    if (links.length === 0)
      return (
        <p className="whitespace-pre-wrap break-words text-sm text-ink">
          {value}
        </p>
      );
    return (
      <ul className="space-y-3 text-sm">
        {links.map((link) => {
          const label = link.label || link.url;
          return (
            <li key={link.url} className="space-y-1">
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="break-all font-medium text-signal transition-ui hover:underline"
              >
                {label}
              </a>
              <p className="break-all font-mono text-xs text-muted">
                {link.url}
              </p>
              {link.description && (
                <p className="whitespace-pre-wrap break-words text-xs text-muted">
                  {link.description}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    );
  }
  if (render === "json") return <TemplateAnalysis raw={value} />;
  return (
    <p className="whitespace-pre-wrap break-words text-sm text-ink">{value}</p>
  );
}

function FieldCard({
  label,
  value,
  render,
}: {
  label: string;
  value: string;
  render: RenderType;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
        <CopyButton
          value={fieldCopyText(value, render)}
          ariaLabel={`Copy ${label}`}
        />
      </div>
      <FieldBody value={value} render={render} />
    </div>
  );
}

type AdjacentJobs = { previous_id: string | null; next_id: string | null };

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tag === "textarea" ||
    tag === "input" ||
    tag === "select"
  );
}

// A span (not a Link with pointer-events-none) when there's no target: anchors
// stay keyboard-operable regardless of aria-disabled, so Enter would navigate to "#".
function AdjacentNavLink({
  href,
  children,
}: {
  href: string | null;
  children: ReactNode;
}) {
  const base =
    "inline-flex h-10 items-center rounded-md border border-line bg-surface px-3 text-sm font-medium";
  return href ? (
    <Link
      href={href}
      className={`${base} text-body transition-ui hover:bg-raised hover:text-ink active:scale-[0.96]`}
    >
      {children}
    </Link>
  ) : (
    <span aria-disabled="true" className={`${base} text-muted opacity-50`}>
      {children}
    </span>
  );
}

function JobHeader({ job, tags }: { job: JobDetail; tags?: ReactNode }) {
  const { restricted } = useRestrictedMode();
  const router = useRouter();
  const searchParams = useSearchParams();
  const contentType = searchParams.get("content_type") ?? undefined;
  const status = searchParams.get("status") ?? undefined;
  const scopeQuery = useMemo(
    () => new URLSearchParams(jobScopeQuery({ contentType, status })).toString(),
    [contentType, status],
  );
  const [adjacent, setAdjacent] = useState<AdjacentJobs>({
    previous_id: null,
    next_id: null,
  });
  const displayTitle = job.title?.trim() || job.url;
  const displayUrl =
    job.url.length > 40 ? `${job.url.slice(0, 40)}...` : job.url;
  const jobHref = (id: string) =>
    `/jobs/${id}${scopeQuery ? `?${scopeQuery}` : ""}`;

  useEffect(() => {
    // Adjacent nav is session-gated (/api/jobs/*) — in Restricted mode the
    // request would just 401, so skip it and leave the pager links hidden.
    if (restricted) return;
    let cancelled = false;
    const qs = scopeQuery ? `?${scopeQuery}` : "";
    void fetch(`/api/jobs/${job.id}/adjacent${qs}`)
      .then((res) =>
        res.ok
          ? res.json()
          : Promise.reject(new Error("Adjacent request failed")),
      )
      .then((payload: AdjacentJobs) => {
        if (!cancelled) setAdjacent(payload);
      })
      .catch(() => {
        if (!cancelled) setAdjacent({ previous_id: null, next_id: null });
      });
    return () => {
      cancelled = true;
    };
  }, [job.id, scopeQuery, restricted]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Modified arrows are browser/OS shortcuts (Alt+Left = history back).
      if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey)
        return;
      if (isEditableTarget(event.target)) return;
      if (event.key === "ArrowLeft" && adjacent.previous_id) {
        event.preventDefault();
        router.push(jobHref(adjacent.previous_id));
      }
      if (event.key === "ArrowRight" && adjacent.next_id) {
        event.preventDefault();
        router.push(jobHref(adjacent.next_id));
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [adjacent.previous_id, adjacent.next_id, router, scopeQuery]);
  return (
    <div>
      {/* #192: full-width 44px touch target on mobile, compact text link on desktop. */}
      <Link
        href="/feed"
        className="mb-4 flex h-11 w-full items-center gap-1.5 rounded-md border border-line bg-surface px-3 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink sm:inline-flex sm:h-auto sm:w-auto sm:rounded-none sm:border-0 sm:bg-transparent sm:px-0 sm:text-xs sm:font-normal sm:text-muted sm:hover:bg-transparent"
      >
        <span aria-hidden="true">&#8592;</span> Back to feed
      </Link>
      <div className="mb-4 flex flex-wrap gap-2">
        <AdjacentNavLink href={adjacent.previous_id && jobHref(adjacent.previous_id)}>
          ← Previous
        </AdjacentNavLink>
        <AdjacentNavLink href={adjacent.next_id && jobHref(adjacent.next_id)}>
          Next →
        </AdjacentNavLink>
      </div>
      <div className="flex flex-wrap items-start gap-3">
        <h1 className="flex-1 break-all text-xl font-semibold leading-snug text-ink">
          {displayTitle}
        </h1>
        <div className="flex shrink-0 items-center gap-2 pt-0.5">
          <TypeBadge label={job.content_type} />
          <StatusBadge label={job.status} />
        </div>
      </div>
      {/* URL on the left, tag row right-aligned under the badges. */}
      <div className="mt-1 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        {/^https?:\/\//i.test(job.url) ? (
          <Tooltip content={job.url} mono>
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="min-w-0 flex-1 break-all font-mono text-xs text-muted transition-ui hover:text-signal hover:underline"
            >
              {displayUrl}
            </a>
          </Tooltip>
        ) : (
          <Tooltip content={job.url} mono>
            <p className="min-w-0 flex-1 break-all font-mono text-xs text-muted">
              {displayUrl}
            </p>
          </Tooltip>
        )}
        {tags && (
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
            {tags}
          </div>
        )}
      </div>
    </div>
  );
}

function JobActionsBar({
  job,
  hasFields,
}: {
  job: JobDetail;
  hasFields: boolean;
}) {
  if (!job.drive_url && !hasFields) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      {job.drive_url && /^https?:\/\//i.test(job.drive_url) ? (
        <a
          href={job.drive_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised"
        >
          Open in Drive &#8599;
        </a>
      ) : (
        <span />
      )}
      {hasFields && (
        <CopyButton
          value={buildMarkdown(job)}
          ariaLabel="Copy all fields as Markdown"
          label="Copy all"
        />
      )}
    </div>
  );
}

export default function JobDetailPage({ params }: { params: { id: string } }) {
  const { restricted } = useRestrictedMode();
  const { job, fetchState } = useJobDetail(params.id, restricted);
  const { annotation, loaded, handleSave } = useJobAnnotation(
    params.id,
    fetchState,
    restricted,
  );
  const { jobTags, allTags, toggleTag, createTag } = useJobTags(
    params.id,
    fetchState,
    restricted,
  );

  if (fetchState === "loading") {
    return (
      <PageShell width="narrow">
        <div className="space-y-3">
          <SkeletonBlock className="h-16" />
          <SkeletonBlock className="h-24" />
          <SkeletonBlock className="h-24" />
        </div>
      </PageShell>
    );
  }
  if (fetchState === "not_found")
    return (
      <div className="text-sm text-body">
        Job not found.{" "}
        <Link href="/feed" className="text-signal hover:underline">
          Back to feed
        </Link>
      </div>
    );
  if (fetchState === "forbidden")
    return (
      <div className="text-sm text-body">
        Access denied.{" "}
        <Link href="/feed" className="text-signal hover:underline">
          Back to feed
        </Link>
      </div>
    );
  if (fetchState === "error" || !job)
    return (
      <div className="text-sm text-body">
        Failed to load job.{" "}
        <Link href="/feed" className="text-signal hover:underline">
          Back to feed
        </Link>
      </div>
    );

  const fieldSet =
    job.content_type === "short" ? SHORT_FIELDS : ENRICHMENT_FIELDS;
  const presentFields = fieldSet.filter(({ key }) => {
    const value = job[key];
    return value !== null && value !== undefined && String(value).trim() !== "";
  });

  return (
    <PageShell width="narrow">
      <JobHeader
        job={job}
        tags={
          <>
            <TagChips
              jobTags={jobTags}
              onRemove={(id) => toggleTag(id, true)}
            />
            <TagMenu
              jobTags={jobTags}
              allTags={allTags}
              onToggle={toggleTag}
              onCreate={createTag}
            />
          </>
        }
      />

      {job.status === "error" && job.error_msg && (
        <div className="rounded-lg border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          <span className="font-semibold">Error: </span>
          {job.error_msg}
        </div>
      )}

      <JobActionsBar job={job} hasFields={presentFields.length > 0} />

      <div className="space-y-3">
        {presentFields.map(({ key, label, render }) => (
          <FieldCard
            key={key}
            label={label}
            value={String(job[key])}
            render={render}
          />
        ))}
      </div>

      {loaded &&
        (restricted ? (
          <Tooltip content="Restricted mode on">
            <div
              aria-disabled="true"
              className="rounded-lg border border-line bg-surface p-4 text-sm text-muted"
            >
              Notes stay with your own Index — sign in to write them.
            </div>
          </Tooltip>
        ) : (
          <MarkdownEditor
            initialMarkdown={annotation.notes}
            onSave={handleSave}
          />
        ))}
    </PageShell>
  );
}
