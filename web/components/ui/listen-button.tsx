'use client';

import { Square, Volume2 } from 'lucide-react';
import { Tooltip } from '@/components/ui/tooltip';
import { useSpeech } from '@/lib/hooks/useSpeech';

export function ListenButton({
  text,
  ariaLabel,
  voiceURI,
}: {
  text: string;
  ariaLabel: string;
  voiceURI?: string | null;
}) {
  const { supported, speaking, toggle } = useSpeech(text, voiceURI);
  if (!supported || !text.trim()) return null;

  const label = speaking ? 'Stop' : ariaLabel;
  return (
    <Tooltip content={label}>
      <button
        onClick={toggle}
        aria-label={label}
        className="inline-flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs font-medium text-muted transition-ui hover:border-line-strong hover:bg-raised hover:text-ink"
      >
        {speaking ? <Square className="h-3.5 w-3.5" /> : <Volume2 className="h-3.5 w-3.5" />}
      </button>
    </Tooltip>
  );
}
