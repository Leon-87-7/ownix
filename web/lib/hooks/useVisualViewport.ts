'use client';

import { useEffect, useState } from 'react';

/**
 * Center point of the *visual* viewport, in layout-viewport pixels.
 *
 * On iOS (and Android Chrome) the software keyboard shrinks the visual
 * viewport but leaves the layout viewport — and therefore `position: fixed`
 * / `top: 50%` / `100dvh` — at full screen height. A dialog centered with
 * `top-1/2` stays pinned to the middle of the full screen, so the keyboard
 * lays on top of its inputs. Recentering on this value keeps the dialog in
 * the visible band above the keyboard.
 */
export interface VisualViewportCenter {
  /** Y of the visible area's center, or null until measured (SSR / no API). */
  centerY: number | null;
  /** Visible height, or null until measured — use to cap the dialog height. */
  height: number | null;
}

const EMPTY: VisualViewportCenter = { centerY: null, height: null };

/** Read the current visual-viewport center, or EMPTY when the API is absent
 * (SSR / older browsers). offsetTop is how far the visual viewport has shifted
 * down inside the layout viewport (e.g. when pinch-zoomed and scrolled). */
function measure(): VisualViewportCenter {
  const vv =
    typeof window !== 'undefined' ? window.visualViewport : null;
  if (!vv) return EMPTY;
  return { centerY: vv.offsetTop + vv.height / 2, height: vv.height };
}

export function useVisualViewport(
  active: boolean,
): VisualViewportCenter {
  // Seed from the current viewport so the first paint is already positioned,
  // avoiding a render at the CSS-centered fallback that then jumps into place.
  const [center, setCenter] = useState<VisualViewportCenter>(() =>
    active ? measure() : EMPTY,
  );

  useEffect(() => {
    if (!active) {
      setCenter(EMPTY);
      return;
    }
    const vv =
      typeof window !== 'undefined' ? window.visualViewport : null;
    if (!vv) return;

    const update = () => setCenter(measure());
    update();
    vv.addEventListener('resize', update);
    vv.addEventListener('scroll', update);
    return () => {
      vv.removeEventListener('resize', update);
      vv.removeEventListener('scroll', update);
    };
  }, [active]);

  return center;
}
