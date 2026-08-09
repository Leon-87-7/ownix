'use client';

import { useState } from 'react';
import { Check, Copy, Link2 } from 'lucide-react';

/** One extracted link as it arrives in an `action_ack` artifact. */
export interface IntakeLink {
  url: string;
  label?: string | null;
  description?: string | null;
}

const APPROVED_LINK_PROTOCOLS = new Set(['http:', 'https:']);

function parseIntakeLink(value: unknown): IntakeLink | null {
  if (!value || typeof value !== 'object') return null;

  const link = value as Record<string, unknown>;
  const { url, label, description } = link;
  if (typeof url !== 'string') return null;

  try {
    const parsed = new URL(url);
    if (!APPROVED_LINK_PROTOCOLS.has(parsed.protocol)) return null;
  } catch {
    return null;
  }

  if (label !== undefined && label !== null && typeof label !== 'string') return null;
  if (description !== undefined && description !== null && typeof description !== 'string') {
    return null;
  }

  return { url, label: label ?? null, description: description ?? null };
}

/** Pull the `{ links: [...] }` artifact out of a response's artifact list. */
export function extractLinks(artifacts: Array<Record<string, unknown>>): IntakeLink[] {
  for (const artifact of artifacts) {
    const links = artifact.links;
    if (Array.isArray(links)) {
      return links.flatMap((link) => {
        const parsed = parseIntakeLink(link);
        return parsed ? [parsed] : [];
      });
    }
  }
  return [];
}

/**
 * Renders the links found in an image/photo intake so they can actually be
 * used — every URL is a real link and selectable text, plus a "Copy all"
 * button that yields the plain one-per-line list (matching the Telegram
 * plain-links message). Without this the intake only reported a count.
 */
export function IntakeLinksList({ links }: { links: IntakeLink[] }) {
  const [copied, setCopied] = useState(false);

  if (links.length === 0) return null;

  const plainList = links.map((l) => l.url).join('\n');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(plainList);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked (insecure context / denied). The URLs stay
      // selectable text, so copying by hand still works.
    }
  };

  return (
    <div className="mt-3 rounded-md border border-line bg-canvas">
      <div className="flex items-center justify-between gap-2 border-b border-line px-3 py-2">
        <span className="inline-flex items-center gap-1.5 font-mono text-label uppercase tracking-wide text-muted">
          <Link2 className="h-3.5 w-3.5" aria-hidden="true" />
          {links.length} link{links.length === 1 ? '' : 's'}
        </span>
        <button
          type="button"
          onClick={handleCopy}
          className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md border border-line bg-raised px-2.5 font-mono text-label text-ink transition-ui hover:border-signal hover:text-signal focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-signal" aria-hidden="true" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" aria-hidden="true" />
              Copy all
            </>
          )}
        </button>
      </div>
      <ul className="divide-y divide-line">
        {links.map((link, i) => (
          <li key={`${link.url}-${i}`} className="px-3 py-2">
            <a
              href={link.url}
              target="_blank"
              rel="noreferrer"
              className="break-all font-mono text-xs text-signal transition-ui hover:text-signal-bright hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
            >
              {link.url}
            </a>
            {(link.label || link.description) && (
              <p className="mt-0.5 select-text text-label text-muted">
                {[link.label, link.description].filter(Boolean).join(' — ')}
              </p>
            )}
          </li>
        ))}
      </ul>
      <p aria-live="polite" className="sr-only">
        {copied ? 'Links copied to clipboard' : ''}
      </p>
    </div>
  );
}
