import type { Metadata } from 'next';
import { cookies } from 'next/headers';
import Image from 'next/image';
import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';
import leonAvatar from '@/images/leon-avatar-for-landing.png';
import { HeroGradient } from '@/components/landing/hero-gradient';
import { AppSlot } from '@/components/landing/app-slot';
import { CountUp } from '@/components/landing/count-up';
import { DemoVideo } from '@/components/landing/demo-video';
import { MobileOnboardingStepper } from '@/components/landing/mobile-onboarding-stepper';
import { OnboardingStepper } from '@/components/landing/onboarding-stepper';
import { WordmarkMarquee } from '@/components/landing/wordmark-marquee';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { OpenAIIcon } from '@/components/svg/openai-icon';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { ChromeIcon } from '@/components/svg/chrome-icon';
import { InstagramIcon } from '@/components/svg/instagram-icon';
import { PuzzlePieceIcon } from '@/components/svg/puzzle-piece';
import { MobileDeviceIcon } from '@/components/svg/mobile-device-icon';
import { DesktopIcon } from '@/components/svg/desktop';
import { TelegramLoginWidget } from '@/components/shell/telegram-login-widget';
import { GhostButton } from '@/components/ui/ghost-button';
import PreviewMotif from '@/components/ui/preview-motif';

import {
  Brain,
  ChevronsRight,
  Inbox,
  ListChecks,
  Share,
} from 'lucide-react';

const pageDescription =
  'Share videos, articles, and repos to Ownix from any app. Three taps, and a minute later the transcript and summary are in your Index - searchable, agent-ready markdown.';
const chromeExtensionUrl =
  'https://chromewebstore.google.com/detail/nofmlngkebkapkpjjiieppamfoodkfid?utm_source=item-share-cb';

export const metadata: Metadata = {
  title: 'Ownix - Your internet. Own it',
  description: pageDescription,
  openGraph: {
    title: 'Ownix - Your internet. Own it',
    description: pageDescription,
    type: 'website',
    siteName: 'Ownix',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Ownix - Your internet. Own it',
    description: pageDescription,
  },
};

// Touch devices get 44px targets (WCAG 2.5.5) without changing the 32px
// pointer-device buttons the design system specifies.
const touchTarget =
  '[@media(pointer:coarse)]:h-11 [@media(pointer:coarse)]:px-5';
const btnSignal = `inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-button font-medium leading-none text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep ${touchTarget}`;
const linkClasses =
  'inline-block transition-ui hover:text-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface [@media(pointer:coarse)]:py-3';

const tiles: [string, number][] = [
  ['Items indexed', 318],
  ['Links extracted', 727],
  ['Videos transcribed', 259],
  ['Repos collected', 38],
];

export default async function LandingPage() {
  const signedIn = Boolean(
    (await cookies()).get('vig_session')?.value,
  );

  return (
    <>
      <nav
        id="top"
        aria-label="Main"
        className="border-b border-line bg-canvas lg:sticky lg:top-0 lg:z-40 lg:border-line/70 lg:bg-canvas/85 lg:backdrop-blur-md"
      >
        <div className="mx-auto flex max-w-[1200px] items-center justify-between px-6 py-4">
          <Link
            href="/restricted"
            aria-label={signedIn ? 'Open feed' : 'Look inside'}
            className="group flex items-center gap-2 rounded-md text-xl font-semibold tracking-tight text-ink"
          >
            <OwnixLogo
              aria-hidden="true"
              focusable="false"
              className="h-7 w-7 group-hover:text-signal-bright motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out-quart motion-safe:group-hover:scale-110 motion-safe:group-hover:rotate-[-6deg]"
            />
            <span className="group-hover:text-contrasignal">
              Ownix
            </span>
          </Link>

          <div className="flex items-center gap-2">
            {!signedIn && (
              <Link
                href="/login"
                className={`ml-1 inline-flex h-8 items-center rounded-md border border-line px-3.5 text-button font-medium text-ink transition-ui duration-200 hover:bg-signal hover:text-onsignal ${touchTarget}`}
              >
                Sign in
              </Link>
            )}
            {signedIn && (
              <GhostButton
                as={Link}
                accent="contrasignal"
                href="/logout"
                className={`h-8 bg-transparent px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-canvas ${touchTarget}`}
              >
                Logout
              </GhostButton>
            )}
          </div>
        </div>
      </nav>

      <main className="bg-canvas text-body">
        <header
          className="relative isolate overflow-hidden py-12 lg:flex lg:min-h-[calc(100svh-4.25rem)] lg:items-center lg:py-0"
          id="hero"
        >
          <HeroGradient />
          {/* Legibility scrim. Below lg a flat 90% canvas killed the glow
            entirely; instead lean the scrim left-to-right — strong under the
            left-aligned copy, easing to a fully-transparent right edge so the
            hot corner shows at full strength (no text reaches that far). lg-up
            widens the fade since the 960px wrap keeps text in the dark zone. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-10 bg-[linear-gradient(115deg,rgba(13,14,16,0.75)_0%,rgba(13,14,16,0)_100%)] lg:bg-[linear-gradient(100deg,rgba(13,14,16,0.96)_0%,rgba(13,14,16,0.88)_55%,rgba(13,14,16,0.45)_80%,rgba(13,14,16,0.12)_100%)]"
          />
          {/* Balanced 50/50 split (was 1fr/500px) sized to a fixed fold
            height, so the two halves read as one weight instead of a text
            block plus a decoration, and the onboarding lead-in below
            always starts exactly at the fold instead of overlapping the
            hero text while the stepper pins (prototype: agent-knowledge
            /skills/prototype, branch prototype/landing-fold-variants). */}
          <div className="mx-auto grid w-full max-w-[1200px] gap-8 px-6 lg:grid-cols-2 lg:items-center lg:gap-16">
            <div>
              {/* Golden-ratio hero. The paragraph below is 1rem, so the floor is
                exactly φ × body (1.618rem) and the ceiling is φ² (2.618rem) —
                both ends derived from the body size rather than picked by eye.
                Replaces an arbitrary 30→52px clamp. */}
              <h1 className="text-balance hero-rise mb-6 max-w-[24ch] font-title text-[clamp(1.618rem,6vw,2.618rem)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink [animation-delay:90ms]">
                You watched it. You liked it.{' '}
                <span className="relative inline-block font-subtitle italic text-signal-bright">
                  You lost it.
                  <svg
                    aria-hidden="true"
                    viewBox="0 0 120 12"
                    preserveAspectRatio="none"
                    className="absolute -bottom-1 left-0 h-2 w-full text-contrasignal-bright"
                  >
                    <path
                      d="M2 8 C 20 2, 40 10, 60 6 S 100 2, 118 7"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeLinecap="round"
                    />
                  </svg>
                </span>
              </h1>
              <p className="text-pretty hero-rise mb-8 max-w-[52ch] text-base leading-relaxed text-body [animation-delay:180ms]">
                <span className="font-medium font-subtitle text-ink">
                  &emsp;Ownix remembers - so you can use it. <br />
                </span>{' '}
                Three taps to share from&ensp;
                <AppSlot />
                &ensp;and a minute later you&apos;ve got the
                transcript: ready to paste into your AI as spec and
                context, or pull back up for a script, a citation, a
                note. <br />
                Even if all you remember is a glimpse.
              </p>
              <div className="hero-rise grid overflow-hidden rounded-lg border border-line bg-surface/50 sm:bg-surface/80 sm:grid-cols-3 sm:divide-x sm:divide-line [animation-delay:270ms]">
                <div className="flex flex-col items-start gap-3 border-b border-line p-4 sm:border-b-0">
                  <span className="font-mono text-xs text-muted">
                    Join Ownix
                  </span>
                  <a
                    href="#invite"
                    className={`${btnSignal} w-full`}
                  >
                    Get an invite
                  </a>
                </div>
                <div className="hidden flex-col items-start gap-3 border-b border-line p-4 sm:flex sm:border-b-0">
                  <span className="font-mono text-xs text-muted">
                    Capture this tab
                  </span>
                  <GhostButton
                    as="a"
                    accent="signal"
                    href={chromeExtensionUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={`h-8 w-full gap-2 whitespace-nowrap bg-canvas/70 px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-canvas ${touchTarget}`}
                  >
                    <ChromeIcon
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0"
                    />
                    Install for Chrome
                  </GhostButton>
                </div>
                <div className="flex flex-col items-start gap-3 p-4">
                  <span className="font-mono text-xs text-muted">
                    See the product
                  </span>
                  <GhostButton
                    as={Link}
                    accent="contrasignal"
                    href="/restricted"
                    className={`h-8 w-full bg-canvas/70 px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-canvas ${touchTarget}`}
                  >
                    {signedIn ? 'Open feed' : 'Look inside'}
                  </GhostButton>
                </div>
              </div>
            </div>
            <PreviewMotif
              label="COLLECT OWN RECALL"
              ariaLabel="Ownix collect, own, and recall motif"
              size="fill"
              treatment="hero"
              className="mx-auto hidden aspect-square h-full max-h-[440px] w-full max-w-[440px] lg:flex"
            />
          </div>
        </header>

        <section
          aria-labelledby="onboarding"
          className="border-t border-line py-6"
        >
          <div className="mx-auto max-w-[960px] px-6">
            {/* border-t + NEXT eyebrow on lg: gives the fold a hard stop —
              the onboarding lead-in starts exactly at the fixed-height
              fold's bottom edge instead of visually overlapping the hero
              text above it while the stepper pins. */}
            <div className="hidden sm:block lg:border-t lg:border-line lg:pt-10">
              <h2
                id="onboarding"
                className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
              >
                Three taps. Nothing new to learn.
              </h2>
              <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
                It&apos;s the share sheet you already use - aimed at
                Ownix instead of a friend. Mid-doomscroll,
                mid-commute, mid-anything.
              </p>
            </div>

            <MobileOnboardingStepper />
            <div className="hidden sm:block">
              <OnboardingStepper />
            </div>
            <div className="mt-6 min-w-0 flex-1 hidden sm:block">
              <WordmarkMarquee />
            </div>
          </div>
        </section>

        <section
          aria-labelledby="showcase"
          className="border-t border-line bg-canvas-gradient py-16 sm:bg-canvas"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="showcase"
              className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              Doomscroll in, engineering standards out.
            </h2>

            <div className="mb-8 max-w-[62ch] text-prose leading-relaxed">
              <h3 className="font-subtitle mb-2 text-title font-semibold font-subtitle text-ink">
                &emsp;How I use Ownix
              </h3>
              <p className="text-pretty mb-4">
                An Instagram reel about post-launch support was about
                to scroll past and vanish, like everything does. I
                shared it to Ownix, got the full transcript back, and
                pasted it into Codex - which turned it into the
                support-playbook rules for another project I&apos;m
                building.
              </p>
              <p className="flex items-center gap-2 font-mono text-xs text-muted">
                <Image
                  src={leonAvatar}
                  alt=""
                  sizes="40px"
                  className="h-10 w-10 rounded-full object-cover"
                />
                A real workflow from Leon, building Ownix
              </p>
            </div>

            <div className="grid items-center gap-4 md:grid-cols-[1fr_auto_1fr]">
              <div
                role="group"
                className="relative overflow-hidden rounded-lg border border-line bg-surface"
                aria-label="The actual transcript file"
              >
                <OwnixLogo
                  aria-hidden="true"
                  className="absolute bottom-3 right-3 h-9 w-9 rounded-full border border-line bg-canvas p-1.5 shadow-md"
                />

                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <span className="min-w-0 truncate font-mono text-mono-label tracking-[0.4px] text-muted">
                    20260711_144906_48FB971E_transcript.md
                  </span>
                  <span className="rounded-sm bg-status-done-tint px-1.5 py-0.5 font-mono text-mono-label font-medium tracking-[0.4px] text-status-done">
                    DONE
                  </span>
                </div>
                <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
                  <span className="text-muted"># Transcript</span>
                  {'\n\n'}
                  <span className="text-muted">**Source:**</span>{' '}
                  instagram.com/reel/DamFvyUj3U0
                  {'\n'}
                  <span className="text-muted">
                    **Platform:**
                  </span>{' '}
                  instagram_reels
                  {'\n'}
                  <span className="text-muted">
                    **Processed:**
                  </span>{' '}
                  2026-07-11T14:49:36
                  {'\n\n---\n\n'}
                  Your AI assistant built your app and shipped{'\n'}
                  it to production. Customers, they&apos;re now{'\n'}
                  paying for it. And at 2:00 in the morning,{'\n'}a
                  customer can&apos;t log in. So, tell me, who{'\n'}
                  handles that? Your AI assistant? Probably{'\n'}
                  not, because it&apos;s not connected to your{'\n'}
                  production system. So your AI assistant{'\n'}
                  built the product, but nobody told it to{'\n'}
                  build the support system too...
                </pre>
              </div>

              <ChevronsRight
                aria-hidden="true"
                className="mx-auto rotate-90 text-muted md:rotate-0"
              />

              <div
                role="group"
                className="relative overflow-hidden rounded-lg border border-line bg-surface"
                aria-label="The agent rules file Codex generated from the transcript"
              >
                <OpenAIIcon
                  aria-hidden="true"
                  className="absolute bottom-3 right-3 h-9 w-9 rounded-full border border-line bg-canvas p-1.5 shadow-md"
                />
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <span className="min-w-0 truncate font-mono text-mono-label tracking-[0.4px] text-muted">
                    AGENTS.md
                  </span>
                </div>
                <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
                  <span className="text-muted"># Role & Context</span>
                  {'\n\n'}
                  You are an AI-directed full-stack engineer{'\n'}
                  responsible for both product delivery and{'\n'}
                  production support readiness.{'\n\n'}A feature is
                  not complete when its code is{'\n'}
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
              </div>
            </div>

            <p className="text-pretty mt-6 max-w-[58ch] text-prose leading-relaxed">
              Every item in your Index has copy-a-segment and
              copy-all, or grab the whole{' '}
              <code className="rounded-sm border border-line bg-surface px-[5px] py-px font-mono text-xs text-ink">
                .md
              </code>{' '}
              file - yours to keep, not stuck behind a login. Claude,
              Cursor, Codex - they all eat markdown.
            </p>
          </div>
        </section>

        <section
          aria-labelledby="showcase-checklists"
          className="border-t border-line py-16"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="showcase-checklists"
              className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              Every video becomes a checklist you can run.
            </h2>

            <div className="mb-8 max-w-[62ch] text-prose leading-relaxed">
              <h3 className="font-subtitle mb-2 text-title font-semibold font-subtitle text-ink">
                &emsp;The Checklists button
              </h3>
              <p className="text-pretty mb-4">
                A reel about migrating an AI-built database schema. I
                hit Run Checklists on the job page, and the transcript
                turned into three checks - zero-downtime migrations, a
                rollback plan, a staging mirror - to run against my
                own project before I touched a live table.
              </p>
              <p className="flex items-center gap-2 font-mono text-xs text-muted">
                <Image
                  src={leonAvatar}
                  alt=""
                  sizes="40px"
                  className="h-10 w-10 rounded-full object-cover"
                />
                A real workflow from Leon, building Ownix
              </p>
            </div>

            <div className="grid items-center gap-4 md:grid-cols-[1fr_auto_1fr]">
              <div
                role="group"
                className="relative overflow-hidden rounded-lg border border-line bg-surface"
                aria-label="The job page, ready to run checklists"
              >
                <InstagramIcon
                  aria-hidden="true"
                  className="absolute bottom-3 right-3 h-9 w-9 rounded-full border border-line bg-canvas p-1.5 shadow-md"
                />

                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <span className="min-w-0 truncate font-mono text-mono-label tracking-[0.4px] text-muted">
                    instagram.com/reel/DbyDJomAkQv
                  </span>
                  <span className="rounded-sm bg-status-done-tint px-1.5 py-0.5 font-mono text-mono-label font-medium tracking-[0.4px] text-status-done">
                    DONE
                  </span>
                </div>
                <div className="max-h-[280px] overflow-hidden p-4 [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
                  <h4 className="mb-2 text-sm font-semibold leading-snug text-ink">
                    Database Migrations for AI-Generated Schemas
                  </h4>
                  <p className="mb-4 text-xs leading-relaxed text-body">
                    Your AI built your database, but it never planned
                    for the day you have to change it completely - add
                    a field, rename a column, restructure how two
                    tables relate.
                  </p>
                  <span
                    aria-hidden="true"
                    className={btnSignal}
                  >
                    Run Checklists
                  </span>
                </div>
              </div>

              <ChevronsRight
                aria-hidden="true"
                className="mx-auto rotate-90 text-muted md:rotate-0"
              />

              <div
                role="group"
                className="relative overflow-hidden rounded-lg border border-line bg-surface"
                aria-label="The checklist Ownix generated from the transcript"
              >
                <span
                  aria-hidden="true"
                  className="absolute bottom-3 right-3 flex h-9 w-9 items-center justify-center rounded-full border border-line bg-canvas shadow-md"
                >
                  <ListChecks className="h-5 w-5 text-signal" />
                </span>
                <div className="flex items-center justify-between border-b border-line px-3 py-2">
                  <span className="min-w-0 truncate font-mono text-mono-label tracking-[0.4px] text-muted">
                    checklist_db-migrations.md
                  </span>
                </div>
                <pre className="max-h-[280px] overflow-hidden whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-body [-webkit-mask-image:linear-gradient(to_bottom,black_70%,transparent)] [mask-image:linear-gradient(to_bottom,black_70%,transparent)]">
                  <span className="text-muted">
                    ## Zero-downtime database migrations
                  </span>
                  {'\n\n'}
                  check whether the current project already has
                  {'\n'}
                  zero-downtime migration scripts that add new{'\n'}
                  structures before removing old ones, copy data,
                  {'\n'}
                  switch application usage, and drop old structures
                  {'\n'}
                  only after confirmation, present a report...
                  {'\n\n'}
                  <span className="text-muted">
                    ## Database migration rollback plans
                  </span>
                  {'\n\n'}
                  check whether the current project has a defined
                  {'\n'}
                  rollback plan or script prepared for every{'\n'}
                  migration before it starts, present a report...
                </pre>
              </div>
            </div>

            <p className="text-pretty mt-6 max-w-[58ch] text-prose leading-relaxed">
              This one became six real GitHub issues in this exact
              codebase - a pre-migration snapshot, a restore script, a
              startup guard, a CI dry-run against a sanitized prod
              copy. Each checklist item is phrased as an instruction,
              not a reminder - paste it into your agent and it audits
              the actual codebase, not just your memory of the video.
              Ownix automated the ask; you still did the checking.
            </p>
          </div>
        </section>

        <section
          aria-labelledby="features"
          className="border-t border-line bg-canvas-gradient py-16 sm:bg-canvas"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-start">
              <div>
                {/* <span className="mb-2 block font-mono text-mono-label font-medium tracking-[0.4px] text-contrasignal">
                  INDEX
                </span> */}
                <h2
                  id="features"
                  className="text-pretty mb-3 max-w-[16ch] font-title text-[clamp(1.5rem,4vw,2.25rem)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink"
                >
                  Never lose it again.
                </h2>
                <p className="text-pretty max-w-[52ch] text-prose leading-relaxed text-body">
                  Reels, long videos, articles, repos, screenshots -
                  share it once and it becomes a searchable Index
                  entry: transcript, summary, links, agent-ready
                  markdown.
                </p>
                <p className="mt-3 mb-6 font-mono text-mono-label text-muted">
                  short ◉ long ◉ article ◉ repo ◉ docs
                </p>

                <div className="border-t border-line pt-4 md:pt-5">
                  <h3 className="font-subtitle italic mb-1 text-title font-semibold leading-snug text-ink">
                    &emsp;<span>All your content, in one place</span>
                  </h3>
                  <p className="text-pretty text-copy leading-relaxed text-body">
                    Every item lands in your Feed and Brain. Filter by
                    type, search by title or tag, open anything to
                    grab its full transcript or copy a segment
                    straight into your AI.
                  </p>
                </div>
              </div>

              <div className="flex flex-col divide-y divide-line border-t border-line md:border-t-0">
                <div className="py-4 first:pt-0 md:py-5">
                  {/* <span className="mb-1 block font-mono text-mono-label font-medium tracking-[0.4px] text-muted">
                    DOCS
                  </span> */}
                  <h3 className="mt-4 font-subtitle italic mb-1 flex items-center gap-2 text-title font-semibold leading-snug text-ink">
                    &emsp;
                    <span>
                      That PDF you saved and never reopened?
                    </span>
                  </h3>
                  <p className="text-pretty text-copy leading-relaxed text-body">
                    Upload it - or paste the link - and the Docs page
                    reads it for you: parsed text, a structured
                    briefing, a clean rewrite. All markdown, all ready
                    for your AI.
                  </p>
                  <p className="mt-2 font-mono text-mono-label text-muted">
                    pdf / word / spreadsheet / presentation
                  </p>
                </div>
                <div className="py-4 md:py-5">
                  <h3 className="font-subtitle italic mb-1 flex items-center gap-2 text-title font-semibold leading-snug text-ink">
                    &emsp;
                    <span>
                      Drop a GitHub repo link, skip the clone
                    </span>
                  </h3>
                  <p className="text-pretty text-copy leading-relaxed text-body">
                    Paste a GitHub URL and Ownix reads the README and
                    structure, writes a plain-language breakdown, and
                    files it in your Index next to everything else.
                  </p>
                </div>
                <div className="py-4 md:py-5">
                  <h3 className="font-subtitle italic mb-1 flex items-center gap-2 text-title font-semibold leading-snug text-ink">
                    &emsp;
                    <span>When search stops being enough</span>
                  </h3>
                  <p className="text-pretty text-copy leading-relaxed text-body">
                    Collections group content into a space when
                    &quot;search later&quot; stops working.
                    <br />
                    Recipes save the freestyle prompt you keep
                    re-running, ready to fire again.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section
          aria-labelledby="capture"
          className="border-t border-line py-16"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="capture"
              className="mb-3 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              However you spot it, it ends up in one place.
            </h2>
            <p className="text-pretty mb-8 max-w-[58ch] text-prose leading-relaxed">
              Wherever you spot it - phone, laptop, or a browser tab -
              there&apos;s a one-tap way in.
            </p>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="relative overflow-hidden rounded-lg border border-line bg-surface p-5 sm:col-span-2 sm:grid sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end sm:gap-8">
                <PuzzlePieceIcon
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-8 -right-5 h-40 w-40 -rotate-[28deg] text-line"
                />
                <div className="relative max-w-[58ch]">
                  <ChromeIcon
                    aria-hidden="true"
                    className="mb-3 h-7 w-7 text-muted"
                  />
                  <h3 className="font-subtitle mb-2 text-title font-semibold leading-snug text-ink">
                    Capture the tab while it matters
                  </h3>
                  <p className="text-pretty text-copy leading-relaxed text-body">
                    Use a shortcut or right-click any page, link, or
                    selection. Ownix sends it without breaking your
                    flow.
                  </p>
                </div>
                <GhostButton
                  as="a"
                  accent="signal"
                  href={chromeExtensionUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`relative mt-5 h-8 shrink-0 gap-2 bg-canvas px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-surface sm:mt-0 ${touchTarget}`}
                >
                  <ChromeIcon
                    aria-hidden="true"
                    className="h-4 w-4"
                  />
                  Install for Chrome
                </GhostButton>
              </div>
              <div className="relative overflow-hidden rounded-lg border border-line bg-surface p-4">
                <MobileDeviceIcon
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 -rotate-[35deg] text-line"
                />
                <TelegramIcon
                  aria-hidden="true"
                  className="relative mb-3 h-6 w-6 text-muted"
                />
                <h3 className="font-subtitle relative mb-1 text-title font-semibold leading-snug text-ink">
                  Share sheet muscle memory
                </h3>
                <p className="relative text-pretty text-copy leading-relaxed text-body">
                  Hit share, tap Ownix. Same reflex as sending a
                  friend a reel.
                </p>
              </div>
              <div className="relative overflow-hidden rounded-lg border border-line bg-surface p-4">
                <DesktopIcon
                  aria-hidden="true"
                  className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 -rotate-[35deg] text-line"
                />
                <Inbox
                  aria-hidden="true"
                  className="relative mb-3 h-6 w-6 text-muted"
                />
                <h3 className="font-subtitle relative mb-1 text-title font-semibold leading-snug text-ink">
                  In app intake
                </h3>
                <p className="relative text-pretty text-copy leading-relaxed text-body">
                  Paste a link, run a command, or drop a file straight
                  into the dashboard. Best for PWA users and
                  desktop-first workflows.
                </p>
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-lg border border-line bg-surface">
              <DemoVideo
                src="/demo-capture.mp4"
                poster="/demo-poster.jpg"
                className="block aspect-video w-full border-b border-line bg-canvas"
              />
              <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
                <span className="font-mono text-xs text-body">
                  11:32 shared ◉{' '}
                  <b className="font-medium text-status-done">
                    11:32 reel analysis ready
                  </b>{' '}
                  ◉ 11:33 landed in Dashboard
                </span>
              </div>
            </div>
            <p className="text-pretty font-subtitle italic mt-4 leading-relaxed text-body">
              See how it works in action.{' '}
              <span className="font-mono not-italic text-muted">
                Telegram share sheet flow.
              </span>
            </p>
          </div>
        </section>

        <div className="mx-auto flex max-w-[960px] items-center justify-center gap-3 border-t border-line p-6">
          <Brain
            aria-hidden="true"
            className="h-6 w-6 shrink-0 text-muted"
          />
          <p className="text-pretty text-button leading-normal">
            <span className="font-medium text-ink">
              You won&apos;t remember the title. Your Brain will.
            </span>
            <br />
            <span className="text-muted">
              Every save joins your Brain - searchable by meaning, not
              just keywords.
            </span>
          </p>
        </div>

        <section
          aria-labelledby="stats"
          className="border-t border-line bg-canvas-gradient py-12 sm:bg-canvas"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="stats"
              className="mb-4 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              It compounds - and it&apos;s yours.
            </h2>
            <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
              One month of casual saving, no effort beyond the share
              button:
            </p>

            {/* Below 360px the two-line mono captions misalign the values —
              stack the tiles instead. */}
            <div className="mb-6 grid grid-cols-1 gap-3 min-[360px]:grid-cols-2 md:grid-cols-4">
              {tiles.map(([cap, val], i) => (
                <div
                  key={cap}
                  className="rounded-lg border border-line bg-surface px-4 py-3"
                >
                  <span className="mb-1 block font-mono text-mono-label font-medium uppercase tracking-[0.4px] text-muted">
                    {cap}
                  </span>
                  <span className="text-stat font-semibold leading-[1.1] text-ink tabular-nums">
                    <CountUp
                      value={val}
                      delay={i * 80}
                    />
                  </span>
                </div>
              ))}
            </div>

            <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
              As I was building Ownix I once needed a frontend
              component library I&apos;d seen weeks earlier -
              couldn&apos;t remember its name, just a glimpse of the
              homepage. Searched my Index instead of my memory, and
              there it was in the link table.
            </p>

            <p className="text-pretty mb-6 max-w-[58ch] text-prose leading-relaxed">
              Don&apos;t remember the title either? Search by tag,
              thumbnail, or whatever you do remember, and pull up
              every link a video ever mentioned - long after the video
              itself scrolled off your feed.
            </p>

            <div className="flex mx-auto max-w-[58ch] items-start gap-3 rounded-lg border border-line bg-surface p-4">
              <GoogleDriveIcon className="my-auto h-6 w-6 shrink-0" />
              <p className="text-pretty text-sm leading-normal">
                Everything also lands in your Google Drive as markdown
                - plug in Claude&apos;s or ChatGPT&apos;s Drive
                connector and your AI reads your whole Index directly.
                No export, no copy-paste.
                <br />
                <b className="mt-4 font-subtitle font-medium text-ink">
                  Your files, your account{' '}
                  <span className="font-title font-normal">
                    - leave anytime and lose nothing.
                  </span>
                </b>
              </p>
            </div>
          </div>
        </section>

        <section
          id="invite"
          aria-labelledby="h-invite"
          className="border-t border-line py-10 md:py-14"
        >
          <div className="mx-auto max-w-[960px] px-6">
            {/* The ask (copy) and the action (widget) sit side by side instead
              of stacked, so the column doesn't dead-end in empty space below
              the paragraph. The marquee stays full-card-width below - it's a
              w-max looping track that only reads correctly (and only avoids a
              grid-blowout clip fight) with the full measure to animate across. */}
            <div className="rounded-lg border border-line bg-surface p-8">
              <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-start">
                <div>
                  <h2
                    id="h-invite"
                    className="mb-3 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
                  >
                    Invite-only for now.
                  </h2>
                  <p className="text-pretty max-w-[52ch] text-prose leading-relaxed">
                    Sign in with Telegram and the Ownix bot asks for
                    your email. I approve every member personally,
                    usually within a few hours - and everything you
                    save lands in your own Google Drive from day one,
                    not just ours. Then you&apos;ll get a hello from
                    me, and a question: want to help build what Ownix
                    becomes?
                  </p>
                </div>
                <div>
                  <TelegramLoginWidget align="start" />
                  <p className="text-pretty font-mono text-xs text-muted">
                    no password ◉ the bot asks for your email ◉
                    approval within hours
                  </p>
                </div>
              </div>

              <div className="mt-8 border-t border-line pt-6">
                <div className="flex items-center gap-3">
                  <span className="flex shrink-0 items-center gap-1 text-muted">
                    <Share
                      aria-hidden="true"
                      className="h-4 w-4 shrink-0 "
                    />
                    <span className="block shrink-0 font-mono text-xs font-medium tracking-[0.4px] text-muted">
                      FROM
                    </span>
                  </span>
                  <div className="min-w-0 flex-1">
                    <WordmarkMarquee />
                  </div>
                  <ChevronsRight
                    aria-hidden="true"
                    className="shrink-0 text-muted"
                  />
                  <TelegramIcon
                    aria-hidden="true"
                    className="h-6 w-6 shrink-0"
                  />
                </div>
                <span className="sr-only">
                  Share from Instagram, YouTube, TikTok, GitHub, or
                  articles to Telegram, and it lands transcribed and
                  searchable in your Index.
                </span>
                <p className="mt-6 text-balance text-center text-lead font-medium leading-normal text-ink">
                  Your internet. Own it. &ensp;Reuse it. Find it
                  &ensp;
                  <span className="italic">even from a glimpse.</span>
                </p>
              </div>
            </div>
          </div>
        </section>
      </main>

      <footer className="z-10 border-t border-line py-6 text-sm text-muted w-11/12 max-w-7xl mx-auto">
        {/* Below 450px: logo+wordmark grid stacked above a centered nav. At
          450px and up (landing page has no width cap, unlike auth-shell's
          narrower container, so this needs its own breakpoint) they share a
          row - wordmark left, nav right - no dividers either way. */}
        <div className="flex flex-col px-3 gap-3 min-[450px]:flex-row min-[450px]:items-center min-[450px]:justify-between">
          <div className="grid grid-cols-[auto_1fr] items-center gap-x-3">
            <a
              href="#top"
              aria-label="Back to top"
              className="hover:text-signal-bright"
            >
              <OwnixLogo
                aria-hidden="true"
                focusable="false"
                className="h-10 w-10 motion-safe:transition-transform motion-safe:duration-200 motion-safe:ease-out-quart motion-safe:hover:scale-110 hover:text-contrasignal motion-safe:animate-[ownix-logo-cycle_7s_linear_infinite] motion-safe:hover:rotate-[-6deg]"
              />
            </a>
            <div className="flex flex-col">
              <span className="text-lg font-semibold text-body ">
                Ownix
              </span>
              <span className="text-sm leading-6">
                <span className="italic">your internet,</span>{' '}
                <span className="font-mono">own it.</span>
              </span>
            </div>
          </div>
          <nav className="flex text-body justify-center gap-4 min-[450px]:justify-end">
            <Link
              href="/privacy"
              className={linkClasses}
            >
              Privacy
            </Link>
            <Link
              href="/terms"
              className={linkClasses}
            >
              Terms
            </Link>
          </nav>
        </div>
      </footer>
    </>
  );
}
