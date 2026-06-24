'use client';

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type React from 'react';

// useLayoutEffect on the server warns; fall back to useEffect there (no DOM to measure anyway).
const useIsoLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

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

// Segmented control (motion-primitives "animated background"): one signal-orange
// thumb slides under the active tab. ponytail: pure-CSS slide via measured
// offsetLeft/width — no framer-motion dependency for a single sliding highlight.
function SegmentedTabs({ tabs, value, onChange }: {
  tabs: ContentTypeTabData[];
  value: string;
  onChange: (value: string) => void;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);
  const activeIndex = tabs.findIndex((t) => t.value === value);

  // Measure before paint so the orange thumb shows on first frame (no flash of no selection).
  useIsoLayoutEffect(() => {
    const el = refs.current[activeIndex];
    if (!el) return;
    const update = () => {
      const next = { left: el.offsetLeft, width: el.offsetWidth };
      setThumb((prev) => (prev && prev.left === next.left && prev.width === next.width ? prev : next));
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [activeIndex, tabs]);

  return (
    <div
      role="tablist"
      aria-label="Content type"
      className="relative flex w-full flex-wrap gap-2 sm:w-auto sm:flex-nowrap sm:gap-1 sm:rounded-lg sm:border sm:border-line sm:bg-surface sm:p-1"
    >
      {thumb && (
        <span
          aria-hidden="true"
          className="absolute bottom-1 top-1 left-0 hidden rounded-md bg-signal transition-[transform,width] duration-200 ease-out motion-reduce:transition-none sm:block"
          style={{ transform: `translateX(${thumb.left}px)`, width: thumb.width }}
        />
      )}
      {tabs.map((tab, i) => {
        const active = tab.value === value;
        return (
          <button
            key={tab.value}
            ref={(el) => { refs.current[i] = el; }}
            type="button"
            role="tab"
            aria-selected={active}
            aria-label={`${tab.label} ${tab.count}`}
            onClick={() => onChange(tab.value)}
            className={`relative z-10 flex h-9 items-center justify-center gap-2 rounded-md border px-3 text-[13px] font-medium transition-colors sm:border-0 ${
              active
                ? "border-signal bg-signal text-onsignal sm:bg-transparent"
                : "border-line bg-surface text-body hover:text-ink sm:after:absolute sm:after:inset-x-3 sm:after:bottom-1 sm:after:h-0.5 sm:after:origin-center sm:after:scale-x-0 sm:after:rounded-full sm:after:bg-ink/70 sm:after:transition-transform sm:after:duration-200 sm:after:ease-out sm:hover:after:scale-x-100 motion-reduce:after:transition-none"
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`rounded border px-1.5 py-0.5 font-mono text-[11px] tabular-nums ${
                active ? "border-onsignal/30 text-onsignal" : "border-line text-muted"
              }`}
            >
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
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
  const tabs = useMemo(
    () =>
      CONTENT_TYPE_FILTERS.map(({ label, value }) => ({
        label,
        value,
        count: value ? contentTypeCounts[value] ?? 0 : totalCount,
      })),
    [contentTypeCounts, totalCount],
  );

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
        <div className="min-w-0">
          <SegmentedTabs tabs={tabs} value={ctFilter} onChange={setCtFilter} />
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
