'use client';

import { useEffect, useRef, useState } from 'react';

export type LinkTag = { id: string; name: string; color: string; meaning: string; icon?: string | null };

export type LinkPreview = {
  id: string;
  og_image_url?: string | null;
};

const HOVER_SELECT_DELAY_MS = 220;

export type LinkRow = {
  id: string;
  url: string;
  title?: string | null;
  topic?: string | null;
  description?: string | null;
  seen_count: number;
  first_seen: string;
  last_seen?: string | null;
  tags?: LinkTag[];
};

type LinksResponse = {
  items: LinkRow[];
  limit: number;
  offset: number;
  total: number;
};

export type LinksOrder = 'asc' | 'desc';

export type LinksView = {
  order: LinksOrder;
  size: 25 | 50 | 100;
};
export type LinksTableState = 'idle' | 'loading' | 'ready' | 'error';

const DEFAULT_LINKS_VIEW: LinksView = {
  order: 'desc',
  size: 25,
};
export const LINKS_PAGE_SIZES: LinksView['size'][] = [25, 50, 100];

/**
 * Owns all Links-view state (search, sort/page-size preference, pagination,
 * data fetch) so the search bar (rendered in the Feed tab row) and the table
 * body (rendered below it) can share one instance instead of duplicating
 * fetch/debounce logic across two components.
 */
export function useLinksTable({ enabled }: { enabled: boolean }) {
  const [page, setPage] = useState(0);
  const [query, setQueryState] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [view, setView] = useState<LinksView>(DEFAULT_LINKS_VIEW);
  const [viewLoaded, setViewLoaded] = useState(false);
  const [data, setData] = useState<LinksResponse>({
    items: [],
    limit: DEFAULT_LINKS_VIEW.size,
    offset: 0,
    total: 0,
  });
  const [state, setState] = useState<LinksTableState>(
    enabled ? 'loading' : 'idle',
  );
  const [message, setMessage] = useState('');
  const [jumpPage, setJumpPage] = useState('1');

  // Desktop preview panel: which row is selected (hover/arrow-key), its
  // fetched og:image + metadata, cached per id so re-selecting a row already
  // seen this session never re-fetches.
  const [selectedLinkId, setSelectedLinkId] = useState<string | null>(null);
  const [previewCache, setPreviewCache] = useState<Record<string, LinkPreview>>({});
  const [previewState, setPreviewState] = useState<
    'idle' | 'loading' | 'ready' | 'error'
  >('idle');
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelHover = () => {
    if (hoverTimer.current) clearTimeout(hoverTimer.current);
    hoverTimer.current = null;
  };

  const selectLink = (id: string) => {
    cancelHover();
    setSelectedLinkId(id);
  };

  const hoverLink = (id: string) => {
    cancelHover();
    hoverTimer.current = setTimeout(() => setSelectedLinkId(id), HOVER_SELECT_DELAY_MS);
  };

  useEffect(() => {
    return () => {
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
    };
  }, []);

  const setQuery = (next: string) => {
    setQueryState(next);
    setPage(0);
  };

  useEffect(() => {
    if (!enabled) setState('idle');
  }, [enabled]);

  // Fetch the sort/page-size preference once per session after it completes.
  // If the Links tab is left mid-fetch, `viewLoaded` stays false so re-entry
  // can retry instead of getting stuck behind a stale "started" latch.
  useEffect(() => {
    if (!enabled || viewLoaded) return;
    setState('loading');
    let cancelled = false;
    const loadView = async () => {
      try {
        const res = await fetch('/api/brain/links/view');
        if (!res.ok)
          throw new Error(`View request failed (${res.status})`);
        // GET returns server-normalized values only; no need to re-coerce here.
        const payload = (await res.json()) as LinksView;
        if (!cancelled) setView(payload);
      } catch {
        // Use defaults if the preference endpoint is temporarily unavailable.
      } finally {
        if (!cancelled) setViewLoaded(true);
      }
    };
    void loadView();
    return () => {
      cancelled = true;
    };
  }, [enabled, viewLoaded]);

  // Debounce only the search box; page navigation should load immediately.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 250);
    return () => clearTimeout(timer);
  }, [query]);

  // Re-fetches every time the Links tab becomes active (not just on state
  // changes) so a re-entry after time away shows anything discovered since.
  useEffect(() => {
    if (!enabled || !viewLoaded) return;
    let cancelled = false;
    const load = async () => {
      setState('loading');
      setMessage('');
      const params = new URLSearchParams({
        limit: String(view.size),
        offset: String(page * view.size),
        order: view.order,
      });
      if (debouncedQuery.trim())
        params.set('q', debouncedQuery.trim());
      try {
        const res = await fetch(`/api/brain/links?${params}`);
        if (!res.ok)
          throw new Error(`Links request failed (${res.status})`);
        const payload = (await res.json()) as LinksResponse;
        if (!cancelled) {
          setData(payload);
          setState('ready');
        }
      } catch (err) {
        if (!cancelled) {
          setState('error');
          setMessage(
            err instanceof Error
              ? err.message
              : 'Unable to load links.',
          );
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [enabled, page, debouncedQuery, view, viewLoaded]);

  // Preserve an explicit selection only while it remains in the visible list.
  // Starting empty keeps mobile preview fetching genuinely lazy and gives the
  // desktop panel a meaningful select-a-row state.
  useEffect(() => {
    if (state !== 'ready') return;
    setSelectedLinkId((prev) =>
      data.items.some((item) => item.id === prev) ? prev : null,
    );
  }, [state, data.items]);

  // Fetches (and caches) the selected link's og:image + metadata. Reselecting
  // an id already seen this session skips the request entirely.
  useEffect(() => {
    if (!selectedLinkId) {
      setPreviewState('idle');
      return;
    }
    if (previewCache[selectedLinkId]) {
      setPreviewState('ready');
      return;
    }
    let cancelled = false;
    setPreviewState('loading');
    const load = async () => {
      try {
        const res = await fetch(`/api/brain/links/${selectedLinkId}/preview`);
        if (!res.ok)
          throw new Error(`Preview request failed (${res.status})`);
        const payload = (await res.json()) as LinkPreview;
        if (!cancelled) {
          setPreviewCache((cache) => ({ ...cache, [selectedLinkId]: payload }));
          setPreviewState('ready');
        }
      } catch {
        if (!cancelled) setPreviewState('error');
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedLinkId, previewCache]);

  // Skip the first run so loading the view from GET doesn't immediately PUT it back.
  const skipFirstPut = useRef(true);
  useEffect(() => {
    if (!viewLoaded) return;
    if (skipFirstPut.current) {
      skipFirstPut.current = false;
      return;
    }
    void fetch('/api/brain/links/view', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(view),
    }).catch(() => {
      // Preference persistence is best-effort.
    });
  }, [view, viewLoaded]);

  const pageCount = Math.max(1, Math.ceil(data.total / view.size));
  const currentPage = Math.min(page + 1, pageCount);
  const start = data.total === 0 ? 0 : data.offset + 1;
  const end = Math.min(data.offset + data.items.length, data.total);
  const hasPrevious = data.offset > 0;
  const hasNext = data.offset + data.limit < data.total;

  useEffect(() => {
    setJumpPage(String(currentPage));
  }, [currentPage]);

  const updateView = (patch: Partial<LinksView>) => {
    setPage(0);
    setView((value) => ({ ...value, ...patch }));
  };

  const toggleOrder = () => {
    updateView({
      order: view.order === 'desc' ? 'asc' : 'desc',
    });
  };

  const submitJump = (requested: number) => {
    if (Number.isNaN(requested)) return;
    setPage(Math.min(Math.max(requested, 1), pageCount) - 1);
  };

  // Moves the preview selection to the previous/next visible row (↑/↓).
  const selectAdjacent = (direction: 1 | -1) => {
    if (data.items.length === 0) return;
    const index = data.items.findIndex((item) => item.id === selectedLinkId);
    const nextIndex =
      index === -1
        ? 0
        : Math.min(Math.max(index + direction, 0), data.items.length - 1);
    selectLink(data.items[nextIndex].id);
  };

  return {
    query,
    setQuery,
    view,
    viewLoaded,
    updateView,
    toggleOrder,
    data,
    state,
    message,
    page,
    setPage,
    jumpPage,
    setJumpPage,
    submitJump,
    pageCount,
    currentPage,
    start,
    end,
    hasPrevious,
    hasNext,
    selectedLinkId,
    selectLink,
    hoverLink,
    cancelHover,
    selectAdjacent,
    preview: selectedLinkId ? (previewCache[selectedLinkId] ?? null) : null,
    previewState,
  };
}

export type UseLinksTableResult = ReturnType<typeof useLinksTable>;
