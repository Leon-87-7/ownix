import OwnixLogo from '@/app/ownix-logo.svg';
import { OpenAIIcon } from '@/components/svg/openai-icon';
import { ShowcaseCard, ShowcasePanel } from './showcase-panel';

const cornerBadgeClasses =
  'absolute bottom-3 right-3 h-9 w-9 rounded-full border border-line bg-canvas p-1.5 shadow-md';

export function ShowcaseTranscriptSection() {
  return (
    <section
      aria-labelledby="showcase"
      className="border-t border-line bg-canvas-gradient py-16 sm:bg-canvas"
    >
      <ShowcasePanel
        id="showcase"
        heading="Doomscroll in, engineering standards out."
        subheading="How I use Ownix"
        vignette={
          <>
            An Instagram reel about post-launch support was about to
            scroll past and vanish, like everything does. I shared it
            to Ownix, got the full transcript back, and pasted it into
            Codex - which turned it into the support-playbook rules
            for another project I&apos;m building.
          </>
        }
        leftCard={
          <ShowcaseCard
            ariaLabel="The actual transcript file"
            filename="20260711_144906_48FB971E_transcript.md"
            status="DONE"
            cornerBadge={
              <OwnixLogo
                aria-hidden="true"
                className={cornerBadgeClasses}
              />
            }
          >
            <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
              <span className="text-muted"># Transcript</span>
              {'\n\n'}
              <span className="text-muted">**Source:**</span>{' '}
              instagram.com/reel/DamFvyUj3U0
              {'\n'}
              <span className="text-muted">**Platform:**</span>{' '}
              instagram_reels
              {'\n'}
              <span className="text-muted">**Processed:**</span>{' '}
              2026-07-11T14:49:36
              {'\n\n---\n\n'}
              Your AI assistant built your app and shipped{'\n'}
              it to production. Customers, they&apos;re now{'\n'}
              paying for it. And at 2:00 in the morning,{'\n'}a customer
              can&apos;t log in. So, tell me, who{'\n'}
              handles that? Your AI assistant? Probably{'\n'}
              not, because it&apos;s not connected to your{'\n'}
              production system. So your AI assistant{'\n'}
              built the product, but nobody told it to{'\n'}
              build the support system too...
            </pre>
          </ShowcaseCard>
        }
        rightCard={
          <ShowcaseCard
            ariaLabel="The agent rules file Codex generated from the transcript"
            filename="AGENTS.md"
            cornerBadge={
              <OpenAIIcon
                aria-hidden="true"
                className={cornerBadgeClasses}
              />
            }
          >
            <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
              <span className="text-muted"># Role & Context</span>
              {'\n\n'}
              You are an AI-directed full-stack engineer{'\n'}
              responsible for both product delivery and{'\n'}
              production support readiness.{'\n\n'}A feature is not
              complete when its code is{'\n'}
              deployed. It is complete only when the team can
              {'\n'}
              detect, diagnose, support, and safely recover{'\n'}
              from failures affecting real users.
              {'\n\n---\n\n'}
              <span className="text-muted"># Core Principle</span>
              {'\n\n'}
              Every production feature must include its{'\n'}
              support system in the same sprint and{'\n'}
              development conversation...
            </pre>
          </ShowcaseCard>
        }
        closing={
          <>
            Every item in your Index has copy-a-segment and copy-all,
            or grab the whole{' '}
            <code className="rounded-sm border border-line bg-surface px-[5px] py-px font-mono text-xs text-ink">
              .md
            </code>{' '}
            file - yours to keep, not stuck behind a login. Claude,
            Cursor, Codex - they all eat markdown.
          </>
        }
      />
    </section>
  );
}
