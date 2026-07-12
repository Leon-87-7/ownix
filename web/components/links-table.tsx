'use client';

import { useState } from 'react';
import { ArrowDown, ArrowUp, ExternalLink } from 'lucide-react';
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
function formatDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function TruncatedDescription({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <span className="inline-flex max-w-full items-center gap-2">
      <span
        title={text}
        className={`min-w-0 text-xs text-body ${
          expanded
            ? 'whitespace-normal break-words'
            : 'max-w-[40ch] truncate sm:max-w-[60ch]'
        }`}
      >
        {text}
      </span>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
        className="relative shrink-0 rounded border border-line px-1.5 py-0.5 text-[10px] font-medium text-muted transition-ui before:absolute before:-inset-x-2 before:-inset-y-2.5 hover:bg-raised hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96]"
      >
        {expanded ? 'Less' : 'More'}
      </button>
    </span>
  );
}

function LinkUrl({ link }: { link: LinkRow }) {
  const href = safeUrl(link.url);
  return href ? (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="group inline-flex max-w-full items-center gap-2 font-mono text-xs text-ink transition-ui hover:text-signal hover:underline"
    >
      <span className="truncate">{link.url}</span>
      <ExternalLink
        className="h-3.5 w-3.5 shrink-0 text-muted transition-ui group-hover:text-signal"
        aria-hidden="true"
      />
    </a>
  ) : (
    <span className="block truncate font-mono text-xs text-muted">
      {link.url}
    </span>
  );
}

function LinkDescription({ link }: { link: LinkRow }) {
  const description = [link.title, link.topic]
    .filter(Boolean)
    .join(' · ');
  return description ? (
    <TruncatedDescription text={description} />
  ) : null;
}

function TableCard({ link }: { link: LinkRow }) {
  return (
    <article className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="min-w-0">
        <LinkUrl link={link} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] tabular-nums text-muted">
        <span>
          Last seen {formatDate(link.last_seen ?? link.first_seen)}
        </span>
        <span>
          {link.seen_count} appearance
          {link.seen_count === 1 ? '' : 's'}
        </span>
      </div>
      {Boolean(link.title || link.topic) && (
        <div className="mt-2 font-mono">
          <LinkDescription link={link} />
        </div>
      )}
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

function SortIcon({
  active,
  order,
}: {
  active: boolean;
  order: LinksOrder;
}) {
  if (!active) return null;
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
        placeholder="Filter links by URL, title, or topic…"
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

export function LinksTable({
  linksData,
}: {
  linksData: UseLinksTableResult;
}) {
  const {
    query,
    view,
    viewLoaded,
    toggleSort,
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
  } = linksData;
  const pending = state === 'loading' || state === 'idle';

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
          {pending
            ? 'Loading…'
            : `${start}-${end} of ${data.total}`}
        </p>
      </div>

      {state === 'error' && <LinksErrorBanner message={message} />}

      {/* Same 639px breakpoint as the table's `hidden sm:block` — CSS gates both. */}
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
            />
          ))}
      </div>

      <div className="hidden overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_0_rgba(255,255,255,0.03)] sm:block">
        <div className="max-h-[70vh] overflow-auto">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <thead className="sticky top-0 z-10 bg-raised text-xs text-muted shadow-[0_1px_0_rgba(255,255,255,0.06)]">
              <tr>
                <th
                  scope="col"
                  className="px-4 py-3 font-medium"
                >
                  URL
                </th>
                <th
                  scope="col"
                  aria-sort={
                    view.sort === 'last_seen'
                      ? view.order === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                  className="px-4 py-3 font-medium"
                >
                  <button
                    type="button"
                    disabled={!viewLoaded}
                    onClick={() => toggleSort('last_seen')}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-left transition-ui hover:bg-surface hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:text-muted disabled:opacity-50"
                  >
                    Last seen{' '}
                    <SortIcon
                      active={view.sort === 'last_seen'}
                      order={view.order}
                    />
                  </button>
                </th>
                <th
                  scope="col"
                  aria-sort={
                    view.sort === 'appearances'
                      ? view.order === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                  className="px-4 py-3 text-right font-medium"
                >
                  <button
                    type="button"
                    disabled={!viewLoaded}
                    onClick={() => toggleSort('appearances')}
                    className="ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-right transition-ui hover:bg-surface hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:text-muted disabled:opacity-50"
                  >
                    Appearances{' '}
                    <SortIcon
                      active={view.sort === 'appearances'}
                      order={view.order}
                    />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {pending && (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-8 text-center text-body"
                  >
                    Loading extracted links…
                  </td>
                </tr>
              )}
              {state === 'ready' && data.items.length === 0 && (
                <tr>
                  <td
                    colSpan={3}
                    className="px-4 py-8 text-center text-body"
                  >
                    {query.trim()
                      ? 'No links match your search.'
                      : 'No extracted links have been saved yet.'}
                  </td>
                </tr>
              )}
              {state === 'ready' &&
                data.items.map((link) => (
                  <tr
                    key={link.url}
                    className="transition-colors hover:bg-raised/60"
                  >
                    <td className="max-w-[36rem] px-4 py-3">
                      <div className="flex flex-col gap-1">
                        <LinkUrl link={link} />
                        <LinkDescription link={link} />
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 font-mono text-xs tabular-nums text-body">
                      {formatDate(link.last_seen ?? link.first_seen)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-xs tabular-nums text-ink">
                      {link.seen_count}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
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
