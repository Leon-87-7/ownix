'use client';

import { useEffect, useMemo, useState, type JSX, type ReactNode } from 'react';
import Link from 'next/link';
import {
  useParams,
  useRouter,
  useSearchParams,
} from 'next/navigation';
import dynamic from 'next/dynamic';
import { Check, Copy } from 'lucide-react';
import { TagMenu, TagChips } from '@/components/ui/tag-picker';
import { StatusBadge, TypeBadge } from '@/components/ui/badges';
import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobAnnotation } from '@/lib/hooks/useJobAnnotation';
import { useJobTags } from '@/lib/hooks/useJobTags';
import type { JobDetail } from '@/lib/hooks/useJobDetail';
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
} from '@/lib/job-detail-utils';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { Tooltip } from '@/components/ui/tooltip';
import { useRestrictedMode } from '@/lib/restricted/context';
import { useGoogleStatus } from '@/components/shell/google-status';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';

const MarkdownEditor = dynamic(
  () => import('@/components/ui/markdown-editor'),
  {
    ssr: false,
    loading: () => (
      <div className="rounded-lg border border-line bg-surface p-4 text-xs text-muted">
        Loading editor…
      </div>
    ),
  },
);

// --- template_analysis: JSON → readable React tree ---

function JsonValue({
  value,
}: {
  value: unknown;
}): JSX.Element | null {
  if (isEmpty(value)) return null;
  if (
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return (
      <p className="whitespace-pre-wrap break-words text-sm text-ink">
        {String(value)}
      </p>
    );
  }
  if (Array.isArray(value)) {
    const allScalar = value.every(
      (v) => typeof v !== 'object' || v === null,
    );
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
  return (
    <JsonObject
      obj={value as Record<string, unknown>}
      nested
    />
  );
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
    <div className={nested ? 'space-y-1' : 'space-y-3'}>
      {entries.map(([key, value]) => {
        const scalar =
          typeof value === 'string' ||
          typeof value === 'number' ||
          typeof value === 'boolean';
        if (nested && scalar) {
          return (
            <p
              key={key}
              className="text-sm text-ink"
            >
              <span className="font-medium text-body">
                {humanizeKey(key)}:
              </span>{' '}
              {String(value)}
            </p>
          );
        }
        return (
          <div
            key={key}
            className="space-y-1"
          >
            <h3
              className={
                nested
                  ? 'text-xs font-medium text-muted'
                  : 'text-sm font-semibold text-ink'
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
      <p className="whitespace-pre-wrap break-words text-sm text-ink">
        {raw}
      </p>
    );
  }
  if (
    parsed === null ||
    typeof parsed !== 'object' ||
    Array.isArray(parsed)
  )
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
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        {label && <span>{copied ? 'Copied!' : label}</span>}
      </button>
    </Tooltip>
  );
}

function FieldBody({
  value,
  render,
}: {
  value: string;
  render: RenderType;
}) {
  if (render === 'list') {
    const items = splitPipes(value);
    if (items.length === 0)
      return <p className="text-sm text-ink">{value}</p>;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    );
  }
  if (render === 'links') {
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
            <li
              key={link.url}
              className="space-y-1"
            >
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
  if (render === 'json') return <TemplateAnalysis raw={value} />;
  if (render === 'code')
    return (
      <pre className="overflow-x-auto whitespace-pre rounded-md bg-canvas p-3 font-mono text-xs text-ink">
        {value}
      </pre>
    );
  return (
    <p className="whitespace-pre-wrap break-words text-sm text-ink">
      {value}
    </p>
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
        <span className="font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
        <CopyButton
          value={fieldCopyText(value, render)}
          ariaLabel={`Copy ${label}`}
        />
      </div>
      <FieldBody
        value={value}
        render={render}
      />
    </div>
  );
}

type AdjacentJobs = {
  previous_id: string | null;
  next_id: string | null;
};

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    target.isContentEditable ||
    tag === 'textarea' ||
    tag === 'input' ||
    tag === 'select'
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
    'inline-flex h-10 items-center rounded-md border border-line bg-surface px-3 text-sm font-medium';
  return href ? (
    <Link
      href={href}
      className={`${base} text-body transition-ui hover:bg-raised hover:text-ink active:scale-[0.96]`}
    >
      {children}
    </Link>
  ) : (
    <span
      aria-disabled="true"
      className={`${base} text-muted opacity-50`}
    >
      {children}
    </span>
  );
}

function JobHeader({
  job,
  tags,
}: {
  job: JobDetail;
  tags?: ReactNode;
}) {
  const { restricted } = useRestrictedMode();
  const router = useRouter();
  const searchParams = useSearchParams();
  const contentType = searchParams.get('content_type') ?? undefined;
  const status = searchParams.get('status') ?? undefined;
  const scopeQuery = useMemo(
    () =>
      new URLSearchParams(
        jobScopeQuery({ contentType, status }),
      ).toString(),
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
    `/jobs/${id}${scopeQuery ? `?${scopeQuery}` : ''}`;

  useEffect(() => {
    // Adjacent nav is session-gated (/api/jobs/*) — in Restricted mode the
    // request would just 401, so skip it and leave the pager links hidden.
    if (restricted) return;
    let cancelled = false;
    const qs = scopeQuery ? `?${scopeQuery}` : '';
    void fetch(`/api/jobs/${job.id}/adjacent${qs}`)
      .then((res) =>
        res.ok
          ? res.json()
          : Promise.reject(new Error('Adjacent request failed')),
      )
      .then((payload: AdjacentJobs) => {
        if (!cancelled) setAdjacent(payload);
      })
      .catch(() => {
        if (!cancelled)
          setAdjacent({ previous_id: null, next_id: null });
      });
    return () => {
      cancelled = true;
    };
  }, [job.id, scopeQuery, restricted]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      // Modified arrows are browser/OS shortcuts (Alt+Left = history back).
      if (
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey
      )
        return;
      if (isEditableTarget(event.target)) return;
      if (event.key === 'ArrowLeft' && adjacent.previous_id) {
        event.preventDefault();
        router.push(jobHref(adjacent.previous_id));
      }
      if (event.key === 'ArrowRight' && adjacent.next_id) {
        event.preventDefault();
        router.push(jobHref(adjacent.next_id));
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
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
        <AdjacentNavLink
          href={adjacent.previous_id && jobHref(adjacent.previous_id)}
        >
          ← Previous
        </AdjacentNavLink>
        <AdjacentNavLink
          href={adjacent.next_id && jobHref(adjacent.next_id)}
        >
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
      {/* URL, then the tag row stacked below it (not squeezed beside a wrapping URL). */}
      <div className="mt-1 flex flex-col items-start gap-2">
        {/^https?:\/\//i.test(job.url) ? (
          <Tooltip
            content={job.url}
            mono
          >
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="max-w-full break-all font-mono text-xs text-muted transition-ui hover:text-signal hover:underline"
            >
              {displayUrl}
            </a>
          </Tooltip>
        ) : (
          <Tooltip
            content={job.url}
            mono
          >
            <p className="max-w-full break-all font-mono text-xs text-muted">
              {displayUrl}
            </p>
          </Tooltip>
        )}
        {tags && (
          <div className="flex w-full flex-wrap items-center justify-end gap-2">
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
  const { connected } = useGoogleStatus();
  const [folderUrl, setFolderUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!connected) {
      setFolderUrl(null);
      return;
    }
    let cancelled = false;
    void fetch('/api/google/folder')
      .then((res) => (res.ok ? res.json() : null))
      .then((data: { folder_url: string } | null) => {
        if (!cancelled) setFolderUrl(data?.folder_url ?? null);
      })
      .catch(() => {
        if (!cancelled) setFolderUrl(null);
      });
    return () => {
      cancelled = true;
    };
  }, [connected]);

  if (!job.drive_url && !hasFields && !folderUrl) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {job.drive_url && /^https?:\/\//i.test(job.drive_url) && (
          <a
            href={job.drive_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 rounded-md border border-line px-3 py-1.5 text-button font-medium text-ink transition-ui hover:bg-raised"
          >
            Open in Drive{' '}
            <OwnixShareIcon
              className="h-[18px] w-[18px]"
              aria-hidden="true"
            />
          </a>
        )}
        {folderUrl && (
          <a
            href={folderUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-button font-medium text-ink transition-ui hover:bg-raised"
          >
            <GoogleDriveIcon className="h-3.5 w-3.5" />
            Ownix folder{' '}
            <OwnixShareIcon
              className="h-[18px] w-[18px]"
              aria-hidden="true"
            />
          </a>
        )}
      </div>
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

export default function JobDetailPage() {
  // Next 16 passes `params` as a Promise to page props; reading it as a plain
  // object yields `undefined`, which sent every detail fetch to
  // /api/jobs/undefined → 404 "Job not found". useParams() is the client-side
  // hook that resolves the route id synchronously (matches doc-parser/[id]).
  const { id } = useParams<{ id: string }>();
  const { restricted } = useRestrictedMode();
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);
  const [withLinks, setWithLinks] = useState(false);
  const { job, fetchState } = useJobDetail(id, restricted);
  const { annotation, loaded, handleSave } = useJobAnnotation(
    id,
    fetchState,
    restricted,
  );
  const { jobTags, allTags, toggleTag, createTag } = useJobTags(
    id,
    fetchState,
    restricted,
  );

  if (fetchState === 'loading') {
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
  if (fetchState === 'not_found')
    return (
      <div className="text-sm text-body">
        Job not found.{' '}
        <Link
          href="/feed"
          className="text-signal hover:underline"
        >
          Back to feed
        </Link>
      </div>
    );
  if (fetchState === 'forbidden')
    return (
      <div className="text-sm text-body">
        Access denied.{' '}
        <Link
          href="/feed"
          className="text-signal hover:underline"
        >
          Back to feed
        </Link>
      </div>
    );
  if (fetchState === 'error' || !job)
    return (
      <div className="text-sm text-body">
        Failed to load job.{' '}
        <Link
          href="/feed"
          className="text-signal hover:underline"
        >
          Back to feed
        </Link>
      </div>
    );

  const fieldSet =
    job.content_type === 'short' ? SHORT_FIELDS : ENRICHMENT_FIELDS;
  const presentFields = fieldSet.filter(({ key }) => {
    const value = job[key];
    return (
      value !== null &&
      value !== undefined &&
      String(value).trim() !== ''
    );
  });

  async function handleDelete() {
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const response = await fetch(
        `/api/jobs/${id}${withLinks ? '?with_links=1' : ''}`,
        { method: 'DELETE' },
      );
      if (!response.ok) throw new Error('Job delete failed');
      if (window.history.length > 1) router.back();
      else router.push('/feed');
    } catch {
      setDeleteFailed(true);
    } finally {
      setDeleting(false);
    }
  }

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

      {job.status === 'error' && job.error_msg && (
        <div className="rounded-lg border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
          <span className="font-semibold">Error: </span>
          {job.error_msg}
        </div>
      )}

      <JobActionsBar
        job={job}
        hasFields={presentFields.length > 0}
      />

      <div className="space-y-3">
        {presentFields.map(({ key, label, render }) => (
          <FieldCard
            key={key}
            label={key === 'code' && job.code_lang ? `${label} (${job.code_lang})` : label}
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
      {!restricted && (
        <div className="border-t border-line pt-5">
          <div className="flex items-stretch gap-4 max-[620px]:flex-col">
            <div className="flex-shrink-0 space-y-2">
              <ConfirmDialog
                title="Permanently delete this job?"
                description="This removes the job and schedules its cloud files for deletion. This can't be undone."
                confirmLabel="Delete permanently"
                pending={deleting}
                onConfirm={handleDelete}
                trigger={
                  <button className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised">
                    Delete job
                  </button>
                }
              >
                {/* ADR-0046: links outlive the job by default — this is the
                    opt-in back into the old cascade. */}
                {typeof job.link_count === 'number' && job.link_count > 0 && (
                  <label className="flex items-start gap-2 text-xs text-body">
                    <input
                      type="checkbox"
                      checked={withLinks}
                      onChange={(event) => setWithLinks(event.target.checked)}
                      className="mt-0.5"
                    />
                    <span>
                      Also remove the {job.link_count}{' '}
                      {job.link_count === 1 ? 'link' : 'links'} this job added
                      to your Brain
                    </span>
                  </label>
                )}
              </ConfirmDialog>
              {deleteFailed && (
                <p className="text-xs text-status-error">
                  Couldn&apos;t delete — try again.
                </p>
              )}
            </div>
            <div className="border-l border-line max-[620px]:hidden" />
            <p className="text-sm text-body">
              Permanently removes this job, its notes, tags and Brain link, and
              its files in Drive, Sheets and storage. This can&apos;t be undone.
            </p>
          </div>
        </div>
      )}
    </PageShell>
  );
}
