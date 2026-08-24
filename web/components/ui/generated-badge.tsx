import { BookmarkCheck, type LucideIcon } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";

// Row cards get a bordered-square shell; a thumbnail overlay (`bare`) uses a
// haloed icon directly on the image so it stays legible across light, dark,
// and busy pixels. Either way the tooltip + aria-label is the text label
// DESIGN.md requires (status never relies on color/shape alone) —
// contrasignal-bright, not amber, since this marks a fact, not an action.
//
// One badge family for any "a generated artifact exists for this job" marker
// — icon/label swap per artifact (checklist, document enrichment, ...).
export function GeneratedBadge({
  bare = false,
  icon: Icon = BookmarkCheck,
  label = "Checklist generated",
}: {
  bare?: boolean;
  icon?: LucideIcon;
  label?: string;
}) {
  const icon = (
    <Icon
      size={bare ? 24 : 14}
      aria-hidden="true"
    />
  );
  return (
    <Tooltip content={label}>
      <span
        className={
          bare
            ? "inline-flex h-8 w-8 items-center justify-center text-contrasignal-bright [filter:drop-shadow(0_1px_1px_rgba(0,0,0,0.98))_drop-shadow(0_0_4px_rgba(0,0,0,0.92))_drop-shadow(0_0_1px_rgba(255,255,255,0.72))]"
            : "inline-flex h-6 w-6 items-center justify-center rounded border border-line bg-canvas text-contrasignal-bright"
        }
        aria-label={label}
      >
        {icon}
      </span>
    </Tooltip>
  );
}
