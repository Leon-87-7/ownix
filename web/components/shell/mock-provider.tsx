'use client';

/* @ds
name: MockProvider
purpose: Starts the MSW mock-service-worker before rendering children, so demo/mock mode (NEXT_PUBLIC_API_MOCK=1) never races a first-paint fetch against an unready worker.
when-not: A no-op passthrough outside mock mode — never used in production. Not a UI component; renders nothing itself.
notes: Renders children even if the worker fails to start, rather than leaving the app blank.
status: inferred
*/

import { useEffect, useState } from 'react';

// Build-time constant: NEXT_PUBLIC_* is inlined, so when unset the worker code
// is never loaded (dynamic import stays an unfetched chunk in prod).
const ENABLED = process.env.NEXT_PUBLIC_API_MOCK === '1';

export default function MockProvider({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(!ENABLED);

  useEffect(() => {
    if (!ENABLED) return;
    let active = true;
    import('@/lib/mocks/browser')
      .then(({ startWorker }) => startWorker())
      .catch((err) => console.error('[MockProvider] mock worker failed to start:', err))
      .finally(() => { if (active) setReady(true); }); // render children even if mocks fail, never blank
    return () => { active = false; };
  }, []);

  // In mock mode, hold render until the worker intercepts (avoids first-paint fetches racing it).
  if (!ready) return null;
  return <>{children}</>;
}
