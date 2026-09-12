'use client';

import { useEffect, useRef } from 'react';

/** Binds one window `keydown` listener for the life of the component and always
 * calls the latest `handler`.
 *
 * Callers keep no deps array, which is what kept going stale: a handler closing
 * over fresh state stayed pinned to whatever the last re-bind captured, so the
 * shortcut acted on values the user had already moved past. Keeping the handler
 * in a ref also means typing in a search box no longer tears down and re-adds a
 * listener on every keystroke. */
export function useGlobalKeydown(
  handler: (event: KeyboardEvent) => void,
): void {
  const handlerRef = useRef(handler);
  // Assigned in an effect rather than during render (refs are not render
  // state). Effects run in declaration order on every commit, so the ref is
  // refreshed before the listener below can be reached by a keystroke — those
  // arrive asynchronously, never between a render and its own effects.
  useEffect(() => {
    handlerRef.current = handler;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => handlerRef.current(event);
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
