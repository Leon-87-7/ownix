'use client';

import { useEffect, useLayoutEffect, useRef } from 'react';

// `useLayoutEffect` warns when React renders on the server, and there are no
// keystrokes there anyway — fall back to the passive effect during SSR.
const useLatestRefEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

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
  // state), and in a *layout* effect specifically: React does not guarantee a
  // passive effect has flushed before the next browser input, so a keydown
  // landing in that gap would call the previous render's handler.
  useLatestRefEffect(() => {
    handlerRef.current = handler;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => handlerRef.current(event);
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
