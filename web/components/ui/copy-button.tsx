'use client';

/* @ds
name: CopyButton
purpose: Copy a machine value (ID, URL, path) to the clipboard with inline confirmation.
when-not: Only for copyable literals — not a general-purpose action button (use GhostButton).
notes: Swaps to a check + "Copied!" for 1.5s after copy; pair with a mono value.
status: inferred
*/

import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';

export function CopyButton({
  value,
  ariaLabel,
  label,
}: {
  value: string;
  ariaLabel: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1500);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {}
  };
  return (
    <Tooltip content={ariaLabel}>
      <button
        onClick={handleCopy}
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
