'use client';

import { useState } from 'react';
import { ChevronDown, ChevronLeft, ChevronRight } from 'lucide-react';
import { StatCard } from '@/components/stat-card';
import { Tooltip } from '@/components/ui/tooltip';
import type { FeedStats } from '@/lib/hooks/useFeedData';

// Total card label reflects the active content-type tab ("" = All).
const TOTAL_LABELS: Record<string, string> = {
  short: 'Total Shorts',
  long: 'Total Long',
  article: 'Total Articles',
  repo: 'Total Repos',
};

const METRIC_TOOLTIPS: Record<string, string> = {
  total: 'All jobs matching the current feed filters.',
  done: 'Jobs that completed successfully.',
  pending: 'Jobs queued but not started yet.',
  error: 'Jobs that failed and may need recovery.',
  processing: 'Jobs currently processing, enriching, or waiting on transcripts.',
};

// Full-breakdown rows: every status / content type the API can report, with its
// semantic colour. Only keys present in the payload are rendered.
const STATUS_META: { key: string; label: string; cls: string }[] = [
  { key: 'done', label: 'Done', cls: 'text-status-done' },
  { key: 'pending', label: 'Pending', cls: 'text-status-pending' },
  {
    key: 'processing',
    label: 'Processing',
    cls: 'text-status-processing',
  },
  {
    key: 'enriching',
    label: 'Enriching',
    cls: 'text-status-enriching',
  },
  {
    key: 'transcript_done',
    label: 'Transcript',
    cls: 'text-status-enriching',
  },
  { key: 'error', label: 'Error', cls: 'text-status-error' },
  {
    key: 'cancelled',
    label: 'Cancelled',
    cls: 'text-status-cancelled',
  },
];

const TYPE_META: { key: string; label: string; cls: string }[] = [
  { key: 'short', label: 'Short', cls: 'text-type-short' },
  { key: 'long', label: 'Long', cls: 'text-type-long' },
  { key: 'article', label: 'Article', cls: 'text-type-article' },
  { key: 'repo', label: 'Repo', cls: 'text-type-repo' },
];

function BreakdownGroup({
  title,
  rows,
  source,
}: {
  title: string;
  rows: { key: string; label: string; cls: string }[];
  source: Record<string, number>;
}) {
  if (rows.length === 0) return null;
  return (
    <div>
      <Tooltip content={title === 'Status' ? 'Counts grouped by processing status.' : 'Counts grouped by source content type.'}>
        <p className="mb-1.5 w-fit text-xs font-medium text-muted">{title}</p>
      </Tooltip>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {rows.map((r) => (
          <span
            key={r.key}
            className="flex items-baseline gap-1.5 text-[13px]"
          >
            <span className="text-body">{r.label}</span>
            <span
              className={`font-mono font-semibold tabular-nums ${r.cls}`}
            >
              {source[r.key] ?? 0}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

export function StatsOverview({
  stats,
  contentType = '',
}: {
  stats: FeedStats;
  contentType?: string;
}) {
  const totalLabel = contentType
    ? (TOTAL_LABELS[contentType] ?? `Total ${contentType}`)
    : 'Total';
  const done = stats.by_status.done ?? 0;
  const pending = stats.by_status.pending ?? 0;
  const error = stats.by_status.error ?? 0;
  const processing =
    (stats.by_status.processing ?? 0) +
    (stats.by_status.enriching ?? 0) +
    (stats.by_status.transcript_done ?? 0);

  const [open, setOpen] = useState(false);
  const statusRows = STATUS_META.filter(
    (s) => (stats.by_status[s.key] ?? 0) > 0,
  );
  const typeRows = TYPE_META.filter(
    (t) => (stats.by_content_type[t.key] ?? 0) > 0,
  );

  return (
    <section
      className="mt-5"
      aria-label="Overview"
    >
      {/* Mobile (#185): one compact inline row instead of the card grid (~100px shorter).
          Tap to reveal the full per-status / per-type breakdown. The T/D/P/E letters are
          decorative — screen readers get the spoken summary on the button. */}
      <div className="sm:hidden">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="stat-breakdown"
          className="group block w-full rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          <span className="sr-only">
            {open ? 'Hide' : 'Show'} full breakdown. Total{' '}
            {stats.total}, done {done}, pending {pending}, error{' '}
            {error}.
          </span>
          <div
            aria-hidden="true"
            className="mx-auto w-fit"
          >
            <div className="flex items-center divide-x divide-line py-1 font-mono text-sm tabular-nums">
              <span className="px-3 text-muted">
                T{' '}
                <span className="font-semibold text-ink">
                  {stats.total}
                </span>
              </span>
              <span className="px-3 text-muted">
                D{' '}
                <span className="font-semibold text-status-done">
                  {done}
                </span>
              </span>
              <span className="px-3 text-muted">
                P{' '}
                <span className="font-semibold text-status-pending">
                  {pending}
                </span>
              </span>
              <span className="px-3 text-muted">
                E{' '}
                <span className="font-semibold text-status-error">
                  {error}
                </span>
              </span>
            </div>
            {/* The affordance: a steady signal underscore flanked by inward-
                pointing chevron trails. Collapsed, the chevrons count 1→2→3→2→1
                toward the centre; open, each side becomes a single down-arrow and
                the line brightens. Signal is earned: the strip acts. */}
            <div className="-mx-2 mt-1.5 flex items-center gap-1">
              {open ? (
                <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-signal" />
              ) : (
                <span aria-hidden="true" className="flex shrink-0 items-center text-signal">
                  <ChevronRight className="chev-c1 h-3 w-3" />
                  <ChevronRight className="chev-c2 -ml-2 h-3 w-3" />
                  <ChevronRight className="chev-c3 -ml-2 h-3 w-3" />
                </span>
              )}
              <div
                className={`h-px flex-1 ${open ? 'bg-signal/60' : 'bg-signal/40'}`}
              />
              {open ? (
                <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-signal" />
              ) : (
                <span aria-hidden="true" className="flex shrink-0 items-center text-signal">
                  <ChevronLeft className="chev-c3 h-3 w-3" />
                  <ChevronLeft className="chev-c2 -ml-2 h-3 w-3" />
                  <ChevronLeft className="chev-c1 -ml-2 h-3 w-3" />
                </span>
              )}
            </div>
          </div>
        </button>

        <div
          id="stat-breakdown"
          className={`grid overflow-hidden transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none ${
            open ? 'grid-rows-[1fr]' : 'grid-rows-[0fr]'
          }`}
        >
          <div className="min-h-0 overflow-hidden" aria-hidden={!open}>
            <div className="mt-3 space-y-3 rounded-lg border border-line bg-surface p-3">
              <BreakdownGroup
                title="Status"
                rows={statusRows}
                source={stats.by_status}
              />
              <BreakdownGroup
                title="Type"
                rows={typeRows}
                source={stats.by_content_type}
              />
            </div>
          </div>
        </div>
      </div>

      <div data-testid="stat-cards" className="hidden grid-cols-2 gap-3 sm:grid sm:grid-cols-3 lg:grid-cols-5">
        <StatCard
          label={totalLabel}
          value={stats.total}
          tooltip={METRIC_TOOLTIPS.total}
        />
        <StatCard
          label="Done"
          tooltip={METRIC_TOOLTIPS.done}
          value={done}
          valueClass="text-status-done"
        />
        <StatCard
          label="Pending"
          tooltip={METRIC_TOOLTIPS.pending}
          value={pending}
          valueClass="text-status-pending"
        />
        <StatCard
          label="Error"
          tooltip={METRIC_TOOLTIPS.error}
          value={error}
          valueClass="text-status-error"
        />
        <StatCard
          label="Processing"
          tooltip={METRIC_TOOLTIPS.processing}
          value={processing}
          valueClass="text-status-processing"
        />
      </div>
    </section>
  );
}
