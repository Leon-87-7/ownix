'use client';

import { useEffect, useState } from 'react';
import { Check, ClipboardCopy, FileDigit } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';

const FEEDBACK_RESET_MS = 1500;
const DOCUMENT_KEY = /^documents\/([a-f0-9]{64})\.([a-z0-9]+)$/i;

type SourceCopyState = 'idle' | 'copied' | 'copy_failed';

function getDocumentSourceMeta(source: string) {
  const match = DOCUMENT_KEY.exec(source);
  if (match) {
    return {
      format: match[2].toUpperCase(),
      shortId: match[1].slice(0, 8),
      copyValue: match[1],
      isSha: true,
    };
  }

  const fallbackName = (() => {
    try {
      const parsed = new URL(source);
      return (
        parsed.pathname.split('/').filter(Boolean).pop() || source
      );
    } catch {
      return (
        source.split(/[?#]/, 1)[0].split('/').filter(Boolean).pop() ||
        source
      );
    }
  })();

  const extension = fallbackName.includes('.')
    ? fallbackName.split('.').pop() || 'file'
    : 'file';
  const stem = fallbackName.replace(/\.[^.]+$/, '') || fallbackName;

  return {
    format: extension.toUpperCase(),
    shortId: stem.slice(0, 8),
    copyValue: stem,
    isSha: false,
  };
}

export function DocumentSourceChip({ source }: { source: string }) {
  const [copyState, setCopyState] = useState<SourceCopyState>('idle');
  const meta = getDocumentSourceMeta(source);

  useEffect(() => {
    if (copyState === 'idle') return;
    const timer = window.setTimeout(
      () => setCopyState('idle'),
      FEEDBACK_RESET_MS,
    );
    return () => window.clearTimeout(timer);
  }, [copyState]);

  async function copySourceId() {
    try {
      await navigator.clipboard.writeText(meta.copyValue);
      setCopyState('copied');
    } catch {
      setCopyState('copy_failed');
    }
  }

  const sourceLabel = meta.isSha ? 'source SHA-256' : 'source';

  const copyLabel =
    copyState === 'copied'
      ? `Copied ${sourceLabel}`
      : copyState === 'copy_failed'
        ? 'Copy failed'
        : `Copy ${sourceLabel}`;

  const liveMessage =
    copyState === 'copied'
      ? `Copied ${sourceLabel}`
      : copyState === 'copy_failed'
        ? 'Copy failed'
        : '';

  return (
    <span className="inline-flex max-w-full items-center gap-2 rounded-md border border-line bg-canvas px-3 py-2 font-mono text-xs text-muted">
      <FileDigit
        className="size-4 shrink-0 text-contrasignal-deep"
        aria-hidden="true"
      />
      <span className="shrink-0 text-body">{meta.format}</span>
      <span
        className="shrink-0 text-line-strong"
        aria-hidden="true"
      >
        ·
      </span>
      <span className="min-w-0 truncate">{meta.shortId}</span>
      <Tooltip content={copyLabel}>
        <button
          type="button"
          onClick={copySourceId}
          aria-label={`Copy ${sourceLabel}`}
          className={`-my-1 -mr-1 inline-flex size-7 shrink-0 items-center justify-center rounded text-muted transition-ui hover:text-ink active:scale-[0.96] ${
            copyState === 'copy_failed' ? 'text-status-error' : ''
          }`}
        >
          {copyState === 'copied' ? (
            <Check
              className="size-4 text-status-done"
              aria-hidden="true"
            />
          ) : (
            <ClipboardCopy
              className="size-4"
              aria-hidden="true"
            />
          )}
        </button>
      </Tooltip>
      <span
        role="status"
        className="sr-only"
      >
        {liveMessage}
      </span>
    </span>
  );
}
