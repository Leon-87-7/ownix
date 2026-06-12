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

// The Signal Rule (DESIGN.md): an active filter is a selection — an act —
// so it earns the signal fill. Inactive chips stay on the plate ladder.
function FilterButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      className={`h-7 rounded-md px-3 text-[13px] font-medium transition-colors duration-150 ease-out-quart ${
        active
          ? "bg-signal text-onsignal hover:bg-signal-bright"
          : "border border-line bg-surface text-body hover:bg-raised hover:text-ink"
      }`}
    >
      {label}
    </button>
  );
}

export function FilterBar({ query, setQuery, ctFilter, setCtFilter, stFilter, setStFilter }: {
  query: string;
  setQuery: (q: string) => void;
  ctFilter: string;
  setCtFilter: (v: string) => void;
  stFilter: string;
  setStFilter: (v: string) => void;
}) {
  return (
    <section className="mt-8 flex flex-col gap-2" aria-label="Search and filters">
      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by title or URL…"
        className="h-10 w-full rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-colors duration-150 ease-out-quart hover:border-line-strong focus:border-signal focus:outline-none"
      />
      <div className="flex flex-wrap items-center gap-1">
        {CONTENT_TYPE_FILTERS.map(({ label, value }) => (
          <FilterButton key={value} label={label} active={ctFilter === value} onClick={() => setCtFilter(value)} />
        ))}
        <span className="mx-1 h-5 w-px bg-line" aria-hidden="true" />
        {STATUS_FILTERS.map(({ label, value }) => (
          <FilterButton key={value} label={label} active={stFilter === value} onClick={() => setStFilter(value)} />
        ))}
      </div>
    </section>
  );
}
