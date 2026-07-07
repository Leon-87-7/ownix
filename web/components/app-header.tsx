'use client';

import { Plus } from 'lucide-react';
import { useSubmitJob } from '@/components/submit-job';

/**
 * The global sticky brand bar — pinned to the top of the scroll area on every
 * dashboard page and every viewport. Below sm the brand block centers and the
 * Submit URL trigger disappears (mobile submits from the Feed's tabs row);
 * sm+ keeps the Feed header's original left-aligned layout.
 */
export function AppHeader() {
  const { setOpen } = useSubmitJob();
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-canvas/85 px-4 py-3 backdrop-blur-md sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-5 gap-y-3 sm:justify-start">
        <span className="text-5xl font-semibold leading-none tracking-tight text-ink">
          VIG
        </span>
        <div
          aria-hidden="true"
          className="my-1 hidden w-px self-stretch bg-line-strong sm:block"
        />
        {/* Two voices: Inter italic motto over the machine's mono echo, each
            Latin word column-aligned above its English state. */}
        <div className="grid grid-cols-[repeat(3,auto)] gap-x-6 gap-y-1.5">
          <span className="text-sm font-medium italic text-body">
            Servavi.
          </span>
          <span className="text-sm font-medium italic text-body">
            Ditavi.
          </span>
          <span className="text-sm font-medium italic text-body">
            Inveni.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Saved.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Enriched.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Found.
          </span>
        </div>

        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-haspopup="dialog"
          aria-keyshortcuts="N"
          className="ml-auto hidden h-9 items-center gap-2 rounded-md border border-line border-b-2 border-b-signal bg-surface px-3.5 text-sm font-medium text-body transition-ui hover:text-ink active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas sm:inline-flex motion-reduce:active:scale-100"
        >
          <Plus
            aria-hidden="true"
            className="h-4 w-4 text-contrasignal-deep"
          />
          Submit URL
        </button>
      </div>
    </header>
  );
}
