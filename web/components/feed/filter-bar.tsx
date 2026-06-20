'use client';

import { useEffect, useState } from 'react';
import type React from 'react';

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

interface ContentTypeTabData {
  label: string;
  value: string;
  count: number;
}

function ContentTypeTab({ label, count, active, onClick }: ContentTypeTabData & { active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={`${label} ${count}`}
      onClick={onClick}
      className={`h-9 shrink-0 rounded-md px-3 text-[13px] font-medium transition-ui ${
        active
          ? "bg-signal text-onsignal hover:bg-signal-bright"
          : "border border-line bg-surface text-body hover:bg-raised hover:text-ink"
      }`}
    >
      <span className="inline-flex items-center gap-2">
        <span>{label}</span>
        <span
          className={`rounded border px-1.5 py-0.5 font-mono text-[11px] tabular-nums ${
            active ? "border-onsignal/30 text-onsignal" : "border-line text-muted"
          }`}
        >
          {count}
        </span>
      </span>
    </button>
  );
}

// The Signal Rule (DESIGN.md): an active filter is a selection — an act —
// so it earns the signal fill. Inactive chips stay on the plate ladder.
function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`h-7 rounded-md px-3 text-[13px] font-medium transition-ui ${
        active
          ? "bg-signal text-onsignal hover:bg-signal-bright"
          : "border border-line bg-surface text-body hover:bg-raised hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

export function FilterBar({ query, setQuery, ctFilter, setCtFilter, contentTypeCounts, totalCount, stFilter, setStFilter, recoveryPanel }: {
  query: string;
  setQuery: (q: string) => void;
  ctFilter: string;
  setCtFilter: (v: string) => void;
  contentTypeCounts: Record<string, number>;
  totalCount: number;
  stFilter: string;
  setStFilter: (v: string) => void;
  recoveryPanel?: React.ReactNode;
}) {
  const tabs = CONTENT_TYPE_FILTERS.map(({ label, value }) => ({
    label,
    value,
    count: value ? contentTypeCounts[value] ?? 0 : totalCount,
  }));

  // #187: status filters + recovery panel collapse behind a disclosure on mobile.
  // Default collapsed; component remounts on navigation so it resets naturally.
  const [filtersOpen, setFiltersOpen] = useState(false);

  // Track the < sm (640px) breakpoint in JS so the collapsed panel is also
  // removed from the tab order / AT tree (inert), not just hidden visually.
  // Guarded for non-browser/jsdom envs → stays on the desktop (always-open) path.
  const [isMobile, setIsMobile] = useState(false);
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mq = window.matchMedia('(max-width: 639px)');
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  const collapsed = isMobile && !filtersOpen;

  return (
    <section className="mt-8 flex flex-col gap-3" aria-label="Search and filters">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {/* #186: tabs wrap to a second row on narrow screens — no horizontal scroll. */}
        <div className="min-w-0" role="tablist" aria-label="Content type">
          <div className="flex flex-wrap items-center gap-1">
            {tabs.map((tab) => (
              <ContentTypeTab
                key={tab.value}
                {...tab}
                active={ctFilter === tab.value}
                onClick={() => setCtFilter(tab.value)}
              />
            ))}
          </div>
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search by title or URL"
          placeholder="Search by title or URL…"
          className="h-9 w-full rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none sm:min-w-0 sm:flex-1"
        />
      </div>
      <button
        type="button"
        onClick={() => setFiltersOpen((o) => !o)}
        aria-expanded={filtersOpen}
        aria-controls="status-filter-bar"
        className="self-start text-[13px] font-medium text-muted transition-ui hover:text-ink sm:hidden"
      >
        Filters <span aria-hidden="true">{filtersOpen ? '▴' : '▾'}</span>
      </button>
      <div
        id="status-filter-bar"
        aria-hidden={collapsed || undefined}
        {...(collapsed ? ({ inert: "" } as Record<string, unknown>) : {})}
        className={`grid overflow-hidden transition-[grid-template-rows] duration-150 ease-out motion-reduce:transition-none ${
          collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]'
        }`}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-lg border border-line bg-surface p-3">
            <div className="flex flex-wrap items-center gap-1">
              {STATUS_FILTERS.map(({ label, value }) => (
                <FilterButton key={value} label={label} active={stFilter === value} onClick={() => setStFilter(value)} />
              ))}
            </div>
            {recoveryPanel}
          </div>
        </div>
      </div>
    </section>
  );
}
