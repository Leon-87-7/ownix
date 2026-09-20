import type { ReactNode } from 'react';
import { PoweredBy } from '@/components/landing/powered-by';

function FeatureNote({
  heading,
  body,
  tag,
}: {
  heading: string;
  body: ReactNode;
  tag?: string;
}) {
  return (
    <>
      <h3 className="font-subtitle italic mb-1 text-title font-semibold leading-snug text-ink">
        &emsp;<span>{heading}</span>
      </h3>
      <p className="text-pretty text-copy leading-relaxed text-body">
        {body}
      </p>
      {tag && (
        <p className="mt-3 font-mono text-mono-label text-muted">{tag}</p>
      )}
    </>
  );
}

const leftNotes: { heading: string; body: ReactNode; tag?: string }[] = [
  {
    heading: 'All your content, in one place',
    body: 'Every item lands in your Feed and Brain. Filter by type, search by title or tag, open anything to grab its full transcript or copy a segment straight into your AI.',
  },
  {
    heading: 'The newsletter you keep meaning to read',
    body: "Give Ownix a newsletter's archive link and it follows the publication itself. New issues land with their links already pulled out, ready to promote into your Index.",
    tag: 'no alias / no forwarding / no inbox access',
  },
];

const rightNotes: { heading: string; body: ReactNode; tag?: string }[] = [
  {
    heading: 'Drop a GitHub repo link, skip the clone',
    body: "Paste a GitHub URL and Ownix reads the README and structure, writes a plain-language breakdown, and files it in your Index next to everything else.",
  },
  {
    heading: 'That PDF you saved and never reopened?',
    body: 'Upload it - or paste the link - and the Docs page reads it for you: parsed text, a structured briefing, a clean rewrite. All markdown, all ready for your AI.',
    tag: 'pdf / word / spreadsheet / presentation / image',
  },
  {
    heading: 'When search stops being enough',
    body: (
      <>
        Collections group content into a space when &quot;search
        later&quot; stops working.
        <br />
        Recipes save the freestyle prompt you keep re-running, ready to
        fire again.
      </>
    ),
  },
];

export function FeaturesSection() {
  return (
    <section
      aria-labelledby="features"
      className="border-t border-line bg-canvas-gradient py-16 sm:bg-canvas"
    >
      <div className="mx-auto max-w-[960px] px-6">
        <PoweredBy />
        <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-start">
          <div>
            <h2
              id="features"
              className="text-pretty mb-3 max-w-[16ch] font-title text-[clamp(1.5rem,4vw,2.25rem)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink"
            >
              Never lose it again.
            </h2>
            <p className="text-pretty max-w-[52ch] text-prose leading-relaxed text-body">
              Reels, long videos, articles, repos, screenshots - share
              it once and it becomes a searchable Index entry:
              transcript, summary, links, agent-ready markdown.
            </p>
            <p className="mt-3 mb-6 font-mono text-mono-label text-muted">
              short ◉ long ◉ article ◉ repo ◉ docs ◉ newsletter
            </p>

            {leftNotes.map((note, i) => (
              <div
                key={note.heading}
                className={
                  i === 0
                    ? 'border-t border-line pt-4 md:pt-5'
                    : 'mt-4 border-t border-line pt-4 md:mt-5 md:pt-5'
                }
              >
                <FeatureNote {...note} />
              </div>
            ))}
          </div>

          <div className="flex flex-col divide-y divide-line border-t border-line md:border-t-0">
            {rightNotes.map((note, i) => (
              <div
                key={note.heading}
                className={
                  i === 0 ? 'py-4 md:py-5 md:first:pt-0' : 'py-4 md:py-5'
                }
              >
                <FeatureNote {...note} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
