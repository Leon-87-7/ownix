'use client';

import { ArrowBigUp, Command } from 'lucide-react';
import { useSubmitJob } from '@/components/submit-job';
import { Tooltip } from '@/components/ui/tooltip';

/**
 * The global sticky brand bar, pinned to the top of the scroll area on every
 * dashboard page and every viewport. Below sm the brand block centers and the
 * Submit URL trigger disappears (mobile submits from the Feed's tabs row);
 * sm+ keeps the Feed header's original left-aligned layout.
 */
export function AppHeader() {
  const { setOpen, openCommand } = useSubmitJob();
  return (
    <header className="relative z-20 shrink-0 border-b border-line bg-canvas/85 px-4 py-3 backdrop-blur-md sm:px-6">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-center gap-x-5 gap-y-3 sm:justify-start">
        <div className="flex flex-col">
          <span className="text-4xl font-semibold leading-none tracking-tight text-ink">
            Ownix
          </span>
          <span className="mt-1 text-xs font-medium text-muted">
            Your internet, indexed.
          </span>
        </div>
        <div
          aria-hidden="true"
          className="my-1 hidden w-px self-stretch bg-line-strong sm:block"
        />
        {/* Ownix rhythm: the personal act, the owned store, the shared layer. */}
        <div className="grid grid-cols-[repeat(3,auto)] gap-x-6 gap-y-1.5">
          <span className="text-sm font-medium italic text-body">
            Collect.
          </span>
          <span className="text-sm font-medium italic text-body">
            Own.
          </span>
          <span className="text-sm font-medium italic text-body">
            Recall.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Index.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Feed.
          </span>
          <span className="font-mono text-[11px] tracking-wide text-contrasignal-bright">
            Brain.
          </span>
        </div>

        <Tooltip
          content="Open command launcher Ctrl+Shift+K"
          side="bottom"
        >
          <button
            type="button"
            onClick={openCommand}
            aria-label="Open command launcher"
            aria-haspopup="dialog"
            aria-keyshortcuts="Meta+Shift+K Control+Shift+K"
            className="ml-auto hidden h-9 items-center gap-2 rounded-md border border-line border-b-2 border-b-signal bg-surface px-3 text-sm font-medium text-body transition-ui hover:text-ink active:scale-[0.96] focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas sm:inline-flex motion-reduce:active:scale-100"
          >
            <span>Commands</span>
            <kbd className="ml-2 inline-flex items-center gap-1 rounded border border-line bg-canvas px-1.5 py-1 font-mono text-contrasignal-deep hover:text-contrasignal-bright">
              <Command
                className="size-3 shrink-0"
                aria-hidden="true"
              />
              <ArrowBigUp
                className="size-3 shrink-0"
                aria-hidden="true"
              />
              <span className="inline-flex leading-none">K</span>
            </kbd>
          </button>
        </Tooltip>
      </div>
    </header>
  );
}
