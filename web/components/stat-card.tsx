'use client';

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
        <span className="w-fit font-mono text-[11px] font-medium uppercase tracking-wider text-muted">
          {label}
        </span>
      </Tooltip>
      <span className={`text-[28px] font-semibold leading-tight tabular-nums ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}
