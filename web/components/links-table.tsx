"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowDown, ArrowUp, ExternalLink } from "lucide-react";

type LinkRow = {
  url: string;
  title?: string | null;
  topic?: string | null;
  seen_count: number;
  first_seen: string;
  last_seen?: string | null;
};

type LinksResponse = {
  items: LinkRow[];
  limit: number;
  offset: number;
  total: number;
};

type LinksSort = "last_seen" | "appearances";
type LinksOrder = "asc" | "desc";

type LinksView = {
  sort: LinksSort;
  order: LinksOrder;
  size: 25 | 50 | 100;
};

const DEFAULT_LINKS_VIEW: LinksView = {
  sort: "last_seen",
  order: "desc",
  size: 25,
};
const LINKS_PAGE_SIZES: LinksView["size"][] = [25, 50, 100];
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
    return parsed.protocol === "https:" || parsed.protocol === "http:"
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
    dateStyle: "medium",
    timeStyle: "short",
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
            ? "whitespace-normal break-words"
            : "max-w-[40ch] truncate sm:max-w-[60ch]"
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
        {expanded ? "Less" : "More"}
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
  const description = [link.title, link.topic].filter(Boolean).join(" · ");
  return description ? <TruncatedDescription text={description} /> : null;
}

function TableCard({ link }: { link: LinkRow }) {
  return (
    <article className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="min-w-0">
        <LinkUrl link={link} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] tabular-nums text-muted">
        <span>Last seen {formatDate(link.last_seen ?? link.first_seen)}</span>
        <span>
          {link.seen_count} appearance{link.seen_count === 1 ? "" : "s"}
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

function SortIcon({ active, order }: { active: boolean; order: LinksOrder }) {
  if (!active) return null;
  const Icon = order === "desc" ? ArrowDown : ArrowUp;
  return <Icon className="h-3.5 w-3.5" aria-hidden="true" />;
}

export function LinksTable() {
  const [page, setPage] = useState(0);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [view, setView] = useState<LinksView>(DEFAULT_LINKS_VIEW);
  const [viewLoaded, setViewLoaded] = useState(false);
  const [data, setData] = useState<LinksResponse>({
    items: [],
    limit: DEFAULT_LINKS_VIEW.size,
    offset: 0,
    total: 0,
  });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [message, setMessage] = useState("");
  const [jumpPage, setJumpPage] = useState("1");

  useEffect(() => {
    let cancelled = false;
    const loadView = async () => {
      try {
        const res = await fetch("/api/brain/links/view");
        if (!res.ok) throw new Error(`View request failed (${res.status})`);
        // GET returns server-normalized values only; no need to re-coerce here.
        const payload = (await res.json()) as LinksView;
        if (!cancelled) setView(payload);
      } catch {
        // Use defaults if the preference endpoint is temporarily unavailable.
      } finally {
        if (!cancelled) setViewLoaded(true);
      }
    };
    void loadView();
    return () => {
      cancelled = true;
    };
  }, []);

  // Debounce only the search box; page navigation should load immediately.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    if (!viewLoaded) return;
    let cancelled = false;
    const load = async () => {
      setState("loading");
      setMessage("");
      const params = new URLSearchParams({
        limit: String(view.size),
        offset: String(page * view.size),
        sort: view.sort,
        order: view.order,
      });
      if (debouncedQuery.trim()) params.set("q", debouncedQuery.trim());
      try {
        const res = await fetch(`/api/brain/links?${params}`);
        if (!res.ok) throw new Error(`Links request failed (${res.status})`);
        const payload = (await res.json()) as LinksResponse;
        if (!cancelled) {
          setData(payload);
          setState("ready");
        }
      } catch (err) {
        if (!cancelled) {
          setState("error");
          setMessage(
            err instanceof Error ? err.message : "Unable to load links.",
          );
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [page, debouncedQuery, view, viewLoaded]);

  // Skip the first run so loading the view from GET doesn't immediately PUT it back.
  const skipFirstPut = useRef(true);
  useEffect(() => {
    if (!viewLoaded) return;
    if (skipFirstPut.current) {
      skipFirstPut.current = false;
      return;
    }
    void fetch("/api/brain/links/view", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(view),
    }).catch(() => {
      // Preference persistence is best-effort.
    });
  }, [view, viewLoaded]);

  const pageCount = Math.max(1, Math.ceil(data.total / view.size));
  const currentPage = Math.min(page + 1, pageCount);
  const start = data.total === 0 ? 0 : data.offset + 1;
  const end = Math.min(data.offset + data.items.length, data.total);
  const hasPrevious = data.offset > 0;
  const hasNext = data.offset + data.limit < data.total;

  useEffect(() => {
    setJumpPage(String(currentPage));
  }, [currentPage]);

  const updateView = (patch: Partial<LinksView>) => {
    setPage(0);
    setView((value) => ({ ...value, ...patch }));
  };

  const toggleSort = (sort: LinksSort) => {
    updateView({
      sort,
      order: view.sort === sort && view.order === "desc" ? "asc" : "desc",
    });
  };

  const submitJump = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const requested = Number.parseInt(jumpPage, 10);
    if (Number.isNaN(requested)) return;
    setPage(Math.min(Math.max(requested, 1), pageCount) - 1);
  };

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">Extracted links</h2>
          <p className="mt-1 text-pretty text-sm text-body">
            Deduplicated canonical URLs discovered by enrichment runs.
          </p>
        </div>
        <p className="font-mono text-xs tabular-nums text-muted">
          {state === "loading"
            ? "Loading…"
            : `${start}-${end} of ${data.total}`}
        </p>
      </div>

      <div className="grid gap-3 rounded-xl border border-line bg-surface p-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <input
          id="links-search"
          type="search"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPage(0);
          }}
          onKeyDown={(e) => {
            // Escape clears the filter if any, else blurs out of the field.
            if (e.key === "Escape") {
              if (query) {
                setQuery("");
                setPage(0);
              } else {
                e.currentTarget.blur();
              }
            }
          }}
          placeholder="Filter links by URL, title, or topic…"
          aria-label="Filter extracted links"
          className="h-10 w-full rounded-lg border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
        />
        <label className="flex items-center gap-2 text-xs font-medium text-muted">
          Page size
          <select
            value={view.size}
            disabled={!viewLoaded}
            onChange={(e) =>
              updateView({ size: Number(e.target.value) as LinksView["size"] })
            }
            className="h-10 rounded-lg border border-line bg-canvas px-3 font-mono text-xs tabular-nums text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none disabled:opacity-50"
          >
            {LINKS_PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>

      {state === "error" && <LinksErrorBanner message={message} />}

      {/* Same 639px breakpoint as the table's `hidden sm:block` — CSS gates both. */}
      <div className="space-y-2 sm:hidden">
        {state === "loading" && (
          <p className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-body">
            Loading extracted links…
          </p>
        )}
        {state === "ready" && data.items.length === 0 && (
          <p className="rounded-lg border border-line bg-surface px-4 py-8 text-center text-body">
            {query.trim()
              ? "No links match your search."
              : "No extracted links have been saved yet."}
          </p>
        )}
        {state === "ready" &&
          data.items.map((link) => <TableCard key={link.url} link={link} />)}
      </div>

      <div className="hidden overflow-hidden rounded-xl border border-line bg-surface shadow-[0_1px_0_rgba(255,255,255,0.03)] sm:block">
        <div className="max-h-[70vh] overflow-auto">
          <table className="min-w-full divide-y divide-line text-left text-sm">
            <thead className="sticky top-0 z-10 bg-raised text-xs text-muted shadow-[0_1px_0_rgba(255,255,255,0.06)]">
              <tr>
                <th scope="col" className="px-4 py-3 font-medium">
                  URL
                </th>
                <th
                  scope="col"
                  aria-sort={
                    view.sort === "last_seen"
                      ? view.order === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                  className="px-4 py-3 font-medium"
                >
                  <button
                    type="button"
                    disabled={!viewLoaded}
                    onClick={() => toggleSort("last_seen")}
                    className="inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-left transition-ui hover:bg-surface hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:text-muted disabled:opacity-50"
                  >
                    Last seen{" "}
                    <SortIcon
                      active={view.sort === "last_seen"}
                      order={view.order}
                    />
                  </button>
                </th>
                <th
                  scope="col"
                  aria-sort={
                    view.sort === "appearances"
                      ? view.order === "asc"
                        ? "ascending"
                        : "descending"
                      : "none"
                  }
                  className="px-4 py-3 text-right font-medium"
                >
                  <button
                    type="button"
                    disabled={!viewLoaded}
                    onClick={() => toggleSort("appearances")}
                    className="ml-auto inline-flex min-h-10 items-center gap-1.5 rounded-md px-2 text-right transition-ui hover:bg-surface hover:text-ink focus:outline-none focus:ring-1 focus:ring-signal active:scale-[0.96] disabled:text-muted disabled:opacity-50"
                  >
                    Appearances{" "}
                    <SortIcon
                      active={view.sort === "appearances"}
                      order={view.order}
                    />
                  </button>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {state === "loading" && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-body">
                    Loading extracted links…
                  </td>
                </tr>
              )}
              {state === "ready" && data.items.length === 0 && (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-body">
                    {query.trim()
                      ? "No links match your search."
                      : "No extracted links have been saved yet."}
                  </td>
                </tr>
              )}
              {state === "ready" &&
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
          onSubmit={submitJump}
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
            disabled={state === "loading"}
            className="h-10 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised active:scale-[0.96] disabled:text-muted disabled:opacity-50"
          >
            Go
          </button>
        </form>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={!hasPrevious || state === "loading"}
            onClick={() => setPage((value) => Math.max(0, value - 1))}
            className="h-10 rounded-lg border border-line bg-surface px-3 text-[13px] font-medium text-ink transition-ui hover:bg-raised active:scale-[0.96] disabled:text-muted disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={!hasNext || state === "loading"}
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
