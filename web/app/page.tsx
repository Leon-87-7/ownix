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
import { WordmarkMarquee } from '@/components/landing/wordmark-marquee';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { OpenAIIcon } from '@/components/svg/openai-icon';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { TelegramLoginWidget } from '@/components/shell/telegram-login-widget';
import {
  ChevronsRight,
  MessageSquareQuote,
  Share,
} from 'lucide-react';

const pageDescription =
  'Share videos, articles, and repos to Ownix from any app. Three taps, and a minute later the transcript and summary are in your Index - searchable, agent-ready markdown.';

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
const btnGhost = `inline-flex h-8 items-center justify-center rounded-md border border-line border-b-2 border-b-contrasignal-deep bg-transparent px-3.5 text-[13px] font-medium leading-none text-ink transition-ui hover:bg-raised ${touchTarget}`;
const btnSignal = `inline-flex h-8 items-center justify-center rounded-md bg-signal px-3.5 text-[13px] font-medium leading-none text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep ${touchTarget}`;
const linkClasses =
  'inline-block transition-ui hover:text-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface [@media(pointer:coarse)]:py-3';

const indexBadges = [
  ['SHORT ◉ REELS ◉ TIKTOK', 'text-type-short'],
  ['LONG VIDEO', 'text-type-long'],
  ['ARTICLE ◉ PDF', 'text-type-article'],
  ['REPO', 'text-type-repo'],
];

const tiles: [string, number][] = [
  ['Items indexed', 318],
  ['Links extracted', 727],
  ['Videos transcribed', 259],
  ['Repos collected', 38],
];

export default function LandingPage() {
  // Session-aware CTA: logged-in visitors see "Open feed", anonymous ones
  // "Look inside". vig_session is httpOnly, so this has to be a server read —
  // which opts the landing page into dynamic rendering. /restricted handles
  // the actual routing (approved -> feed, else -> preview) either way.
  const signedIn = Boolean(cookies().get('vig_session')?.value);
  return (
    <>
      <nav
        id="top"
        aria-label="Main"
        className="border-b border-line bg-canvas"
      >
        <div className="mx-auto flex max-w-[960px] items-center justify-between px-6 py-4">
          <Link
            href="/"
            aria-label="Ownix home"
            className={`group flex items-center gap-2 rounded-md text-xl font-semibold tracking-tight text-ink`}
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
            <Link
              href="/login"
              className={`ml-1 inline-flex h-8 items-center rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-ui duration-200 hover:bg-signal hover:text-onsignal ${touchTarget}`}
            >
              Sign in
            </Link>
          </div>
        </div>
      </nav>

      <main className="bg-canvas text-body">
        <header
          className="relative isolate overflow-hidden py-12"
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
          <div className="mx-auto max-w-[960px] px-6">
            <h1 className="hero-rise mb-6 max-w-[16ch] text-[clamp(30px,6vw,52px)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink [animation-delay:90ms]">
              You watched it. You liked it.{' '}
              <span className="text-muted">You lost it.</span>
            </h1>
            <p className="text-pretty hero-rise mb-8 max-w-[56ch] text-base leading-relaxed text-body [animation-delay:180ms]">
              <span className="font-medium text-ink">
                Ownix remembers. <br />
              </span>{' '}
              Three taps to share from&ensp;
              <AppSlot />
              &ensp;and a minute later it&apos;s transcribed,
              summarized, searchable - even when all you remember is a
              glimpse. <br />
              Paste it straight into your AI.
            </p>
            <div className="hero-rise flex flex-wrap items-center gap-3 [animation-delay:270ms]">
              <a
                href="#invite"
                className={btnSignal}
              >
                Get an invite
              </a>
              <Link
                href="/restricted"
                className={btnGhost}
              >
                {signedIn ? 'Open feed' : 'Look inside'}
              </Link>
              <span className="ml-2 font-mono text-xs text-muted">
                invite-only for now
              </span>
            </div>
          </div>
        </header>

        <section
          aria-labelledby="demo"
          className="border-t border-line py-12"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="demo"
              className="mb-4 text-[clamp(22px,3.4vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              Three taps. Nothing new to learn.
            </h2>
            <p className="text-pretty mb-6 max-w-[58ch] text-[15px] leading-relaxed">
              It&apos;s the share sheet you already use - aimed at
              Ownix instead of a friend. Mid-doomscroll, mid-commute,
              mid-anything: share it, keep scrolling. Ownix does the
              reading.
            </p>

            <div className="overflow-hidden rounded-lg border border-line bg-surface">
              {/* Recording flow: YouTube share sheet -> Telegram bot reply -> item in the Ownix feed. */}
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

            <div
              role="group"
              className="mt-6 flex flex-wrap gap-2"
              aria-label="What Ownix indexes"
            >
              {indexBadges.map(([label, color]) => (
                <span
                  key={label}
                  className={`rounded-sm border border-line px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-[0.4px] ${color}`}
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </section>

        <section
          aria-labelledby="showcase"
          className="border-t border-line py-16"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="showcase"
              className="mb-4 text-[clamp(22px,3.4vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              Doomscroll in, engineering standards out.
            </h2>

            <div className="mb-8 max-w-[68ch] text-[15px] leading-relaxed">
              <p className="text-pretty mb-4">
                &quot;&ensp;An Instagram reel about post-launch
                support was about to fly past me, like everything
                does. I shared it to Ownix, got the full transcript
                back, and pasted it into Codex - which turned it into
                the support-playbook rules for another project
                I&apos;m building.&ensp;&quot;
              </p>
              <p className="text-pretty mb-4 ml-2 border-l-2 border-line pl-4 text-[15px] leading-relaxed text-muted">
                A reel became rules in a production codebase.
              </p>
              <p className="flex items-center gap-2 font-mono text-xs text-muted">
                <Image
                  src={leonAvatar}
                  alt=""
                  className="h-10 w-10 rounded-full object-cover"
                />
                Leon (me), building Ownix
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
                  <span className="min-w-0 truncate font-mono text-[11px] tracking-[0.4px] text-muted">
                    20260711_144906_48FB971E_transcript.md
                  </span>
                  <span className="rounded-sm bg-status-done-tint px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-[0.4px] text-status-done">
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
                  <span className="min-w-0 truncate font-mono text-[11px] tracking-[0.4px] text-muted">
                    AGENTS.md
                  </span>
                  {/* <span className="rounded-sm bg-status-done-tint px-1.5 py-0.5 font-mono text-[11px] font-medium tracking-[0.4px] text-status-done">
                    DONE
                  </span> */}
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

            <p className="text-pretty mt-6 max-w-[58ch] text-[15px] leading-relaxed">
              Every item in your Index has copy-a-segment and
              copy-all, or grab the whole{' '}
              <code className="rounded-sm border border-line bg-surface px-[5px] py-px font-mono text-xs text-ink">
                .md
              </code>{' '}
              file. Claude, Cursor, Codex - they all eat markdown.
            </p>
          </div>
        </section>

        <section
          aria-labelledby="features"
          className="border-t border-line py-16"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <div className="grid gap-8 md:grid-cols-[1.1fr_1fr] md:items-start">
              <div>
                <span className="mb-2 block font-mono text-[11px] font-medium tracking-[0.4px] text-contrasignal">
                  INDEX
                </span>
                <h2
                  id="features"
                  className="text-pretty mb-3 max-w-[16ch] text-[clamp(24px,4vw,36px)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink"
                >
                  Reverse the feed, Own it.
                </h2>
                <p className="text-pretty max-w-[52ch] text-[15px] leading-relaxed text-body">
                  Reels, long videos, articles, repos, screenshots -
                  share it once and it becomes a searchable Index
                  entry: transcript, summary, links, agent-ready
                  markdown.
                </p>
                <p className="mt-3 font-mono text-[11px] text-muted">
                  short ◉ long ◉ article ◉ repo
                </p>
              </div>

              <div className="flex flex-col divide-y divide-line border-t border-line md:border-t-0">
                <div className="py-4 first:pt-0 md:py-5">
                  <span className="mb-1 block font-mono text-[11px] font-medium tracking-[0.4px] text-muted">
                    FEED
                  </span>
                  <h3 className="mb-1 text-[16px] font-semibold leading-snug text-ink">
                    Your personal search-engine
                  </h3>
                  <p className="text-pretty text-[14px] leading-relaxed text-body">
                    Every item lands in your Feed. Filter by type,
                    search by title or tag, open anything to grab its
                    full transcript or copy a segment straight into
                    your AI.
                  </p>
                </div>
                <div className="py-4 md:py-5">
                  <span className="mb-1 block font-mono text-[11px] font-medium tracking-[0.4px] text-muted">
                    DOCS
                  </span>
                  <h3 className="mb-1 text-[16px] font-semibold leading-snug text-ink">
                    That PDF you saved and never reopened?
                  </h3>
                  <p className="text-pretty text-[14px] leading-relaxed text-body">
                    Upload it - or paste the link - and the Docs page
                    reads it for you: parsed text, a structured
                    briefing, a clean rewrite. All markdown, all ready
                    for your AI.
                  </p>
                  <p className="mt-2 font-mono text-[11px] text-muted">
                    pdf today ◉ word / spreadsheet / presentation /
                    image - soon
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <div className="mx-auto flex max-w-[960px] items-center justify-center gap-3 border-t border-line p-6">
          <MessageSquareQuote className="h-4 w-6 shrink-0" />
          <p className="text-pretty text-[13px] text-muted leading-normal">
            A shared Brain is growing quietly underneath all of this -
            early members shape it.
          </p>
        </div>

        <section
          aria-labelledby="stats"
          className="border-t border-line py-12"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="stats"
              className="mb-4 text-[clamp(22px,3.4vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              It compounds - and it&apos;s yours.
            </h2>
            <p className="text-pretty mb-6 max-w-[58ch] text-[15px] leading-relaxed">
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
                  <span className="mb-1 block font-mono text-[11px] font-medium uppercase tracking-[0.4px] text-muted">
                    {cap}
                  </span>
                  <span className="text-[28px] font-semibold leading-[1.1] text-ink tabular-nums">
                    <CountUp
                      value={val}
                      delay={i * 80}
                    />
                  </span>
                </div>
              ))}
            </div>

            <p className="text-pretty mb-6 max-w-[58ch] text-[15px] leading-relaxed">
              As I was building Ownix I once needed a frontend
              component library I&apos;d seen weeks earlier -
              couldn&apos;t remember its name, just a glimpse of the
              homepage. Searched my Index instead of my memory, and
              there it was in the link table.
            </p>

            <p className="text-pretty mb-6 max-w-[58ch] text-[15px] leading-relaxed">
              Don&apos;t remember the title either? Search by tag,
              thumbnail, or whatever you do remember, and pull up
              every link a video ever mentioned - long after it
              scrolled away.
            </p>

            <div className="flex mx-auto max-w-[58ch] items-start gap-3 rounded-lg border border-line bg-surface p-4">
              <GoogleDriveIcon className="my-auto h-6 w-6 shrink-0" />
              <p className="text-pretty text-sm leading-normal">
                Everything also lands in your Google Drive as
                markdown.
                <br />
                <b className="font-medium text-ink">
                  Your files, your account - leave anytime and lose
                  nothing.
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
            <div className="rounded-lg border border-line bg-surface p-8">
              <h2
                id="h-invite"
                className="mb-3 text-[clamp(22px,3.4vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink"
              >
                Invite-only for now.
              </h2>
              <p className="text-pretty mb-6 max-w-[52ch] text-[15px] leading-relaxed">
                Sign in with Telegram and the Ownix bot asks for your
                email. I approve every member personally, usually
                within a few hours. Then you&apos;ll get a hello from
                me - and a question: want to help build what Ownix
                becomes?
              </p>
              <TelegramLoginWidget align="start" />
              <p className="text-pretty font-mono text-xs text-muted">
                no password ◉ the bot asks for your email ◉ approval
                within hours
              </p>

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
                <p className="mt-6 text-balance text-center text-[17px] font-medium leading-normal text-ink">
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
