'use client';

import { useEffect } from 'react';

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas px-4">
      <section className="w-full max-w-md rounded-lg border border-line bg-surface p-6 text-center">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.04em] text-status-error">
          Error
        </p>
        <h1 className="mt-3 text-2xl font-semibold tracking-tight text-ink">Something went wrong</h1>
        <p className="mt-2 text-sm leading-6 text-body">
          The page hit an unexpected error. You can try again, or head back to the feed.
        </p>
        <div className="mt-5 flex justify-center gap-3">
          <button
            type="button"
            onClick={reset}
            className="h-8 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
          >
            Try again
          </button>
          <a
            href="/"
            className="inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui hover:bg-raised"
          >
            Back to feed
          </a>
        </div>
      </section>
    </div>
  );
}
