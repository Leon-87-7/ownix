'use client';

import { BraveIcon } from '@/components/svg/brave-icon';
import { FirecrawlIcon } from '@/components/svg/firecrawl-icon';
import { GeminiIcon } from '@/components/svg/gemini-icon';
import { GitHubIcon } from '@/components/svg/github-icon';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { JinaIcon } from '@/components/svg/jina-icon';
import { LlamaIndexIcon } from '@/components/svg/llamaindex-icon';
import { Tooltip, TooltipProvider } from '@/components/ui/tooltip';

const stack: {
  name: string;
  by?: string;
  Icon: (props: React.SVGProps<SVGSVGElement>) => React.JSX.Element;
  tooltip: string;
}[] = [
  {
    name: 'LiteParse',
    by: 'LlamaIndex',
    Icon: LlamaIndexIcon,
    tooltip: 'Turns any PDF you share into clean, searchable text.',
  },
  {
    name: 'Anydoc',
    by: 'Firecrawl',
    Icon: FirecrawlIcon,
    tooltip: 'Converts Word, PowerPoint, and Excel files into markdown.',
  },
  {
    name: 'Gemini',
    Icon: GeminiIcon,
    tooltip: 'Reads and summarizes everything you save - video, article, or repo.',
  },
  {
    name: 'Jina',
    Icon: JinaIcon,
    tooltip: 'Pulls clean article text straight out of the page, no scraping mess.',
  },
  {
    name: 'Brave',
    Icon: BraveIcon,
    tooltip: 'Verifies and labels every link your video or article mentions.',
  },
  {
    name: 'GitHub',
    Icon: GitHubIcon,
    tooltip: "Reads a repo's README and structure into a plain-language breakdown.",
  },
  {
    name: 'Google Drive',
    Icon: GoogleDriveIcon,
    tooltip: 'Where every result lands as markdown - yours to keep, no lock-in.',
  },
];

/** Trust block naming the real services under the hood - Gemini for
 * enrichment, Jina/Brave for article and link ingestion, LiteParse (by
 * LlamaIndex) and Anydoc (by Firecrawl) for PDF and office-document
 * parsing, GitHub for repo analysis, Drive for storage. Leads the features
 * section. Pills mirror the Controls > Tags pill styling (rounded-full,
 * border-line, bg-raised) so the two surfaces read as one design language.
 * Each pill is a tooltip trigger (hover/focus - so effectively desktop-only,
 * since touch has no hover) naming what that service does inside Ownix
 * specifically, not just the vendor's own pitch. */
export function PoweredBy() {
  return (
    <div
      aria-label="Powered by"
      className="mb-8 rounded-lg border border-line bg-surface px-6 py-5"
    >
      <span className="mb-4 block text-center font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
        Powered by
      </span>
      <TooltipProvider>
        <ul className="flex flex-wrap justify-center gap-2">
          {stack.map(({ name, by, Icon, tooltip }) => (
            <li key={name}>
              <Tooltip content={tooltip}>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-raised px-2.5 py-1 text-xs font-medium text-ink transition-ui hover:border-line-strong focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-surface">
                  <Icon className="h-3.5 w-3.5 shrink-0" />
                  {name}
                  {by && <span className="text-muted">by {by}</span>}
                </span>
              </Tooltip>
            </li>
          ))}
        </ul>
      </TooltipProvider>
    </div>
  );
}
