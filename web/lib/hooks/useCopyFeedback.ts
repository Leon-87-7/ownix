'use client';

import { useEffect, useState } from 'react';

const RESET_MS = 1500;

/** Copies `value` to the clipboard and flips `copied` true for RESET_MS. */
export function useCopyFeedback(value: string) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), RESET_MS);
    return () => window.clearTimeout(timer);
  }, [copied]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
    } catch {}
  };

  return { copied, copy };
}
