import { BraveIcon } from '@/components/svg/brave-icon';
import { FirecrawlIcon } from '@/components/svg/firecrawl-icon';
import { GeminiIcon } from '@/components/svg/gemini-icon';
import { GitHubIcon } from '@/components/svg/github-icon';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { JinaIcon } from '@/components/svg/jina-icon';
import { LiteParseIcon } from '@/components/svg/liteparse-icon';

const stack: {
  name: string;
  Icon: (props: React.SVGProps<SVGSVGElement>) => React.JSX.Element;
  iconClassName?: string;
}[] = [
  { name: 'Gemini', Icon: GeminiIcon },
  { name: 'Jina', Icon: JinaIcon },
  { name: 'Brave', Icon: BraveIcon },
  { name: 'LiteParse', Icon: LiteParseIcon, iconClassName: 'text-muted' },
  { name: 'Firecrawl', Icon: FirecrawlIcon },
  { name: 'GitHub', Icon: GitHubIcon, iconClassName: 'text-ink' },
  { name: 'Google Drive', Icon: GoogleDriveIcon },
];

/** Trust bar naming the real services under the hood - Gemini for
 * enrichment, Jina/Brave for article and link ingestion, LiteParse/Firecrawl
 * (anydoc) for PDF and office-document parsing, GitHub for repo analysis,
 * Drive for storage. Sits between the hero and the onboarding section so it
 * doesn't grow the hero's fixed-height fold. */
export function PoweredBy() {
  return (
    <div
      aria-label="Powered by"
      className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 rounded-lg border border-line bg-surface px-6 py-5"
    >
      <span className="font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
        Powered by
      </span>
      {stack.map(({ name, Icon, iconClassName }) => (
        <span
          key={name}
          className="flex shrink-0 items-center gap-2 text-sm font-medium text-ink"
        >
          <Icon className={`h-5 w-auto shrink-0 ${iconClassName ?? ''}`} />
          {name}
        </span>
      ))}
    </div>
  );
}
