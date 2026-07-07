'use client';

import Link from 'next/link';
import {
  Fragment,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import type React from 'react';
import type { LucideIcon } from 'lucide-react';

// useLayoutEffect on the server warns; fall back to useEffect there (no DOM to measure anyway).
const useIsoLayoutEffect =
  typeof window !== 'undefined' ? useLayoutEffect : useEffect;

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

// Segmented control (motion-primitives "animated background"): one signal-orange
// thumb slides under the active tab. ponytail: pure-CSS slide via measured
// offsetLeft/width — no framer-motion dependency for a single sliding highlight.
// Exported so view-switcher tablists (e.g. Brain) can share the same look without
// pulling in FilterBar's search + status-panel machinery.
export function SegmentedTabs({
  tabs,
  value,
  onChange,
  label,
  leadingItem,
}: {
  tabs: readonly FilterTab[];
  value: string;
  onChange: (value: string) => void;
  label: string;
  /** Rendered as the first item inside the wrap grid, before the tabs — for a
   * page-level action that should flow with the chips on mobile (e.g. the feed's
   * Submit trigger). Not a tab: it never participates in value/thumb logic. */
  leadingItem?: React.ReactNode;
}) {
  const refs = useRef<(HTMLElement | null)[]>([]);
  const [thumb, setThumb] = useState<{
    left: number;
    width: number;
  } | null>(null);
  const activeIndex = tabs.findIndex((t) => t.value === value);

  // Measure before paint so the orange thumb shows on first frame (no flash of no selection).
  useIsoLayoutEffect(() => {
    const el = refs.current[activeIndex];
    if (!el) return;
    const update = () => {
      const next = { left: el.offsetLeft, width: el.offsetWidth };
      setThumb((prev) =>
        prev && prev.left === next.left && prev.width === next.width
          ? prev
          : next,
      );
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [activeIndex, tabs]);

  return (
    <div
      role="group"
      aria-label={label}
      className="relative grid w-full grid-cols-4 gap-2 px-1 sm:flex sm:w-auto sm:flex-nowrap sm:gap-1 sm:rounded-lg sm:border sm:border-line sm:bg-surface sm:p-1 sm:px-0"
    >
      {thumb && (
        <span
          aria-hidden="true"
          className="absolute bottom-1 top-1 left-0 hidden rounded-md bg-signal transition-[transform,width] duration-200 ease-out motion-reduce:transition-none sm:block"
          style={{
            transform: `translateX(${thumb.left}px)`,
            width: thumb.width,
          }}
        />
      )}
      {leadingItem}
      {tabs.map((tab, i) => {
        const active = !tab.href && tab.value === value;
        const Icon = tab.icon;
        const labelText = tab.badge
          ? `${tab.label} (${tab.badge})`
          : `${tab.label} ${tab.count ?? ''}`.trim();
        const className = `relative z-10 flex h-9 items-center justify-center gap-1.5 rounded-md border px-1.5 text-[13px] font-medium transition-colors disabled:cursor-default sm:gap-2 sm:border-0 sm:px-3 ${
          active
            ? 'border-signal bg-signal text-onsignal sm:bg-transparent'
            : tab.disabled
              ? 'border-line bg-surface text-muted'
              : 'border-line bg-surface text-body hover:text-ink sm:after:absolute sm:after:inset-x-3 sm:after:bottom-1 sm:after:h-0.5 sm:after:origin-center sm:after:scale-x-0 sm:after:rounded-full sm:after:bg-contrasignal/70 sm:after:transition-transform sm:after:duration-200 sm:after:ease-out sm:hover:after:scale-x-100 motion-reduce:after:transition-none'
        }`;
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
              <span className="font-mono text-[10px] uppercase tracking-wide text-muted">
                {tab.badge}
              </span>
            ) : tab.count !== undefined ? (
              <span
                className={`rounded border bg-on-signal px-1 py-0.5 font-mono text-[11px] tabular-nums text-contrasignal-deep sm:px-1.5 ${active ? 'border-onsignal/30' : 'border-line'}`}
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
                ref={(el) => {
                  refs.current[i] = el;
                }}
                href={tab.href}
                aria-label={labelText}
                className={className}
              >
                {content}
              </Link>
            ) : (
              <button
                ref={(el) => {
                  refs.current[i] = el;
                }}
                type="button"
                aria-pressed={active}
                aria-label={labelText}
                disabled={tab.disabled}
                onClick={() => onChange(tab.value)}
                className={className}
              >
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
      className={`h-7 rounded-md px-3 text-[13px] font-medium transition-ui ${
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
          />
        </div>
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
      </div>
      <button
        type="button"
        onClick={() => setFiltersOpen((o) => !o)}
        aria-expanded={filtersOpen}
        aria-controls="status-filter-bar"
        className="mx-auto self-start text-[13px] font-medium text-muted transition-ui hover:text-ink sm:hidden"
      >
        Filters{' '}
        <span aria-hidden="true">{filtersOpen ? '▲' : '▼'}</span>
      </button>
      <div
        id="status-filter-bar"
        aria-hidden={collapsed || undefined}
        {...(collapsed
          ? ({ inert: '' } as Record<string, unknown>)
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
    </section>
  );
}
