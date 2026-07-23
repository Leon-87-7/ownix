'use client';

import { useEffect, useRef, useState } from 'react';
import { ArrowDown, ArrowUp } from 'lucide-react';
import { OwnixShareIcon } from '@/components/svg/ownix-share-icon';
import { PlatformGlyph } from '@/components/ui/platform-icon';
import { Tooltip } from '@/components/ui/tooltip';
import { TagMark, TagMenu } from '@/components/ui/tag-picker';
import PreviewMotif from '@/components/ui/preview-motif';
import { useLinkTags } from '@/lib/hooks/useLinkTags';
import {
  LINKS_PAGE_SIZES,
  type LinkRow,
  type LinksOrder,
  type LinksTableState,
  type LinksView,
  type UseLinksTableResult,
} from '@/lib/hooks/useLinksTable';

function LinksErrorBanner({ message }: { message: string }) {
  return (
    <p className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">
      {message}
    </p>
  );
}

function safeUrl(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:'
      ? url
      : undefined;
  } catch {
    return undefined;
  }
}
/** Trimmed URL (CONTEXT.md): pathname + query, scheme and host dropped — the
 * favicon carries the domain. Root-domain links show the hostname and query,
 * since a favicon alone can't identify an unknown site. */
function trimUrl(url: string): string {
  try {
    const parsed = new URL(url);
    if (parsed.pathname === '' || parsed.pathname === '/') {
      return `${parsed.hostname.replace(/^www\./, '')}${parsed.search}`;
    }
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return url;
  }
}

/** Compact dd/mm/yy — used for Last seen everywhere (mobile card + the
 * desktop URL cell it's folded into, replacing the old More button there). */
function formatDateCompact(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const dd = String(date.getDate()).padStart(2, '0');
  const mm = String(date.getMonth() + 1).padStart(2, '0');
  const yy = String(date.getFullYear()).slice(-2);
  return `${dd}/${mm}/${yy}`;
}


function LinkPreviewUnavailable({
  className,
}: {
  className: string;
}) {
  return (
    <PreviewMotif
      label="NO PREVIEW"
      className={`${className} bg-canvas px-3`}
    />
  );
}

function OgPreviewImage({
  src,
  className,
}: {
  src: string | null;
  className: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!src) return null;

  if (failed) {
    return <LinkPreviewUnavailable className={className} />;
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
      className={className}
    />
  );
}

function linkPreviewImageUrl(linkId: string): string {
  return `/api/brain/links/${encodeURIComponent(linkId)}/preview/image`;
}

/** Mobile-only: the card's More panel. Expanded order: og:image preview
 * (fetched lazily via the shared links-table selection/cache, task 397) →
 * full URL (the only place it renders on touch) → title · description →
 * provenance ("seen in a video about X" — never row identity, task 32). */
function LinkDetails({
  link,
  linksData,
  expanded,
  onToggle,
}: {
  link: LinkRow;
  linksData: UseLinksTableResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  const description = [link.title, link.description]
    .filter(Boolean)
    .join(' · ');
  const href = safeUrl(link.url);
  const { preview, previewState, selectedLinkId } = linksData;
  const previewResolved =
    selectedLinkId === link.id &&
    (previewState === 'ready' || previewState === 'error');
  const ogImageUrl =
    preview?.id === link.id && previewState === 'ready'
      ? preview.og_image_url
      : null;

  return (
    <span className="inline-flex max-w-full items-start gap-2">
      <span
        title={description || undefined}
        className={`min-w-0 text-xs text-body ${
          expanded
            ? 'whitespace-normal break-words'
            : 'max-w-[40ch] truncate sm:max-w-[60ch]'
        }`}
      >
        {expanded &&
          previewResolved &&
          (ogImageUrl ? (
            <OgPreviewImage
              key={ogImageUrl}
              src={linkPreviewImageUrl(link.id)}
              className="mb-2 h-32 w-full rounded-md border border-line object-cover"
            />
          ) : (
            <LinkPreviewUnavailable className="mb-2 h-32 w-full rounded-md border border-line" />
          ))}
        {expanded &&
          (href ? (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="mb-1 block break-all font-mono text-[11px] text-ink transition-ui hover:text-signal hover:underline"
            >
              {link.url}
            </a>
          ) : (
            <span className="mb-1 block break-all font-mono text-[11px] text-muted">
              {link.url}
            </span>
          ))}
        {description}
        {expanded && link.topic && (
          <span className="mt-1 block text-[11px] text-muted">
            From: {link.topic}
          </span>
        )}
      </span>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={onToggle}
        className="relative shrink-0 rounded border border-line px-1.5 py-0.5 text-[10px] font-medium text-muted transition-ui before:absolute before:-inset-x-2 before:-inset-y-2.5 hover:bg-raised hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96]"
      >
        {expanded ? 'Less' : 'More'}
      </button>
    </span>
  );
}

function LinkTagCluster({ link }: { link: LinkRow }) {
  const { linkTags, allTags, toggleTag, createTag } = useLinkTags(
    link.id,
    link.tags ?? [],
  );
  const trigger = (
    <button
      type="button"
      aria-label={
        linkTags.length
          ? `Edit ${linkTags.length} link tags`
          : 'Add link tag'
      }
      className="inline-flex min-h-7 min-w-7 items-center justify-center gap-1 rounded border border-line px-1.5 text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
    >
      {linkTags.length === 0 ? (
        <span className="text-sm leading-none opacity-70">+</span>
      ) : (
        linkTags.slice(0, 4).map((tag) => (
          <Tooltip
            key={tag.id}
            content={[tag.name, tag.meaning]
              .filter(Boolean)
              .join(' — ')}
          >
            <span className="inline-flex h-4 w-4 items-center justify-center">
              <TagMark
                tag={tag}
                className="h-3 w-3"
              />
            </span>
          </Tooltip>
        ))
      )}
    </button>
  );

  return (
    <TagMenu
      jobTags={linkTags}
      allTags={allTags}
      onToggle={toggleTag}
      onCreate={createTag}
      trigger={trigger}
    />
  );
}

/** Link row identity (CONTEXT.md): favicon → trimmed URL → open button.
 * Favicon + trimmed URL form one anchor; the external-link icon is a second,
 * separate button to the same URL. The full URL renders only in the anchor's
 * tooltip and the expanded More panel. */
function LinkUrl({ link }: { link: LinkRow }) {
  const href = safeUrl(link.url);
  const display = trimUrl(link.url);
  if (!href) {
    return (
      <span className="flex min-w-0 flex-1 items-center gap-2">
        <PlatformGlyph
          url={link.url}
          size={16}
          className="shrink-0 text-muted"
        />
        <span
          className="min-w-0 truncate font-mono text-xs text-muted"
          title={link.url}
        >
          {display}
        </span>
      </span>
    );
  }
  return (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <Tooltip
        content={link.url}
        mono
      >
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="flex min-w-0 items-center gap-2 font-mono text-xs text-ink transition-ui hover:text-signal hover:underline"
        >
          <PlatformGlyph
            url={link.url}
            size={16}
            className="shrink-0 text-muted"
          />
          <span className="min-w-0 truncate">{display}</span>
        </a>
      </Tooltip>
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Open ${link.url} in a new tab`}
        className="ml-auto inline-flex h-7 w-7 shrink-0 items-center justify-center rounded border border-line text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-signal focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
      >
        <OwnixShareIcon
          className="h-3.5 w-3.5"
          aria-hidden="true"
        />
      </a>
    </span>
  );
}

function TableCard({
  link,
  linksData,
  expanded,
  onToggle,
}: {
  link: LinkRow;
  linksData: UseLinksTableResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <article className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <LinkUrl link={link} />
        <LinkTagCluster link={link} />
      </div>
      <div className="mt-2 font-mono text-[11px] tabular-nums text-muted">
        Last seen{' '}
        {formatDateCompact(link.last_seen ?? link.first_seen)}
      </div>
      <div className="mt-2">
        <LinkDetails
          link={link}
          linksData={linksData}
          expanded={expanded}
          onToggle={onToggle}
        />
      </div>
    </article>
  );
}

function linksCountLabel(
  state: LinksTableState,
  query: string,
  total: number,
): string {
  if (state === 'loading' || state === 'idle') return 'loading…';
  if (query.trim()) return `${total} result${total === 1 ? '' : 's'}`;
  return `${total} link${total === 1 ? '' : 's'}`;
}

function LinkPreviewEmptyState() {
  return (
    <aside className="flex min-h-[320px] min-w-0 flex-1 items-center justify-center rounded-xl border border-line bg-surface p-4 sm:max-h-[70vh]">
      <PreviewMotif
        label="SELECT A ROW"
        ariaLabel="Select a row to preview its details"
        className="h-44 w-44"
      />
    </aside>
  );
}

function SortIcon({ order }: { order: LinksOrder }) {
  const Icon = order === 'desc' ? ArrowDown : ArrowUp;
  return (
    <Icon
      className="h-3.5 w-3.5"
      aria-hidden="true"
    />
  );
}

/** The Links tab's search input + page-size picker — rendered inside
 * FilterBar's tab row (via `searchSlot`) instead of below the "Extracted
 * links" heading, since the standard job search/filters are hidden there. */
export function LinksSearchBar({
  linksData,
}: {
  linksData: UseLinksTableResult;
}) {
  const { query, setQuery, view, viewLoaded, updateView } = linksData;
  return (
    <div className="grid w-full gap-2 sm:flex sm:items-center">
      <input
        id="links-search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          // Escape clears the filter if any, else blurs out of the field.
          if (e.key === 'Escape') {
            if (query) {
              setQuery('');
            } else {
              e.currentTarget.blur();
            }
          }
        }}
        placeholder="Filter links by URL, title, description, or exact tag…"
        aria-label="Filter extracted links"
        className="h-9 w-full min-w-0 rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none sm:flex-1"
      />
      <label className="flex items-center justify-between gap-2 text-xs font-medium text-muted sm:shrink-0 sm:justify-start">
        Page size
        <select
          value={view.size}
          disabled={!viewLoaded}
          onChange={(e) =>
            updateView({
              size: Number(e.target.value) as LinksView['size'],
            })
          }
          className="h-9 rounded-md border border-line bg-canvas pl-2 font-mono text-xs text-contrasignal transition-ui hover:border-line-strong focus:border-signal focus:outline-none disabled:opacity-50"
        >
          {LINKS_PAGE_SIZES.map((size) => (
            <option
              key={size}
              value={size}
            >
              {size}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

/** Desktop-only preview panel beside the table: the selected row's (hover or
 * ↑/↓) og:image + row metadata — this is what replaced the per-row More
 * button on desktop (task 397). */
function LinkPreviewPanel({
  linksData,
}: {
  linksData: UseLinksTableResult;
}) {
  const { data, selectedLinkId, preview, previewState } = linksData;
  const link =
    data.items.find((item) => item.id === selectedLinkId) ?? null;

  if (!link) {
    return <LinkPreviewEmptyState />;
  }

  const href = safeUrl(link.url);
  const description = [link.title, link.description]
    .filter(Boolean)
    .join(' · ');
  const ogImageUrl =
    previewState === 'ready' && preview?.id === link.id
      ? preview.og_image_url
      : null;
  const previewResolved =
    previewState === 'ready' || previewState === 'error';

  return (
    <aside className="max-h-[70vh] min-w-0 flex-1 space-y-3 overflow-y-auto rounded-xl border border-line bg-surface p-4">
      {previewResolved &&
        (ogImageUrl ? (
          <OgPreviewImage
            key={ogImageUrl}
            src={linkPreviewImageUrl(link.id)}
            className="aspect-video w-full rounded-lg border border-line object-cover"
          />
        ) : (
          <LinkPreviewUnavailable className="aspect-video w-full rounded-lg border border-line" />
        ))}
      {previewState === 'loading' && preview?.id !== link.id && (
        <div className="aspect-video w-full animate-pulse rounded-lg border border-line bg-canvas" />
      )}
      <div className="flex min-w-0 items-center gap-2">
        <PlatformGlyph
          url={link.url}
          size={16}
          className="shrink-0 text-muted"
        />
        {href ? (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="min-w-0 truncate font-mono text-xs text-ink transition-ui hover:text-signal hover:underline"
          >
            {link.url}
          </a>
        ) : (
          <span className="min-w-0 truncate font-mono text-xs text-muted">
            {link.url}
          </span>
        )}
      </div>
      {description && (
        <p className="text-sm text-body">{description}</p>
      )}
      {link.topic && (
        <p className="text-xs text-muted">From: {link.topic}</p>
      )}
      {link.tags && link.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {link.tags.map((tag) => (
            <Tooltip
              key={tag.id}
              content={[tag.name, tag.meaning]
                .filter(Boolean)
                .join(' — ')}
            >
              <span className="inline-flex items-center gap-1 rounded border border-line px-1.5 py-0.5 text-[11px] text-body">
                <TagMark
                  tag={tag}
                  className="h-3 w-3"
                />
                {tag.name}
              </span>
            </Tooltip>
          ))}
        </div>
      )}
    </aside>
  );
}

export function LinksTable({
  linksData,
}: {
  linksData: UseLinksTableResult;
}) {
  const {
    query,
    view,
    viewLoaded,
    toggleOrder,
    data,
    state,
    message,
    page,
    setPage,
    jumpPage,
    setJumpPage,
    submitJump,
    pageCount,
    currentPage,
    start,
    end,
    hasPrevious,
    hasNext,
    selectedLinkId,
    selectLink,
    hoverLink,
    cancelHover,
    selectAdjacent,
  } = linksData;
  const pending = state === 'loading' || state === 'idle';
  const [expandedLinkId, setExpandedLinkId] = useState<string | null>(
    null,
  );

  const toggleMobileDetails = (linkId: string) => {
    const opening = expandedLinkId !== linkId;
    setExpandedLinkId(opening ? linkId : null);
    if (opening) selectLink(linkId);
  };

  const selectedRowRef = useRef<HTMLTableRowElement | null>(null);
  const keyboardNavigationRef = useRef(false);
  useEffect(() => {
    selectedRowRef.current?.scrollIntoView({ block: 'nearest' });
    if (keyboardNavigationRef.current) {
      selectedRowRef.current?.focus();
      keyboardNavigationRef.current = false;
    }
  }, [selectedLinkId]);

  const moveSelection = (direction: 1 | -1) => {
    keyboardNavigationRef.current = true;
    selectAdjacent(direction);
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="text-base font-semibold text-ink">
            Extracted links
          </h2>
          <span
            className="inline-flex items-center rounded border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-muted"
            aria-live="polite"
          >
            {linksCountLabel(state, query, data.total)}
          </span>
        </div>
        <p className="font-mono text-xs tabular-nums text-muted">
          {pending ? 'Loading…' : `${start}-${end} of ${data.total}`}
        </p>
      </div>

      {state === 'error' && <LinksErrorBanner message={message} />}

      {/* Same 639px breakpoint as the table's `hidden sm:flex` below — CSS gates both. */}
      <div className="space-y-2 sm:hidden">
        {pending && (
          <p className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-body">
            Loading extracted links…
          </p>
        )}
        {state === 'ready' && data.items.length === 0 && (
          <p className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-body">
            {query.trim()
              ? 'No links match your search.'
              : 'No extracted links have been saved yet.'}
          </p>
        )}
        {state === 'ready' &&
          data.items.map((link) => (
            <TableCard
              key={link.url}
              link={link}
              linksData={linksData}
              expanded={expandedLinkId === link.id}
              onToggle={() => toggleMobileDetails(link.id)}
            />
          ))}
      </div>

      <div className="hidden gap-3 sm:flex">
        <div className="min-w-0 flex-[2] overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_0_rgba(255,255,255,0.03)]">
          <div className="max-h-[70vh] overflow-auto">
            <table className="min-w-full divide-y divide-line text-left text-sm">
              <thead className="sticky top-0 z-10 bg-raised text-xs text-muted shadow-[0_1px_0_rgba(255,255,255,0.06)]">
                <tr>
                  <th
                    scope="col"
                    aria-sort={
                      view.order === 'asc'
                        ? 'ascending'
                        : 'descending'
                    }
                    className="px-4 py-3 font-medium"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <span className="font-mono text-[11px] font-normal uppercase tracking-wider text-muted">
                        ↑↓ navigate
                      </span>
                      <button
                        type="button"
                        disabled={!viewLoaded}
                        onClick={toggleOrder}
                        className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-right transition-ui hover:bg-surface hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:text-muted disabled:opacity-50"
                      >
                        Last seen <SortIcon order={view.order} />
                      </button>
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {pending && (
                  <tr>
                    <td className="px-4 py-8 text-center text-body">
                      Loading extracted links…
                    </td>
                  </tr>
                )}
                {state === 'ready' && data.items.length === 0 && (
                  <tr>
                    <td className="px-4 py-8 text-center text-body">
                      {query.trim()
                        ? 'No links match your search.'
                        : 'No extracted links have been saved yet.'}
                    </td>
                  </tr>
                )}
                {state === 'ready' &&
                  data.items.map((link, index) => (
                    <tr
                      key={link.url}
                      ref={
                        link.id === selectedLinkId
                          ? selectedRowRef
                          : undefined
                      }
                      aria-selected={link.id === selectedLinkId}
                      tabIndex={
                        link.id === selectedLinkId ||
                        (!selectedLinkId && index === 0)
                          ? 0
                          : -1
                      }
                      onFocus={() => selectLink(link.id)}
                      onClick={() => selectLink(link.id)}
                      onMouseEnter={() => hoverLink(link.id)}
                      onMouseLeave={cancelHover}
                      onKeyDown={(event) => {
                        if (event.currentTarget !== event.target)
                          return;
                        if (event.key === 'ArrowDown') {
                          event.preventDefault();
                          moveSelection(1);
                        } else if (event.key === 'ArrowUp') {
                          event.preventDefault();
                          moveSelection(-1);
                        }
                      }}
                      className={`transition-colors hover:bg-raised/60 focus-visible:bg-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-signal ${
                        link.id === selectedLinkId ? 'bg-raised' : ''
                      }`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex flex-col gap-1">
                          <div className="flex min-w-0 items-center gap-2">
                            <LinkUrl link={link} />
                            <LinkTagCluster link={link} />
                          </div>
                          <span className="font-mono text-[11px] tabular-nums text-muted">
                            {formatDateCompact(
                              link.last_seen ?? link.first_seen,
                            )}
                          </span>
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
        <LinkPreviewPanel linksData={linksData} />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submitJump(Number.parseInt(jumpPage, 10));
          }}
          className="flex items-center gap-2 text-xs text-muted"
        >
          <span className="font-mono tabular-nums">
            Page {currentPage} of {pageCount}
          </span>
          <label className="flex items-center gap-2">
            Jump to
            <input
              type="number"
              min={1}
              max={pageCount}
              value={jumpPage}
              onChange={(e) => setJumpPage(e.target.value)}
              className="h-10 w-20 rounded-lg border border-line bg-canvas px-3 font-mono text-xs tabular-nums text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </label>
          <button
            type="submit"
            disabled={pending}
            className="h-10 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised active:scale-[0.96] disabled:text-muted disabled:opacity-50"
          >
            Go
          </button>
        </form>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!hasPrevious || pending}
            onClick={() => setPage((value) => Math.max(0, value - 1))}
            className="h-10 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised active:scale-[0.96] disabled:text-muted disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasNext || pending}
            onClick={() => setPage((value) => value + 1)}
            className="h-10 rounded-lg bg-signal px-3 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] disabled:bg-surface disabled:text-muted"
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
