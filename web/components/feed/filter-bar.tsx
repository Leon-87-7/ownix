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

function ContentTypeTab({ label, value, count, active, onClick }: ContentTypeTabData & { active: boolean; onClick: () => void }) {
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

  return (
    <section className="mt-8 flex flex-col gap-3" aria-label="Search and filters">
      <div className="-mx-1 overflow-x-auto px-1 pb-1" role="tablist" aria-label="Content type">
        <div className="flex min-w-max items-center gap-1">
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
        placeholder="Search by title or URL…"
        className="h-10 w-full rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
      />
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
        <div className="flex flex-wrap items-center gap-1">
          {STATUS_FILTERS.map(({ label, value }) => (
            <FilterButton key={value} label={label} active={stFilter === value} onClick={() => setStFilter(value)} />
          ))}
        </div>
        {recoveryPanel}
      </div>
    </section>
  );
}
