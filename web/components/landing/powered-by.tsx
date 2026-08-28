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
 * section: a 4-col grid puts the 7 tools in two rows on desktop, 2 columns
 * on mobile. Each tile is a tooltip trigger (hover/focus - so effectively
 * desktop-only, since touch has no hover) naming what that service does
 * inside Ownix specifically, not just the vendor's own pitch. */
export function PoweredBy() {
  return (
    <div
      aria-label="Powered by"
      className="mb-8 rounded-lg border border-line bg-surface px-6 py-5"
    >
      <span className="mb-4 block font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
        Powered by
      </span>
      <TooltipProvider>
        <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 sm:gap-x-8">
          {stack.map(({ name, by, Icon, tooltip }) => (
            <Tooltip
              key={name}
              content={tooltip}
            >
              <span className="flex shrink-0 items-center gap-2 rounded-sm text-ink focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-surface">
                <Icon className="h-5 w-auto shrink-0" />
                <span className="flex flex-col leading-tight">
                  <span className="text-sm font-medium">{name}</span>
                  {by && (
                    <span className="font-mono text-[10px] uppercase tracking-[0.4px] text-muted">
                      by {by}
                    </span>
                  )}
                </span>
              </span>
            </Tooltip>
          ))}
        </div>
      </TooltipProvider>
    </div>
  );
}
