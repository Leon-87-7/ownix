'use client';

import { useEffect, useState } from 'react';
import { Link2 } from 'lucide-react';
import type { LinkRow } from '@/lib/hooks/useLinksTable';
import { TagMark } from '@/components/ui/tag-picker';
import { Tooltip } from '@/components/ui/tooltip';
import { safeUrl } from '@/lib/url-utils';

type FetchState = 'loading' | 'ready' | 'error';

/** GoTo quick-jump: the links carrying at least one of the user's pinned tags
 * (Controls → Tags' Pin toggle). Nothing is seeded or mandatory — an empty
 * result just invites the user to go pin a tag, for brand-new and long-time
 * accounts alike. */
export function GoToLinksPanel() {
  const [state, setState] = useState<FetchState>('loading');
  const [links, setLinks] = useState<LinkRow[]>([]);

  useEffect(() => {
    let cancelled = false;
    fetch('/api/brain/links?pinned=1&limit=100', { credentials: 'include' })
      .then((res) => {
        if (!res.ok) throw new Error('Failed to load GoTo links');
        return res.json() as Promise<{ items: LinkRow[] }>;
      })
      .then((data) => {
        if (cancelled) return;
        setLinks(data.items);
        setState('ready');
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === 'loading') {
    return <p className="text-sm text-body">Loading…</p>;
  }
  if (state === 'error') {
    return <p className="text-sm text-status-error">Couldn&apos;t load GoTo links.</p>;
  }
  if (links.length === 0) {
    return (
      <p className="text-sm text-body">
        Nothing pinned yet. Open Controls → Tags and tap the pin icon on any tag to see its links here.
      </p>
    );
  }

  return (
    <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
      {links.map((link) => {
        const href = safeUrl(link.url);
        const pinnedTags = (link.tags ?? []).filter((tag) => tag.pinned);
        return (
          <li
            key={link.id}
            className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-ui hover:bg-raised"
          >
            <Link2
              className="h-3.5 w-3.5 shrink-0 text-muted"
              aria-hidden="true"
            />
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-0 flex-1 truncate text-sm text-ink transition-ui hover:text-signal hover:underline"
              >
                {link.title || link.url}
              </a>
            ) : (
              <span className="min-w-0 flex-1 truncate text-sm text-muted">
                {link.title || link.url}
              </span>
            )}
            <span className="flex shrink-0 items-center gap-1">
              {pinnedTags.map((tag) => (
                <Tooltip
                  key={tag.id}
                  content={tag.name}
                >
                  <TagMark
                    tag={tag}
                    className="h-3 w-3"
                  />
                </Tooltip>
              ))}
            </span>
          </li>
        );
      })}
    </ul>
  );
}
