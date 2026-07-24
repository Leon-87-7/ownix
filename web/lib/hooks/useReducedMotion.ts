import { useEffect, useState } from 'react';

// Safe-by-default: assume reduced motion until the media query resolves, so
// no animation flashes for a vestibular-disorder user before the effect runs.
export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(true);

  useEffect(() => {
    if (!window.matchMedia) return;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(media.matches);
    update();
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  return reducedMotion;
}
