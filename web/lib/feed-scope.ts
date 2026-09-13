/** The Feed's narrowing, and the two URL vocabularies it round-trips through.
 *
 * The Feed reads its own params (`type`, `checklist`, `q`); the job APIs take
 * theirs (`content_type`, `has_checklist`). They are deliberately not
 * interchangeable, which is why both serializers live here side by side rather
 * than one being derived from the other. */

/** Content types the Feed can narrow to. Anything else in `?type=` is noise
 * (a stale link, a typo) and reads as "no narrowing". */
const CONTENT_TYPES = new Set(['short', 'long', 'article', 'repo']);

export function isKnownContentType(value: string | null): boolean {
  return value !== null && CONTENT_TYPES.has(value);
}

/** Every narrowing the Feed can hold, plus which surface is showing it.
 *
 * `view` is part of the scope rather than separate state because it is already
 * a URL param the Feed round-trips, and because the two interact: choosing a
 * content type means the Jobs list, never the Links table. */
export interface FeedScope {
  contentType?: string;
  status?: string;
  query?: string;
  checklistOnly?: boolean;
  tags?: string[];
  view?: 'jobs' | 'links';
}

/** Single source of truth for the Feed-scope query params (#309): card links
 * write them, the detail page reads them back for its adjacent lookup. */
export function jobScopeQuery(scope: {
  contentType?: string;
  status?: string;
}): Record<string, string> {
  return {
    ...(scope.contentType ? { content_type: scope.contentType } : {}),
    ...(scope.status ? { status: scope.status } : {}),
  };
}

/** The /adjacent lookup's full scope: everything jobScopeQuery sends plus
 * has_checklist/tags, in the job APIs' own param names. Kept separate from
 * jobScopeQuery (rather than widening it) because jobScopeQuery also feeds
 * buildJobHref, which already writes checklist/tags in the Feed's vocabulary
 * via feedOnlyParams — adding them here too would just duplicate/dead-param
 * that URL. Prev/next needs the full scope or it can walk outside a feed
 * narrowed by tag or checklist filters. */
export function adjacentScopeQuery(scope: FeedScope): Record<string, string> {
  return {
    ...jobScopeQuery(scope),
    ...(scope.checklistOnly ? { has_checklist: 'true' } : {}),
    ...(scope.tags?.length ? { tags: scope.tags.join(',') } : {}),
  };
}

/** Narrowings only the Feed understands. They ride job URLs as passengers so
 * Back can rebuild the Feed from a detail page opened in a new tab (no history
 * to go back to); they are never sent to the job APIs. */
function feedOnlyParams(scope: FeedScope): Record<string, string> {
  return {
    ...(scope.query?.trim() ? { q: scope.query.trim() } : {}),
    ...(scope.checklistOnly ? { checklist: '1' } : {}),
    ...(scope.tags?.length ? { tags: scope.tags.join(',') } : {}),
  };
}

/** Serializes a FeedScope into the params `/feed` reads on arrival, so a
 * back-navigation restores the narrowing instead of dropping the user into an
 * unfiltered list. Empty values are omitted rather than written blank — a bare
 * `/feed` has to keep meaning "everything". Inverse: `parseFeedScope`. */
export function feedScopeQuery(scope: FeedScope): Record<string, string> {
  return {
    ...(scope.contentType ? { type: scope.contentType } : {}),
    ...(scope.status ? { status: scope.status } : {}),
    ...feedOnlyParams(scope),
    // Only the non-default surface is written; a bare /feed means the job list.
    ...(scope.view === 'links' ? { view: 'links' } : {}),
  };
}

/** Reads a FeedScope back off the Feed's own URL — the exact inverse of
 * `feedScopeQuery`, `contentType` included. It used to stop short of
 * `contentType` and leave the Feed to validate `type` itself, which is what
 * forced the Feed to keep a second, separately-parsed copy of that one field. */
export function parseFeedScope(params: URLSearchParams): FeedScope {
  const type = params.get('type');
  return {
    contentType: isKnownContentType(type) ? (type as string) : '',
    status: params.get('status') ?? '',
    query: params.get('q') ?? '',
    checklistOnly: params.get('checklist') === '1',
    tags: params.get('tags')?.split(',').filter(Boolean) ?? [],
    view: params.get('view') === 'links' ? 'links' : 'jobs',
  };
}

/** Reads a scope back off a job-detail URL — the inverse of `buildJobHref`, and
 * NOT interchangeable with `parseFeedScope`: job URLs spell the content type
 * `content_type` (the job APIs' name), the Feed spells it `type`. Unlike the
 * Feed's own param, this one isn't validated against the known content types —
 * it is passed straight back to the job APIs, which own that check. */
export function parseJobScope(params: URLSearchParams): FeedScope {
  return {
    contentType: params.get('content_type') ?? '',
    status: params.get('status') ?? '',
    query: params.get('q') ?? '',
    checklistOnly: params.get('checklist') === '1',
    tags: params.get('tags')?.split(',').filter(Boolean) ?? [],
  };
}

/** Job-detail href carrying the Feed's active filter scope (#309). Carries the
 * whole scope, not just content_type/status: a cmd-click into a new tab has no
 * history for Back to use, so the detail URL is the only record of where the
 * user was. */
export function buildJobHref(id: string, scope: FeedScope) {
  return {
    pathname: `/jobs/${id}`,
    query: jobUrlQuery(scope),
  };
}

/** The full param set a job-detail URL carries — `buildJobHref`'s query, on its
 * own, for the links that hop *between* job pages (detail ↔ transcript). They
 * have to write the same set or a round trip silently drops `q`/checklist/tags
 * and lands the user back in a wider feed than they left. Inverse:
 * `parseJobScope`. */
export function jobUrlQuery(scope: FeedScope): Record<string, string> {
  return { ...jobScopeQuery(scope), ...feedOnlyParams(scope) };
}
