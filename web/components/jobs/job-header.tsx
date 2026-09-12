'use client';

import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Pencil } from 'lucide-react';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { StatusBadge, TypeBadge } from '@/components/ui/badges';
import { Tooltip } from '@/components/ui/tooltip';
import { useRestrictedMode } from '@/lib/restricted/context';
import { apiPut } from '@/lib/fetch-utils';
import { isSafeHttpUrl } from '@/lib/url-utils';
import { isEditableTarget } from '@/lib/keyboard';
import { useGlobalKeydown } from '@/lib/hooks/useGlobalKeydown';
import type { JobDetail } from '@/lib/hooks/useJobDetail';
import {
  adjacentScopeQuery,
  buildJobHref,
  feedScopeQuery,
  parseJobScope,
  type FeedScope,
} from '@/lib/feed-scope';

type AdjacentJobs = {
  previous_id: string | null;
  next_id: string | null;
};

// A span (not a Link with pointer-events-none) when there's no target: anchors
// stay keyboard-operable regardless of aria-disabled, so Enter would navigate to "#".
function AdjacentNavLink({
  href,
  children,
}: {
  href: string | null;
  children: ReactNode;
}) {
  const base =
    'flex flex-1 items-center justify-center px-3 text-sm font-medium';
  return href ? (
    <Link
      href={href}
      className={`${base} text-body transition-ui hover:bg-raised hover:text-ink`}
    >
      {children}
    </Link>
  ) : (
    <span aria-disabled="true" className={`${base} text-muted opacity-50`}>
      {children}
    </span>
  );
}

export function JobHeader({
  job,
  tags,
  onTitleSaved,
}: {
  job: JobDetail;
  tags?: ReactNode;
  onTitleSaved: (title: string | null) => void;
}) {
  const { restricted } = useRestrictedMode();
  const router = useRouter();
  const searchParams = useSearchParams();
  // parseJobScope, not parseFeedScope: this page's URL was written by
  // buildJobHref, so its content type is spelled `content_type`.
  const feedScope: FeedScope = useMemo(
    () => parseJobScope(new URLSearchParams(searchParams.toString())),
    [searchParams],
  );
  // Two vocabularies, deliberately: /api/jobs/:id/adjacent takes the API's
  // param names (has_checklist, tags) while /feed reads its own (checklist,
  // tags). Both read off the same feedScope, so prev/next can't drift from
  // the scope Back would restore.
  const scopeQuery = useMemo(
    () => new URLSearchParams(adjacentScopeQuery(feedScope)).toString(),
    [feedScope],
  );
  const [adjacent, setAdjacent] = useState<AdjacentJobs>({
    previous_id: null,
    next_id: null,
  });
  const displayTitle = job.title?.trim() || job.url;
  const displayUrl =
    job.url.length > 40 ? `${job.url.slice(0, 40)}...` : job.url;
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleValue, setTitleValue] = useState(displayTitle);
  const [titleSaving, setTitleSaving] = useState(false);
  const [titleError, setTitleError] = useState<string>();
  const skipBlurSaveRef = useRef(false);
  useEffect(() => {
    setTitleValue(displayTitle);
  }, [job.id, displayTitle]);
  const saveTitle = async () => {
    const next = titleValue.trim();
    if (next === displayTitle) {
      setEditingTitle(false);
      return;
    }
    setTitleSaving(true);
    setTitleError(undefined);
    try {
      const data = await apiPut<{ title: string | null }>(
        `/api/jobs/${job.id}/title`,
        { title: next },
        'Title save failed',
      );
      onTitleSaved(data.title);
      setEditingTitle(false);
    } catch {
      setTitleError('Title save failed');
    } finally {
      setTitleSaving(false);
    }
  };
  // Siblings keep the whole scope so walking Previous/Next never quietly
  // narrows what Back can restore.
  const jobHref = (id: string) => {
    const { pathname, query } = buildJobHref(id, feedScope);
    const qs = new URLSearchParams(query).toString();
    return qs ? `${pathname}?${qs}` : pathname;
  };
  // The Feed's own vocabulary (`type`, not `content_type`) — this rebuilds the
  // Feed when there's no history to go back to, e.g. a card cmd-clicked into a
  // new tab. Emitting the API's param names here restored nothing.
  const feedQs = new URLSearchParams(feedScopeQuery(feedScope)).toString();
  const feedHref = `/feed${feedQs ? `?${feedQs}` : ''}`;
  const handleBackToFeed = () => {
    if (window.history.length > 1) router.back();
    else router.push(feedHref);
  };

  useEffect(() => {
    // Adjacent nav is session-gated (/api/jobs/*) - in Restricted mode the
    // request would just 401, so skip it and leave the pager links hidden.
    if (restricted) return;
    let cancelled = false;
    const qs = scopeQuery ? `?${scopeQuery}` : '';
    void fetch(`/api/jobs/${job.id}/adjacent${qs}`)
      .then((res) =>
        res.ok
          ? res.json()
          : Promise.reject(new Error('Adjacent request failed')),
      )
      .then((payload: AdjacentJobs) => {
        if (!cancelled) setAdjacent(payload);
      })
      .catch(() => {
        if (!cancelled) setAdjacent({ previous_id: null, next_id: null });
      });
    return () => {
      cancelled = true;
    };
  }, [job.id, scopeQuery, restricted]);

  // No deps array (useGlobalKeydown keeps the handler current), which also
  // closes a stale-scope hole: the old deps listed `scopeQuery`, so a change to
  // a feed-only param like `q` — absent from that string — left the pager
  // pushing hrefs built from the previous scope.
  useGlobalKeydown((event) => {
    // Modified arrows are browser/OS shortcuts (Alt+Left = history back).
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey)
      return;
    if (isEditableTarget(event.target)) return;
    if (event.key === 'ArrowLeft' && adjacent.previous_id) {
      event.preventDefault();
      router.push(jobHref(adjacent.previous_id));
    }
    if (event.key === 'ArrowRight' && adjacent.next_id) {
      event.preventDefault();
      router.push(jobHref(adjacent.next_id));
    }
  });

  return (
    <div>
      {/* #192: 44px touch target, icon back + segmented Previous/Next in one row, capped to mobile's width on larger screens instead of stretching full-bleed. */}
      <div className="mb-4 flex items-center gap-2 sm:max-w-xs">
        <button
          type="button"
          onClick={handleBackToFeed}
          aria-label="Back"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-md border border-line bg-surface text-body transition-ui hover:bg-raised hover:text-ink"
        >
          <OwnixChevronRight aria-hidden="true" className="h-4 w-4 rotate-180" />
        </button>
        <div className="flex h-11 flex-1 items-stretch overflow-hidden rounded-full border border-line bg-surface">
          <AdjacentNavLink
            href={adjacent.previous_id && jobHref(adjacent.previous_id)}
          >
            ← Previous
          </AdjacentNavLink>
          <span aria-hidden="true" className="w-px shrink-0 bg-line" />
          <AdjacentNavLink href={adjacent.next_id && jobHref(adjacent.next_id)}>
            Next →
          </AdjacentNavLink>
        </div>
      </div>
      <div className="flex flex-wrap items-start gap-3">
        {editingTitle ? (
          <div className="min-w-[12rem] flex-1">
            <input
              autoFocus
              value={titleValue}
              onChange={(e) => setTitleValue(e.target.value)}
              onFocus={(e) => e.target.select()}
              onBlur={() => {
                if (skipBlurSaveRef.current) {
                  skipBlurSaveRef.current = false;
                  return;
                }
                void saveTitle();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  void saveTitle();
                }
                if (e.key === 'Escape') {
                  skipBlurSaveRef.current = true;
                  setTitleValue(displayTitle);
                  setEditingTitle(false);
                }
              }}
              disabled={titleSaving}
              aria-label="Job title"
              maxLength={500}
              className="w-full rounded-md border border-line bg-canvas px-2 py-1 text-xl font-semibold leading-snug text-ink focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright"
            />
            {titleError && (
              <p role="alert" className="mt-1 text-xs text-status-error">
                {titleError}
              </p>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setEditingTitle(true)}
            disabled={restricted}
            aria-label="Edit title"
            className="group flex flex-1 items-start gap-1.5 break-all text-left text-xl font-semibold leading-snug text-ink disabled:cursor-default"
          >
            {displayTitle}
            {!restricted && (
              <Pencil
                aria-hidden="true"
                className="mt-1.5 h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition-ui group-hover:opacity-100 group-focus-visible:opacity-100"
              />
            )}
          </button>
        )}
        <div className="flex shrink-0 items-center gap-2 pt-0.5">
          <TypeBadge label={job.content_type} />
          <StatusBadge label={job.status} />
        </div>
      </div>
      {/* URL, then the tag row stacked below it (not squeezed beside a wrapping URL). */}
      <div className="mt-1 flex flex-col items-start gap-2">
        <Tooltip content={job.url} mono>
          {isSafeHttpUrl(job.url) ? (
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="max-w-full break-all font-mono text-xs text-muted transition-ui hover:text-signal hover:underline"
            >
              {displayUrl}
            </a>
          ) : (
            <p className="max-w-full break-all font-mono text-xs text-muted">
              {displayUrl}
            </p>
          )}
        </Tooltip>
        {tags && (
          <div className="flex w-full flex-wrap items-center justify-end gap-2">
            {tags}
          </div>
        )}
      </div>
    </div>
  );
}
