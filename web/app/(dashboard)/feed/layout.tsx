import { Suspense } from 'react';
import { cookies, headers } from 'next/headers';
import {
  buildThumbnailHints,
  fetchFeedThumbnails,
} from '@/lib/feed-thumbnail-preload';

async function FeedThumbnailPreload() {
  const cookieStore = await cookies();
  const thumbnails = await fetchFeedThumbnails({
    sessionCookie: cookieStore.get('vig_session')?.value,
    previewCookie: cookieStore.get('ownix_preview')?.value,
    cookieHeader: (await headers()).get('cookie') ?? '',
  });
  if (!thumbnails) return null;

  // Feed thumbnail preload (ADR-0041): give the all-client Feed freshness model
  // an SSR head start without server-rendering any cards.
  //
  // These are declarative <link> tags on purpose. The App Router's server
  // renderer hoists <link>/<meta> rendered inside a server component into
  // <head> and dedupes them; the imperative ReactDOM.preload/preconnect APIs
  // are NOT exposed by react-dom 18.3.1's public entry on this stack, so a
  // <link> here is the supported path - do not "upgrade" this to
  // ReactDOM.preload without also bumping react-dom. Browsers also honor these
  // hints when they land in <body>, so the head start degrades gracefully even
  // if hoisting ever regresses.
  return (
    <>
      {buildThumbnailHints(thumbnails).map((hint) =>
        hint.kind === 'preconnect' ? (
          <link
            key={`preconnect-${hint.href}`}
            rel="preconnect"
            href={hint.href}
            crossOrigin="anonymous"
          />
        ) : (
          <link
            key={`preload-${hint.href}`}
            rel="preload"
            as="image"
            href={hint.href}
            fetchPriority={hint.highPriority ? 'high' : undefined}
          />
        ),
      )}
    </>
  );
}

export default function FeedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // The preload sits in its own Suspense boundary so the feed shell always
  // streams immediately - a slow/cold backend just skips the head start.
  return (
    <>
      {children}
      <Suspense fallback={null}>
        <FeedThumbnailPreload />
      </Suspense>
    </>
  );
}
