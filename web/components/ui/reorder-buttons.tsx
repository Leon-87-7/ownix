import { OwnixChevronDown } from '@/components/svg/ownix-chevron-down';

export function ReorderButtons({
  onUp,
  onDown,
  disableUp,
  disableDown,
}: {
  onUp: () => void;
  onDown: () => void;
  disableUp: boolean;
  disableDown: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <button
        onClick={onUp}
        disabled={disableUp}
        className="rounded px-1 py-0.5 text-xs text-muted transition-ui hover:text-ink disabled:opacity-30"
        aria-label="Move up"
      >
        <OwnixChevronDown className="h-3.5 w-3.5 rotate-180" />
      </button>
      <button
        onClick={onDown}
        disabled={disableDown}
        className="rounded px-1 py-0.5 text-xs text-muted transition-ui hover:text-ink disabled:opacity-30"
        aria-label="Move down"
      >
        <OwnixChevronDown className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
