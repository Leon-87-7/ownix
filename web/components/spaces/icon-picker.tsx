import { SPACE_ICONS } from "@/lib/space-icons";

export function IconPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (name: string) => void;
}) {
  return (
    <div>
      <span className="mb-1 block text-xs font-medium text-body">Icon</span>
      <div className="flex flex-wrap gap-1">
        {SPACE_ICONS.map(({ name, Icon }) => {
          const active = value === name;
          return (
            <button
              key={name}
              type="button"
              onClick={() => onChange(name)}
              aria-label={name}
              aria-pressed={active}
              className={`flex h-8 w-8 items-center justify-center rounded-md transition-ui ${active ? "bg-signal text-onsignal hover:bg-signal-bright" : "border border-line bg-surface text-body hover:bg-raised hover:text-ink"}`}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
