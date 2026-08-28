import { BraveIcon } from '@/components/svg/brave-icon';
import { FirecrawlIcon } from '@/components/svg/firecrawl-icon';
import { GeminiIcon } from '@/components/svg/gemini-icon';
import { GitHubIcon } from '@/components/svg/github-icon';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { JinaIcon } from '@/components/svg/jina-icon';
import { LlamaIndexIcon } from '@/components/svg/llamaindex-icon';

const stack: {
  name: string;
  by?: string;
  Icon: (props: React.SVGProps<SVGSVGElement>) => React.JSX.Element;
  iconClassName?: string;
}[] = [
  { name: 'Gemini', Icon: GeminiIcon },
  { name: 'Jina', Icon: JinaIcon },
  { name: 'Brave', Icon: BraveIcon },
  { name: 'LiteParse', by: 'LlamaIndex', Icon: LlamaIndexIcon },
  { name: 'Anydoc', by: 'Firecrawl', Icon: FirecrawlIcon },
  { name: 'GitHub', Icon: GitHubIcon, iconClassName: 'text-ink' },
  { name: 'Google Drive', Icon: GoogleDriveIcon },
];

/** Trust block naming the real services under the hood - Gemini for
 * enrichment, Jina/Brave for article and link ingestion, LiteParse (by
 * LlamaIndex) and Anydoc (by Firecrawl) for PDF and office-document
 * parsing, GitHub for repo analysis, Drive for storage. Leads the features
 * section: a 4-col grid puts the 7 tools in two rows on desktop, 2 columns
 * on mobile. */
export function PoweredBy() {
  return (
    <div
      aria-label="Powered by"
      className="mb-8 rounded-lg border border-line bg-surface px-6 py-5"
    >
      <span className="mb-4 block font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
        Powered by
      </span>
      <div className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-4 sm:gap-x-8">
        {stack.map(({ name, by, Icon, iconClassName }) => (
          <span
            key={name}
            className="flex shrink-0 items-center gap-2"
          >
            <Icon className={`h-5 w-auto shrink-0 ${iconClassName ?? ''}`} />
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-medium text-ink">{name}</span>
              {by && (
                <span className="font-mono text-[10px] uppercase tracking-[0.4px] text-muted">
                  by {by}
                </span>
              )}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
