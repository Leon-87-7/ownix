'use client';

/* @ds
name: FilterBar / SegmentedTabs / FilterButton
purpose: The search-and-filter row above a collection — SegmentedTabs pick one content-type view, FilterButton toggles a status facet, with a search that collapses on mobile.
variants:
  SegmentedTabs: active option flips to an amber fill + near-black text (selection is the action); inactive is hairline + hover underline.
  FilterButton: a secondary status toggle beside the tabs.
when-not: For switching peer views that aren't filters use TabBar; never put two amber winners on one row.
notes: FilterButton currently fills contrasignal-deep rather than amber — a known drift (DRIFT-BACKLOG.md), documented as-is, not corrected here.
status: inferred
*/

import Link from 'next/link';
import { Fragment, useEffect, useRef, useState } from 'react';
import type React from 'react';
import type { LucideIcon } from 'lucide-react';

function isEditableShortcutTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return (
    tag === 'input' ||
    tag === 'textarea' ||
    tag === 'select' ||
    target.isContentEditable ||
    Boolean(target.closest('[role="dialog"]'))
  );
}

export interface FilterTab {
  label: string;
  value: string;
  count?: number; // rendered as the mono count badge
  badge?: string; // overrides count, e.g. "soon" for a not-yet-supported option
  disabled?: boolean;
  dividerBefore?: boolean; // thin rule before this tab (desktop only), e.g. to fence off "soon" options
  href?: string;
  icon?: LucideIcon;
}

export interface StatusOption {
  label: string;
  value: string;
}

// Shared default: feed and doc-parser both filter on the same job statuses.
export const DEFAULT_STATUS_FILTERS: StatusOption[] = [
  { label: 'All', value: '' },
  { label: 'Done', value: 'done' },
  { label: 'Pending', value: 'pending' },
  { label: 'Processing', value: 'processing' },
  { label: 'Error', value: 'error' },
];

// Segmented control (motion-primitives "animated background"): the active tab
// fills bottom-to-top with the signal color via an animated clip-path, with a
// slight overshoot easing so it reads as poured rather than mechanical.
// Exported so view-switcher tablists (e.g. Brain) can share the same look without
// pulling in FilterBar's search + status-panel machinery.
export function SegmentedTabs({
  tabs,
  value,
  onChange,
  label,
  leadingItem,
  scrollOnMobile = false,
}: {
  tabs: readonly FilterTab[];
  value: string;
  onChange: (value: string) => void;
  label: string;
  /** Rendered as the first item inside the wrap grid, before the tabs — for a
   * page-level action that should flow with the chips on mobile (e.g. the feed's
   * Submit trigger). Not a tab: it never participates in value/fill logic. */
  leadingItem?: React.ReactNode;
  /** Mobile (< sm) layout. Default is the 4-column wrap grid (the feed places its
   * leadingItem into that grid). `true` swaps it for a single horizontally
   * scrollable row so a tab set that doesn't divide evenly into 4 (e.g.
   * doc-parser's five format chips) never orphans a chip onto a second row. */
  scrollOnMobile?: boolean;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className={`relative px-1 sm:flex sm:w-auto sm:flex-nowrap sm:gap-1 sm:overflow-visible sm:rounded-lg sm:border sm:border-line sm:bg-surface sm:p-1 ${
        scrollOnMobile
          ? 'flex w-full flex-nowrap gap-2 overflow-x-auto pb-1 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden'
          : 'grid w-full grid-cols-4 gap-2'
      }`}
    >
      {leadingItem}
      {tabs.map((tab) => {
        const active = !tab.href && tab.value === value;
        const Icon = tab.icon;
        const labelText = tab.badge
          ? `${tab.label} (${tab.badge})`
          : `${tab.label} ${tab.count ?? ''}`.trim();
        const className = `relative z-10 flex h-9 items-center justify-center gap-1.5 rounded-md border px-1.5 text-button font-medium transition-colors disabled:cursor-default sm:gap-2 sm:border-0 sm:px-3 ${scrollOnMobile ? 'shrink-0 whitespace-nowrap ' : ''}${
          active
            ? 'border-signal text-onsignal'
            : tab.disabled
              ? 'border-line bg-surface text-muted'
              : 'border-line bg-surface text-body hover:text-ink sm:after:absolute sm:after:inset-x-3 sm:after:bottom-1 sm:after:h-0.5 sm:after:origin-center sm:after:scale-x-0 sm:after:rounded-full sm:after:bg-contrasignal/70 sm:after:transition-transform sm:after:duration-200 sm:after:ease-out sm:hover:after:scale-x-100 motion-reduce:after:transition-none'
        }`;
        // Bottom-to-top fill: clipped fully away when inactive, revealed via
        // clip-path on activation. -z-10 keeps it under the (non-positioned,
        // so paint-order-first) label/badge content without a wrapper.
        const fill = (
          <span
            aria-hidden="true"
            className="absolute inset-0 -z-10 rounded-md bg-signal transition-[clip-path] duration-300 ease-[cubic-bezier(0.34,1.56,0.64,1)] motion-reduce:transition-none"
            style={{
              clipPath: active ? 'inset(0 0 0 0)' : 'inset(100% 0 0 0)',
            }}
          />
        );
        const content = (
          <>
            {Icon && (
              <Icon
                className="h-4 w-4 shrink-0"
                aria-hidden="true"
              />
            )}
            <span>{tab.label}</span>
            {tab.badge ? (
              <span className="font-mono text-micro uppercase tracking-wide text-muted">
                {tab.badge}
              </span>
            ) : tab.count !== undefined ? (
              <span
                className={`rounded border bg-on-signal px-1 py-0.5 font-mono text-mono-label tabular-nums text-contrasignal-deep sm:px-1.5 ${active ? 'border-onsignal/30 text-onsignal' : 'border-line'}`}
              >
                {tab.count}
              </span>
            ) : null}
          </>
        );
        return (
          <Fragment key={tab.value}>
            {tab.dividerBefore && (
              <span
                aria-hidden="true"
                className="mx-0.5 my-1 hidden w-px self-stretch bg-line sm:block"
              />
            )}
            {tab.href ? (
              <Link
                href={tab.href}
                aria-label={labelText}
                className={className}
              >
                {fill}
                {content}
              </Link>
            ) : (
              <button
                type="button"
                aria-pressed={active}
                aria-label={labelText}
                disabled={tab.disabled}
                onClick={() => onChange(tab.value)}
                className={className}
              >
                {fill}
                {content}
              </button>
            )}
          </Fragment>
        );
      })}
    </div>
  );
}

// The Signal Rule (DESIGN.md): an active filter is a selection — an act —
// so it earns the signal fill. Inactive chips stay on the plate ladder.
function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`h-7 rounded-md px-3 text-button font-medium transition-ui ${
        active
          ? 'bg-contrasignal-deep text-onsignal hover:bg-contrasignal'
          : 'border border-line bg-surface text-body hover:bg-raised hover:text-ink'
      }`}
    >
      {label}
    </button>
  );
}

export function FilterBar({
  tabs,
  tabValue,
  onTabChange,
  tabsLabel = 'Content type',
  query,
  setQuery,
  searchInputId,
  searchPlaceholder = 'Search…',
  searchLabel = 'Search',
  statusFilters = DEFAULT_STATUS_FILTERS,
  statusValue,
  onStatusChange,
  recoveryPanel,
  actionSlot,
  hideSearchAndFilters = false,
  searchSlot,
  scrollTabsOnMobile = false,
}: {
  tabs: readonly FilterTab[];
  tabValue: string;
  onTabChange: (value: string) => void;
  tabsLabel?: string;
  query: string;
  setQuery: (q: string) => void;
  /** DOM id on the search input so the command launcher can focus it. */
  searchInputId?: string;
  searchPlaceholder?: string;
  searchLabel?: string;
  statusFilters?: StatusOption[];
  statusValue: string;
  onStatusChange: (v: string) => void;
  recoveryPanel?: React.ReactNode;
  /** Page-level action rendered as the first slot in the tabs wrap grid (see
   * SegmentedTabs.leadingItem). */
  actionSlot?: React.ReactNode;
  /** Drops the status-filter/recovery row, keeping only the tab row (plus the
   * search input or searchSlot, if any) — for views (e.g. Links) that have no
   * use for the job-status filters. */
  hideSearchAndFilters?: boolean;
  /** Renders in place of the built-in search input, in the same slot next to
   * the tabs — for views (e.g. Links) whose search bar carries extra controls
   * (a page-size picker) and filters through its own state, not `query`. */
  searchSlot?: React.ReactNode;
  /** Forwarded to SegmentedTabs — see its `scrollOnMobile`. Use for tab sets
   * that don't divide evenly into the mobile 4-column grid. */
  scrollTabsOnMobile?: boolean;
}) {
  // #187: status filters + recovery panel collapse behind a disclosure on mobile.
  // Default collapsed; component remounts on navigation so it resets naturally.
  const [filtersOpen, setFiltersOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

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

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key !== '/' ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey ||
        isEditableShortcutTarget(event.target)
      ) {
        return;
      }
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <section
      className="mt-8 flex flex-col gap-3"
      aria-label="Search and filters"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <SegmentedTabs
            tabs={tabs}
            value={tabValue}
            onChange={onTabChange}
            label={tabsLabel}
            leadingItem={actionSlot}
            scrollOnMobile={scrollTabsOnMobile}
          />
        </div>
        {searchSlot ? (
          <div className="min-w-0 sm:flex-1">{searchSlot}</div>
        ) : (
          !hideSearchAndFilters && (
            <input
              ref={searchRef}
              id={searchInputId}
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                // Escape exits the search (mirrors the `/` shortcut to enter it).
                if (e.key === 'Escape') e.currentTarget.blur();
              }}
              aria-label={searchLabel}
              aria-keyshortcuts="/ Escape"
              placeholder={searchPlaceholder}
              className="h-9 w-full rounded-md border border-line bg-canvas px-4 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none sm:min-w-0 sm:flex-1"
            />
          )
        )}
      </div>
      {!hideSearchAndFilters && (
        <>
          <button
            type="button"
            onClick={() => setFiltersOpen((o) => !o)}
            aria-expanded={filtersOpen}
            aria-controls="status-filter-bar"
            className="mx-auto self-start text-button font-medium text-muted transition-ui hover:text-ink sm:hidden"
          >
            Filters{' '}
            <span aria-hidden="true">{filtersOpen ? '▲' : '▼'}</span>
          </button>
          <div
            id="status-filter-bar"
            aria-hidden={collapsed || undefined}
            {...(collapsed
              ? ({
                  inert: '',
                } as React.HTMLAttributes<HTMLDivElement> & { inert?: string })
              : {})}
            className={`grid overflow-hidden transition-[grid-template-rows] duration-150 ease-out motion-reduce:transition-none ${
              collapsed ? 'grid-rows-[0fr]' : 'grid-rows-[1fr]'
            }`}
          >
            <div className="min-h-0 overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 rounded-lg border border-line bg-surface p-3">
                <div className="flex flex-wrap items-center gap-1">
                  {statusFilters.map(({ label, value }) => (
                    <FilterButton
                      key={value}
                      label={label}
                      active={statusValue === value}
                      onClick={() => onStatusChange(value)}
                    />
                  ))}
                </div>
                {recoveryPanel}
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
