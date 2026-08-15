'use client';

/* @ds
name: StatCard
purpose: The Summary Tile primitive from DESIGN.md §5 — a mono-label caption over a large tabular-nums value, optionally tinted with a status hue.
when-not: No trend arrows, sparklines, or gradient accents — DESIGN.md explicitly rules those out for this component.
notes: valueClass is the caller's way to tint the value with a semantic status color (e.g. text-status-done); default is plain text-ink.
status: inferred
*/

import { Tooltip } from '@/components/ui/tooltip';

interface StatCardProps {
  label: string;
  value: number;
  tooltip?: string;
  /** Status hue for the value, e.g. "text-status-done" (DESIGN.md: stat tiles
   *  may tint their value with the matching status hue). */
  valueClass?: string;
  className?: string;
}

export function StatCard({ label, value, tooltip, valueClass = "text-ink", className = "" }: StatCardProps) {
  return (
    <div
      className={`flex flex-col gap-1 rounded-lg border border-line bg-surface px-4 py-3 ${className}`}
    >
      <Tooltip content={tooltip} mono>
        <span className="w-fit font-mono text-mono-label font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
      </Tooltip>
      <span className={`text-stat font-semibold leading-tight tabular-nums ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}
