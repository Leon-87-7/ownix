// Small shared product primitive (DESIGN.md).

interface TabBarProps<T extends string> {
  tabs: readonly T[];
  active: T;
  onChange: (tab: T) => void;
  labels?: Partial<Record<T, string>>;
}

// Underline-active tab bar: active tab earns the signal (a selection is an act).
export function TabBar<T extends string>({
  tabs,
  active,
  onChange,
  labels,
}: TabBarProps<T>) {
  return (
    <div className="flex gap-1 border-b border-line">
      {tabs.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          className={`px-4 py-2 text-sm font-medium transition-ui ${
            tab === active
              ? 'border-b-2 border-signal text-ink'
              : 'text-body hover:text-ink'
          }`}
        >
          {labels?.[tab] ?? tab}
        </button>
      ))}
    </div>
  );
}
