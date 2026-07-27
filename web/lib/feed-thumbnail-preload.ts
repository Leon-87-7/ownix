const API_URL = process.env.API_INTERNAL_URL || "http://localhost:8000";

export interface FeedThumbnail {
  thumbnail_url?: string | null;
}

// Third-party thumbnail hosts worth a connection warm-up (ADR-0041 step 3).
// Instagram/TikTok thumbnails are same-origin (/api/jobs/{id}/thumbnail) so the
// connection is already open; article thumbnails come from arbitrary hosts and
// can't be preconnected — the preload hints cover those instead.
const PRECONNECT_HOSTS = [
  "https://img.youtube.com",
  "https://opengraph.githubassets.com",
] as const;

// Only the first N cards are eager-loaded (see preview-card.tsx); preloading
// more than that would waste bandwidth on cards the browser will lazy-load.
const PRELOAD_COUNT = 10;
// The first few get fetchpriority=high so the above-the-fold thumbnails win the
// bandwidth race on mobile (1-column feed); the rest are plain speculative
// preloads. Must stay in sync with the eager/high boundaries in preview-card.tsx.
const HIGH_PRIORITY_COUNT = 4;

export type PreloadHint =
  | { kind: "preconnect"; href: string }
  | { kind: "preload"; href: string; highPriority: boolean };

/**
 * Turn the fetched thumbnail list into the resource-hint descriptors the feed
 * layout renders as <link> tags: two static preconnects, then up to
 * PRELOAD_COUNT image preloads (first HIGH_PRIORITY_COUNT high priority),
 * skipping jobs with no thumbnail. Pure + synchronous so the tiering is unit
 * testable without rendering an async server component.
 */
export function buildThumbnailHints(thumbnails: FeedThumbnail[]): PreloadHint[] {
  const hints: PreloadHint[] = PRECONNECT_HOSTS.map((href) => ({
    kind: "preconnect",
    href,
  }));
  thumbnails.slice(0, PRELOAD_COUNT).forEach((thumbnail, index) => {
    if (thumbnail.thumbnail_url) {
      hints.push({
        kind: "preload",
        href: thumbnail.thumbnail_url,
        highPriority: index < HIGH_PRIORITY_COUNT,
      });
    }
  });
  return hints;
}

/**
 * Server-side fetch of the first jobs' thumbnails for the SSR preload head start
 * (ADR-0041). Returns null (no head start, no error) whenever it can't help:
 * no eligible cookie, a non-ok response, or the 800ms timeout tripping.
 *
 * Cookie routing mirrors the dashboard layout's restricted-mode check, but
 * deliberately without the extra /api/auth/me round trip that would add latency
 * to the critical path: a session cookie is treated as the owned feed. A
 * pending/blocked signed-in user (who actually sees the restricted preview
 * corpus) will 401/403 on /api/jobs and simply get no preload — a fail-safe
 * miss, not a broken page. The preview corpus endpoint ignores `limit`, so the
 * PRELOAD_COUNT cap in buildThumbnailHints is the real bound there.
 */
export async function fetchFeedThumbnails({
  sessionCookie,
  previewCookie,
  cookieHeader,
}: {
  sessionCookie?: string;
  previewCookie?: string;
  cookieHeader: string;
}): Promise<FeedThumbnail[] | null> {
  const path = sessionCookie
    ? "/api/jobs?limit=10"
    : previewCookie === "1"
      ? "/api/preview/jobs?limit=10"
      : null;
  if (!path) return null;

  try {
    const response = await fetch(`${API_URL}${path}`, {
      headers: { cookie: cookieHeader },
      cache: "no-store",
      signal: AbortSignal.timeout(800),
    });
    if (!response.ok) return null;
    const payload = (await response.json()) as { items?: FeedThumbnail[] };
    return Array.isArray(payload.items) ? payload.items : null;
  } catch {
    return null;
  }
}
