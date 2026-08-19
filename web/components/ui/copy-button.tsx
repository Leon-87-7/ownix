'use client';

import { Check, Copy } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { useCopyFeedback } from '@/lib/hooks/useCopyFeedback';

export function CopyButton({
  value,
  ariaLabel,
  label,
}: {
  value: string;
  ariaLabel: string;
  label?: string;
}) {
  const { copied, copy } = useCopyFeedback(value);
  return (
    <Tooltip content={ariaLabel}>
      <button
        onClick={copy}
        aria-label={ariaLabel}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {copied ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        {label && <span>{copied ? 'Copied!' : label}</span>}
      </button>
    </Tooltip>
  );
}
