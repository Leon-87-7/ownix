'use client';

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type JSX,
  type ReactNode,
} from 'react';
import Link from 'next/link';
import {
  useParams,
  useRouter,
  useSearchParams,
} from 'next/navigation';
import dynamic from 'next/dynamic';
import {
  Check,
  Copy,
  Download,
  Pencil,
  RotateCcw,
} from 'lucide-react';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { TagMenu, TagChips } from '@/components/ui/tag-picker';
import { StatusBadge, TypeBadge } from '@/components/ui/badges';
import { useHoldConfirm } from '@/lib/hooks/useHoldConfirm';
import { useJobDetail } from '@/lib/hooks/useJobDetail';
import { useJobAnnotation } from '@/lib/hooks/useJobAnnotation';
import { useMergedTags } from '@/lib/hooks/useMergedTags';
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
  downloadMarkdownFile,
  isSafeHttpUrl,
} from '@/lib/job-detail-utils';
import { useChecklists } from '@/lib/hooks/useChecklists';
import { useCopyFeedback } from '@/lib/hooks/useCopyFeedback';
import { PageShell } from '@/components/shell/page-shell';
import { SkeletonBlock } from '@/components/feed/feed-states';
import { Tooltip } from '@/components/ui/tooltip';
import { CopyButton } from '@/components/ui/copy-button';
import { useRestrictedMode } from '@/lib/restricted/context';
import { useGoogleStatus } from '@/components/shell/google-status';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { FolderTagForm } from '@/components/feed/folder-tag-form';
import { apiPost, apiPut } from '@/lib/fetch-utils';
import { startPolling } from '@/lib/polling';
import { useTemplateList } from '@/lib/hooks/useTemplateList';
import { RepoFollowupPanel } from '@/components/ui/repo-followup-panel';
import { useHapticFeedback } from '@/lib/hooks/useHapticFeedback';
import { usePressFeedback } from '@/lib/hooks/usePressFeedback';

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
  const parsed = useMemo<unknown>(() => {
    try {
      return JSON.parse(raw);
    } catch {
      return undefined;
    }
  }, [raw]);
  if (parsed === undefined) {
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
    'flex flex-1 items-center justify-center px-3 text-sm font-medium';
  return href ? (
    <Link
      href={href}
      className={`${base} text-body transition-ui hover:bg-raised hover:text-ink`}
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
  onTitleSaved,
}: {
  job: JobDetail;
  tags?: ReactNode;
  onTitleSaved: (title: string | null) => void;
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
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(displayTitle);
  const [titleSaving, setTitleSaving] = useState(false);
  const [titleError, setTitleError] = useState<string>();
  const skipBlurSaveRef = useRef(false);
  useEffect(() => {
    setTitleValue(displayTitle);
  }, [job.id, displayTitle]);
  const saveTitle = async () => {
    const next = titleValue.trim();
    if (next === displayTitle) {
      setEditingTitle(false);
      return;
    }
    setTitleSaving(true);
    setTitleError(undefined);
    try {
      const data = await apiPut<{ title: string | null }>(
        `/api/jobs/${job.id}/title`,
        { title: next },
        'Title save failed',
      );
      onTitleSaved(data.title);
      setEditingTitle(false);
    } catch {
      setTitleError('Title save failed');
    } finally {
      setTitleSaving(false);
    }
  };
  const jobHref = (id: string) =>
    `/jobs/${id}${scopeQuery ? `?${scopeQuery}` : ''}`;
  const feedHref = `/feed${scopeQuery ? `?${scopeQuery}` : ''}`;
  const handleBackToFeed = () => {
    if (window.history.length > 1) router.back();
    else router.push(feedHref);
  };

  useEffect(() => {
    // Adjacent nav is session-gated (/api/jobs/*) - in Restricted mode the
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
      {/* #192: 44px touch target, icon back + segmented Previous/Next in one row, capped to mobile's width on larger screens instead of stretching full-bleed. */}
      <div className="mb-4 flex items-center gap-2 sm:max-w-xs">
        <button
          type="button"
          onClick={handleBackToFeed}
          aria-label="Back"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-line bg-surface text-body transition-ui hover:bg-raised hover:text-ink"
        >
          <OwnixChevronRight
            aria-hidden="true"
            className="h-4 w-4 rotate-180"
          />
        </button>
        <div className="flex h-11 flex-1 items-stretch overflow-hidden rounded-full border border-line bg-surface">
          <AdjacentNavLink
            href={
              adjacent.previous_id && jobHref(adjacent.previous_id)
            }
          >
            ← Previous
          </AdjacentNavLink>
          <span
            aria-hidden="true"
            className="w-px shrink-0 bg-line"
          />
          <AdjacentNavLink
            href={adjacent.next_id && jobHref(adjacent.next_id)}
          >
            Next →
          </AdjacentNavLink>
        </div>
      </div>
      <div className="flex flex-wrap items-start gap-3">
        {editingTitle ? (
          <div className="min-w-[12rem] flex-1">
            <input
              autoFocus
              value={titleValue}
              onChange={(e) => setTitleValue(e.target.value)}
              onFocus={(e) => e.target.select()}
              onBlur={() => {
                if (skipBlurSaveRef.current) {
                  skipBlurSaveRef.current = false;
                  return;
                }
                void saveTitle();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void saveTitle();
                }
                if (e.key === 'Escape') {
                  skipBlurSaveRef.current = true;
                  setTitleValue(displayTitle);
                  setEditingTitle(false);
                }
              }}
              disabled={titleSaving}
              aria-label="Job title"
              maxLength={500}
              className="w-full rounded-md border border-line bg-canvas px-2 py-1 text-xl font-semibold leading-snug text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright"
            />
            {titleError && (
              <p
                role="alert"
                className="mt-1 text-xs text-status-error"
              >
                {titleError}
              </p>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setEditingTitle(true)}
            disabled={restricted}
            aria-label="Edit title"
            className="group flex flex-1 items-start gap-1.5 break-all text-left text-xl font-semibold leading-snug text-ink disabled:cursor-default"
          >
            {displayTitle}
            {!restricted && (
              <Pencil
                aria-hidden="true"
                className="mt-1.5 h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition-ui group-hover:opacity-100 group-focus-visible:opacity-100"
              />
            )}
          </button>
        )}
        <div className="flex shrink-0 items-center gap-2 pt-0.5">
          <TypeBadge label={job.content_type} />
          <StatusBadge label={job.status} />
        </div>
      </div>
      {/* URL, then the tag row stacked below it (not squeezed beside a wrapping URL). */}
      <div className="mt-1 flex flex-col items-start gap-2">
        {isSafeHttpUrl(job.url) ? (
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
  enrich,
}: {
  job: JobDetail;
  hasFields: boolean;
  enrich?: { open: boolean; onToggle: () => void };
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

  if (!job.drive_url && !hasFields && !folderUrl && !enrich) return null;
  return (
    <div className="flex items-start gap-2">
      <div className="flex flex-col items-start gap-2">
        {job.drive_url && isSafeHttpUrl(job.drive_url) && (
          <DriveTextLink
            href={job.drive_url}
            label="Open in Drive"
          />
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
      {(hasFields || enrich) && (
        <div className="ml-auto flex flex-col items-end gap-2">
          {hasFields && (
            <CopyButton
              value={buildMarkdown(job)}
              ariaLabel="Copy all fields as Markdown"
              label="Copy all"
            />
          )}
          {enrich && (
            <button
              type="button"
              onClick={enrich.onToggle}
              aria-expanded={enrich.open}
              className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
            >
              Enrich
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// Borderless icon buttons shared by the transcript and checklist preview cards
// so both carry the same copy/download affordances.
const CARD_ACTION_BUTTON =
  'inline-flex min-h-10 min-w-10 items-center justify-center rounded-md text-muted transition-ui hover:text-ink';

function CardCopyButton({
  value,
  label,
}: {
  value: string;
  label: string;
}) {
  const { copied, copy } = useCopyFeedback(value);
  const pressFeedback = usePressFeedback();

  return (
    <Tooltip content={copied ? 'Copied' : label}>
      <button
        type="button"
        onClick={copy}
        aria-label={label}
        className={CARD_ACTION_BUTTON}
        {...pressFeedback}
      >
        {copied ? (
          <Check className="h-4 w-4" />
        ) : (
          <Copy className="h-4 w-4" />
        )}
      </button>
    </Tooltip>
  );
}

function CardEditButton({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  const pressFeedback = usePressFeedback();
  return (
    <Tooltip content={label}>
      <Link
        href={href}
        aria-label={label}
        className={CARD_ACTION_BUTTON}
        {...pressFeedback}
      >
        <Pencil className="h-4 w-4" />
      </Link>
    </Tooltip>
  );
}

function CardDownloadButton({
  onDownload,
  label,
}: {
  onDownload: () => void;
  label: string;
}) {
  const pressFeedback = usePressFeedback();
  return (
    <Tooltip content={label}>
      <button
        type="button"
        onClick={onDownload}
        aria-label={label}
        className={CARD_ACTION_BUTTON}
        {...pressFeedback}
      >
        <Download className="h-4 w-4" />
      </button>
    </Tooltip>
  );
}

function DriveTextLink({
  href,
  label,
  ariaLabel,
}: {
  href: string;
  label: string;
  ariaLabel?: string;
}) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={ariaLabel}
      className="inline-flex items-center gap-1 whitespace-nowrap rounded-md border border-line px-3 py-1.5 text-button font-medium text-ink transition-ui hover:bg-raised"
    >
      {label}{' '}
      <OwnixShareIcon
        className="h-[18px] w-[18px]"
        aria-hidden="true"
      />
    </a>
  );
}

function CardOpenButton({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  const pressFeedback = usePressFeedback();
  return (
    <Tooltip content={label}>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={label}
        className={CARD_ACTION_BUTTON}
        {...pressFeedback}
      >
        <OwnixShareIcon
          className="h-4 w-4"
          aria-hidden="true"
        />
      </a>
    </Tooltip>
  );
}

// Transcript preview card - mirrors the doc-parser detail page's output cards
// (rounded surface, capped scroll region, header actions), minus the leading
// glyph so the title anchors the row on its own. Capped/read-only here so the
// mobile job feed stays glanceable (PRODUCT.md "state at a glance") - editing
// lives on its own page (see TranscriptEditPage) behind an explicit Edit tap.
function TranscriptCard({ job, restricted }: { job: JobDetail; restricted: boolean }) {
  const searchParams = useSearchParams();
  const scopeQuery = useMemo(
    () =>
      new URLSearchParams(
        jobScopeQuery({
          contentType: searchParams.get('content_type') ?? undefined,
          status: searchParams.get('status') ?? undefined,
        }),
      ).toString(),
    [searchParams],
  );
  const transcript = job.transcript;
  if (!transcript || !transcript.trim()) return null;

  return (
    <article className="rounded-lg border border-line bg-surface p-4">
      <div className="mb-2 flex items-center gap-2">
        <h2 className="flex-1 text-sm font-semibold text-ink">
          Transcript
        </h2>
        {!restricted && (
          <CardEditButton
            href={`/jobs/${job.id}/transcript${scopeQuery ? `?${scopeQuery}` : ''}`}
            label="Edit transcript"
          />
        )}
        <CardCopyButton
          value={transcript}
          label="Copy transcript"
        />
        <CardDownloadButton
          onDownload={() =>
            downloadMarkdownFile(
              `transcript_${job.id.slice(-4)}.md`,
              transcript,
            )
          }
          label="Download transcript"
        />
        {job.transcript_drive_url && isSafeHttpUrl(job.transcript_drive_url) && (
          <CardOpenButton
            href={job.transcript_drive_url}
            label="Open transcript in Drive"
          />
        )}
      </div>
      <pre className="max-h-44 overflow-auto whitespace-pre-wrap break-words rounded bg-canvas p-3 font-mono text-xs text-body">
        {transcript}
      </pre>
    </article>
  );
}

function ChecklistsSection({ job }: { job: JobDetail }) {
  const { generating, error, run } = useChecklists(job.id);
  const [markdown, setMarkdown] = useState(job.checklists_md);

  if (
    !['short', 'long'].includes(job.content_type) ||
    !['transcript_done', 'done'].includes(job.status)
  )
    return null;

  const handleRun = async () => {
    const result = await run();
    if (result) {
      setMarkdown(result.checklists_md);
    }
  };

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <h2 className="flex-1 text-sm font-semibold text-ink">
          Checklists
        </h2>
        {markdown && (
          <>
            <CardCopyButton
              value={markdown}
              label="Copy checklist"
            />
            <CardDownloadButton
              onDownload={() =>
                downloadMarkdownFile(
                  `checklist_${job.id.slice(-4)}.md`,
                  markdown,
                )
              }
              label="Download checklist"
            />
          </>
        )}
        <button
          type="button"
          onClick={handleRun}
          disabled={generating}
          className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
        >
          {generating ? (
            // `.ownix-shimmer` only takes effect under
            // `prefers-reduced-motion: no-preference` - otherwise it inherits
            // the button's own `disabled:text-muted`.
            <span className="ownix-shimmer">Generating…</span>
          ) : markdown ? (
            'Regenerate'
          ) : (
            'Run Checklists'
          )}
        </button>
      </div>
      {error && (
        <p
          role="alert"
          className="text-sm text-status-error"
        >
          {error}
        </p>
      )}
      {markdown && (
        <pre className="max-h-[32rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-line bg-canvas p-4 font-mono text-xs text-body">
          {markdown}
        </pre>
      )}
    </section>
  );
}

function ScreenshotsSection({
  job,
  reload,
}: {
  job: JobDetail;
  reload: () => Promise<void>;
}) {
  const [error, setError] = useState<string | null>(null);
  const generating = job.screenshots_status === 'generating';
  const hasRun = job.screenshots_status != null;
  const overLimit =
    job.video_duration_seconds != null &&
    job.video_duration_seconds > 5400;

  useEffect(() => {
    if (!generating) return;
    return startPolling(
      reload,
      () => job.screenshots_status !== 'generating',
      2000,
    );
  }, [generating, reload, job.screenshots_status]);

  if (
    job.content_type !== 'long' ||
    !['transcript_done', 'done'].includes(job.status)
  )
    return null;

  const run = async () => {
    setError(null);
    try {
      const result = await apiPost<{ screenshots_status: string }>(
        `/api/jobs/${job.id}/screenshots`,
        {},
        'Screenshot capture failed',
      );
      if (!result.ok) setError(result.detail);
    } catch {
      setError('Screenshot capture failed');
    }
    await reload();
  };

  return (
    <section className="space-y-3 rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-title font-semibold text-ink">
            Screenshots
          </h2>
          <p className="mt-1 text-label text-muted">
            {generating
              ? 'Capturing…'
              : hasRun
                ? 'Hold the retry button to capture again.'
                : 'Informative diagrams, code, slides, and product views.'}
          </p>
        </div>
        {hasRun ? (
          <div className="flex items-center gap-2">
            {job.screenshots_drive_url && (
              <DriveTextLink
                href={job.screenshots_drive_url}
                label="Open in Drive"
                ariaLabel="Open screenshots in Drive"
              />
            )}
            <ScreenshotsRetryButton
              generating={generating}
              onConfirm={run}
            />
          </div>
        ) : (
          <Tooltip
            content={
              overLimit
                ? 'Available for videos up to 90 minutes'
                : 'Capture informative frames'
            }
          >
            <button
              type="button"
              onClick={run}
              disabled={generating || overLimit}
              className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
            >
              {generating ? (
                <span className="ownix-shimmer">Capturing…</span>
              ) : (
                'Capture'
              )}
            </button>
          </Tooltip>
        )}
      </div>
      {error && (
        <p
          role="alert"
          className="text-sm text-status-error"
        >
          {error}
        </p>
      )}
      {job.screenshots_status === 'error' && !error && (
        <p
          role="alert"
          className="text-sm text-status-error"
        >
          Capture failed. Try again.
        </p>
      )}
    </section>
  );
}

function ScreenshotsRetryButton({
  generating,
  onConfirm,
}: {
  generating: boolean;
  onConfirm: () => void;
}) {
  const { holding, startHold, cancelHold } = useHoldConfirm(
    500,
    onConfirm,
  );

  return (
    <Tooltip content={generating ? 'Capturing…' : 'Hold to retry'}>
      <button
        type="button"
        aria-label="Retry screenshot capture"
        disabled={generating}
        onPointerDown={startHold}
        onPointerUp={cancelHold}
        onPointerLeave={cancelHold}
        onKeyDown={(e) => {
          if (e.key !== 'Enter' && e.key !== ' ') return;
          e.preventDefault();
          if (!e.repeat) startHold();
        }}
        onKeyUp={(e) => {
          if (e.key === 'Enter' || e.key === ' ') cancelHold();
        }}
        className={`relative flex h-8 w-8 items-center justify-center rounded-full border border-line text-ink transition-ui hover:bg-raised disabled:cursor-not-allowed disabled:opacity-60 ${holding ? 'retry-hold' : ''}`}
      >
        <RotateCcw
          className={`h-5 w-5 ${generating ? 'motion-safe:animate-[spin_1s_linear_infinite_reverse,ownix-logo-cycle_7s_linear_infinite]' : ''}`}
          aria-hidden="true"
        />
      </button>
    </Tooltip>
  );
}

const GEMINI_RECIPES = [
  'summary',
  'method',
  'technical',
  'review',
  'narrative',
] as const;

function useDesktopViewport() {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const update = () => setDesktop(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);
  return desktop;
}

function RecipeChoices({
  onSubmit,
  descriptions = {},
  disabled = false,
}: {
  onSubmit: (template: string, prompt?: string) => Promise<void>;
  descriptions?: Record<string, string>;
  disabled?: boolean;
}) {
  const [freestyle, setFreestyle] = useState(false);
  const [prompt, setPrompt] = useState('');
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap justify-center gap-2">
        {GEMINI_RECIPES.map((recipe) => (
          <button
            key={recipe}
            type="button"
            disabled={disabled}
            onClick={() => void onSubmit(recipe)}
            className={`${descriptions[recipe] ? 'h-auto w-full py-2 text-left' : 'h-8'} rounded-md border border-line px-3 text-button font-medium capitalize text-ink transition-ui hover:bg-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal`}
          >
            <span className="block">{recipe}</span>
            {descriptions[recipe] && (
              <span className="mt-1 block text-sm font-normal normal-case text-body">
                {descriptions[recipe]}
              </span>
            )}
          </button>
        ))}
        <button
          type="button"
          disabled={disabled}
          onClick={() => setFreestyle(true)}
          className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
        >
          Freestyle
        </button>
      </div>
      {freestyle && (
        <div className="space-y-2">
          <label
            htmlFor="gemini-freestyle"
            className="block text-label font-medium text-body"
          >
            Freestyle instructions
          </label>
          <textarea
            id="gemini-freestyle"
            value={prompt}
            disabled={disabled}
            onChange={(event) => setPrompt(event.target.value)}
            maxLength={4000}
            rows={4}
            className="w-full rounded-md border border-line bg-canvas px-3 py-2 text-sm text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal"
          />
          <button
            type="button"
            disabled={disabled || !prompt.trim()}
            onClick={() => void onSubmit('freestyle', prompt.trim())}
            className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright disabled:bg-raised disabled:text-muted"
          >
            Run Freestyle
          </button>
        </div>
      )}
    </div>
  );
}

/** Replaces the Run Gemini button while enrichment is in flight - the button
 * disappearing with no feedback read as broken (see #528). Shimmer style
 * matches the intake console's in-flight treatment (`.ownix-shimmer`). */
function EnrichmentStatusCard() {
  return (
    <section className="rounded-lg border border-line bg-surface p-4">
      <span className="ownix-shimmer font-mono text-sm text-body">
        Gemini is enriching…
      </span>
    </section>
  );
}

/** Trigger button lives in JobActionsBar now (stacked under Copy all); this
 * panel just owns the recipe picker itself - the mobile accordion and the
 * desktop slide panel - driven by state lifted to JobDetailPage so both can
 * share one `open` toggle. */
function RunGeminiPanel({
  open,
  setOpen,
  error,
  submit,
}: {
  open: boolean;
  setOpen: (value: boolean) => void;
  error?: string;
  submit: (template: string, freestylePrompt?: string) => Promise<void>;
}) {
  const desktop = useDesktopViewport();
  const { templates } = useTemplateList();

  return (
    <section className="space-y-3">
      {error && (
        <p
          role="alert"
          className="text-sm text-status-error"
        >
          {error}
        </p>
      )}
      {!desktop && (
        <div
          aria-hidden={!open}
          inert={!open}
          className={`grid overflow-hidden transition-[grid-template-rows] duration-300 ease-out-quart motion-reduce:transition-none ${open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'}`}
        >
          <div
            data-testid="gemini-accordion"
            className={`min-h-0 overflow-hidden rounded-lg border border-line bg-surface p-4 transition-[opacity,transform] duration-300 ease-out-quart motion-reduce:transition-none ${open ? 'translate-y-0 opacity-100' : '-translate-y-2 opacity-0'}`}
          >
            <RecipeChoices onSubmit={submit} disabled={!open} />
          </div>
        </div>
      )}
      {desktop && (
        <aside
          data-testid="gemini-slide-panel"
          aria-label="Gemini recipes"
          aria-hidden={!open}
          inert={!open}
          className={`fixed inset-y-0 right-0 z-40 w-full max-w-sm overflow-y-auto border-l border-line bg-surface p-6 shadow-xl transition-transform duration-200 motion-reduce:transition-none ${open ? 'translate-x-0' : 'translate-x-full pointer-events-none'}`}
        >
          <div className="mb-5 flex items-center justify-between">
            <h2 className="text-title font-semibold text-ink">
              Choose a recipe
            </h2>
            <button
              type="button"
              disabled={!open}
              onClick={() => setOpen(false)}
              className="text-sm text-body hover:text-ink"
            >
              Close
            </button>
          </div>
          <RecipeChoices
            disabled={!open}
            onSubmit={submit}
            descriptions={Object.fromEntries(
              templates
                .filter((template) => template.is_builtin)
                .map((template) => [
                  template.name,
                  template.description,
                ]),
            )}
          />
        </aside>
      )}
    </section>
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
  const haptic = useHapticFeedback();
  const enrichmentTriggered = useRef(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteFailed, setDeleteFailed] = useState(false);
  const [withLinks, setWithLinks] = useState(false);
  const [folderTagFormOpen, setFolderTagFormOpen] = useState(false);
  const [runGeminiOpen, setRunGeminiOpen] = useState(false);
  const [runGeminiError, setRunGeminiError] = useState<string>();
  const { job, setData, fetchState, reload } = useJobDetail(
    id,
    restricted,
  );
  const jobRef = useRef(job);
  useEffect(() => {
    jobRef.current = job;
  }, [job]);
  useEffect(() => {
    if (job?.status !== 'enriching') return;
    return startPolling(
      reload,
      () => jobRef.current?.status !== 'enriching',
      10_000,
    );
  }, [job?.status, reload]);
  useEffect(() => {
    if (!enrichmentTriggered.current || job?.status === 'enriching')
      return;
    if (job?.status === 'done') haptic('success');
    else if (job?.status === 'error') haptic('error');
    else return;
    enrichmentTriggered.current = false;
  }, [haptic, job?.status]);
  const { annotation, loaded, handleSave } = useJobAnnotation(
    id,
    fetchState,
    restricted,
  );
  const { jobTags, allTags, toggleTag, createTag } = useMergedTags(
    id,
    job?.content_type ?? '',
    job?.link_id,
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
  // Transcript renders as its own preview card (see TranscriptCard); Topic is
  // folded into the merged Title | Topic card below - drop both from the
  // generic field loop to avoid showing them twice.
  const presentFields = fieldSet.filter(({ key }) => {
    if (key === 'transcript' || key === 'ai_topic') return false;
    const value = job[key];
    return (
      value !== null &&
      value !== undefined &&
      String(value).trim() !== ''
    );
  });
  const titleTopicValue = [job.title?.trim(), job.ai_topic?.trim()]
    .filter(Boolean)
    .join('\n\n');
  const showRunGemini =
    !restricted &&
    job.content_type === 'long' &&
    job.status === 'transcript_done';

  async function submitRunGemini(
    template: string,
    freestylePrompt?: string,
  ) {
    setRunGeminiError(undefined);
    let result: Awaited<ReturnType<typeof apiPost<{ status: string }>>>;
    try {
      result = await apiPost<{ status: string }>(
        `/api/jobs/${id}/enrich`,
        {
          template,
          freestyle_prompt:
            template === 'freestyle' ? freestylePrompt : null,
        },
        'Enrichment failed',
      );
    } catch {
      setRunGeminiError('Enrichment failed');
      haptic('error');
      return;
    }
    if (!result.ok) {
      setRunGeminiError(result.detail);
      haptic('error');
      return;
    }
    enrichmentTriggered.current = true;
    setData((current) =>
      current ? { ...current, status: 'enriching' } : current,
    );
  }

  async function handleDelete() {
    setDeleting(true);
    setDeleteFailed(false);
    try {
      const response = await fetch(
        `/api/jobs/${id}${withLinks ? '?with_links=1' : ''}`,
        { method: 'DELETE' },
      );
      if (!response.ok) throw new Error('Job delete failed');
      haptic('success');
      if (window.history.length > 1) router.back();
      else router.push('/feed');
    } catch {
      setDeleteFailed(true);
      haptic('error');
    } finally {
      setDeleting(false);
    }
  }

  return (
    <PageShell width="narrow">
      <JobHeader
        job={job}
        onTitleSaved={(title) =>
          setData((prev) => (prev ? { ...prev, title } : prev))
        }
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
        hasFields={
          presentFields.length > 0 || !!job.transcript?.trim()
        }
        enrich={
          showRunGemini
            ? {
                open: runGeminiOpen,
                onToggle: () => setRunGeminiOpen((value) => !value),
              }
            : undefined
        }
      />

      {showRunGemini && (
        <RunGeminiPanel
          open={runGeminiOpen}
          setOpen={setRunGeminiOpen}
          error={runGeminiError}
          submit={submitRunGemini}
        />
      )}
      {!restricted &&
        job.content_type === 'long' &&
        job.status === 'enriching' && <EnrichmentStatusCard />}

      {!restricted &&
        job.status === 'done' &&
        (job.content_type === 'long' ||
          job.content_type === 'short') && (
          <RepoFollowupPanel jobId={job.id} />
        )}

      {!restricted && <ChecklistsSection job={job} />}
      {!restricted && (
        <ScreenshotsSection
          job={job}
          reload={reload}
        />
      )}

      <TranscriptCard key={job.id} job={job} restricted={restricted} />

      <div className="space-y-3">
        {titleTopicValue && (
          <FieldCard
            label="Title | Topic"
            value={titleTopicValue}
            render="text"
          />
        )}
        {presentFields.map(({ key, label, render }) => (
          <FieldCard
            key={key}
            label={
              key === 'code' && job.code_lang
                ? `${label} (${job.code_lang})`
                : label
            }
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
              Notes stay with your own Index - sign in to write them.
            </div>
          </Tooltip>
        ) : (
          <MarkdownEditor
            initialMarkdown={annotation.notes}
            onSave={handleSave}
          />
        ))}
      {!restricted &&
        job.content_type === 'link' &&
        job.url?.startsWith('bookmarks:') && (
          <div className="border-t border-line pt-5">
            <div className="flex items-stretch gap-4 max-[620px]:flex-col">
              <div className="flex-shrink-0">
                <button
                  type="button"
                  onClick={() => setFolderTagFormOpen(true)}
                  className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised"
                >
                  Create tags from folders
                </button>
              </div>
              <div className="border-l border-line max-[620px]:hidden" />
              <p className="text-sm text-body">
                Turn this import&apos;s bookmark folders into link
                tags, applied to every link in that folder. Safe to
                run any time - nothing is lost by skipping it now.
              </p>
            </div>
            <FolderTagForm
              jobId={id}
              open={folderTagFormOpen}
              onOpenChange={setFolderTagFormOpen}
            />
          </div>
        )}
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
                {/* ADR-0046: links outlive the job by default - this is the
                    opt-in back into the old cascade. */}
                {typeof job.link_count === 'number' &&
                  job.link_count > 0 && (
                    <label className="flex items-start gap-2 text-xs text-body">
                      <input
                        type="checkbox"
                        checked={withLinks}
                        onChange={(event) =>
                          setWithLinks(event.target.checked)
                        }
                        className="mt-0.5"
                      />
                      <span>
                        Also remove the {job.link_count}{' '}
                        {job.link_count === 1 ? 'link' : 'links'} this
                        job added to your Brain
                      </span>
                    </label>
                  )}
              </ConfirmDialog>
              {deleteFailed && (
                <p className="text-xs text-status-error">
                  Couldn&apos;t delete - try again.
                </p>
              )}
            </div>
            <div className="border-l border-line max-[620px]:hidden" />
            <p className="text-sm text-body">
              Permanently removes this job, its notes and tags, and
              its files in Drive, Sheets and storage. Its Brain links
              stay in your Index unless you choose to remove them
              below. This can&apos;t be undone.
            </p>
          </div>
        </div>
      )}
    </PageShell>
  );
}
