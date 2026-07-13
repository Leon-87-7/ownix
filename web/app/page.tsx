import type { Metadata } from 'next';
import Link from 'next/link';
import OwnixLogo from '@/app/ownix-logo.svg';
import { HeroGradient } from '@/components/hero-gradient';
import { AppSlot } from '@/components/landing/app-slot';
import { CountUp } from '@/components/landing/count-up';
import { GoogleDriveIcon } from '@/components/svg/google-drive-icon';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { ChevronsRight } from 'lucide-react';

const pageDescription =
  'Share videos, articles, and repos to Ownix from any app. Three taps, and a minute later the transcript and summary are in your Index - searchable, agent-ready markdown.';

export const metadata: Metadata = {
  title: 'Ownix - Your internet, indexed',
  description: pageDescription,
  openGraph: {
    title: 'Ownix - Your internet, indexed',
    description: pageDescription,
    type: 'website',
    siteName: 'Ownix',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Ownix - Your internet, indexed',
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
  ['SHORT · REELS · TIKTOK', 'text-type-short'],
  ['LONG VIDEO', 'text-type-long'],
  ['ARTICLE · PDF', 'text-type-article'],
  ['REPO', 'text-type-repo'],
];

const tiles: [string, number][] = [
  ['Items indexed', 260],
  ['Links extracted', 623],
  ['Videos transcribed', 207],
  ['Repos collected', 35],
];

export default function LandingPage() {
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
        <header className="relative isolate overflow-hidden py-12">
          <HeroGradient />
          {/* Legibility scrim. Below lg the copy spans nearly the full hero
            width, so the left-to-right gradient would leave its right edge
            over barely-scrimmed shader — flat 90% canvas there; the gradient
            (hot corners surviving on the right) is lg-up only, where the
            960px wrap keeps text inside the 0.88 zone. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-10 bg-canvas/90 lg:bg-transparent lg:bg-[linear-gradient(100deg,rgba(13,14,16,0.96)_0%,rgba(13,14,16,0.88)_55%,rgba(13,14,16,0.45)_80%,rgba(13,14,16,0.12)_100%)]"
          />
          <div className="mx-auto max-w-[960px] px-6">
            <p className="text-pretty hero-rise mb-4 text-sm font-medium text-muted">
              The friend you send everything to.
            </p>
            <h1 className="hero-rise mb-6 max-w-[16ch] text-[clamp(30px,6vw,52px)] font-semibold leading-[1.15] tracking-[-0.5px] text-ink [animation-delay:90ms]">
              You watched it. You liked it.{' '}
              <span className="text-muted">You lost it.</span>
            </h1>
            <p className="text-pretty hero-rise mb-8 max-w-[56ch] text-base leading-relaxed text-body [animation-delay:180ms]">
              Share to Ownix from &ensp; <AppSlot />{' '}
              <span>
                <ChevronsRight className="inline-block ml-1 mr-3" />
              </span>
              three taps, and a minute later it&apos;s in your{' '}
              <span className="font-medium text-ink">Index</span>:
              transcribed, summarized, searchable, ready to paste into
              your AI.
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
                Look inside
              </Link>
              <span className="ml-2 font-mono text-xs text-muted">
                invite-only for now
              </span>
            </div>
          </div>
        </header>

        <section
          aria-labelledby="h-capture"
          className="border-t border-line py-12"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="h-capture"
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
              {/*
              DROP THE SCREEN RECORDING HERE.
              Replace the placeholder div with:
              <video controls preload="metadata" poster="/demo-poster.jpg" className="block w-full">
                <source src="/demo-capture.mp4" type="video/mp4" />
              </video>
              Recording flow: YouTube share sheet -> Telegram bot reply -> item in the Ownix feed.
            */}
              <div className="flex aspect-video flex-col items-center justify-center gap-3 border-b border-line bg-canvas">
                <div
                  aria-hidden="true"
                  className="flex h-12 w-12 items-center justify-center rounded-full border border-line-strong text-body"
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 16 16"
                    fill="currentColor"
                  >
                    <path d="M4 2.5v11l9-5.5z" />
                  </svg>
                </div>
                <p className="text-pretty font-mono text-xs text-muted">
                  demo-capture.mp4 · share sheet → bot → Index
                </p>
              </div>
              <div className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
                <span className="font-mono text-xs text-body">
                  17:24 shared ·{' '}
                  <b className="font-medium text-status-done">
                    17:24 transcript ready
                  </b>{' '}
                  · 17:30 full analysis
                </span>
                <span className="text-xs font-medium text-muted">
                  Demo film coming - those timestamps are real.
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
          aria-labelledby="h-agent"
          className="border-t border-line py-16"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="h-agent"
              className="mb-4 text-[clamp(22px,3.4vw,28px)] font-semibold leading-tight tracking-[-0.25px] text-ink"
            >
              Doomscroll in, engineering standards out.
            </h2>

            <div className="grid items-start gap-6 md:grid-cols-2">
              <div className="text-[15px] leading-relaxed">
                <p className="text-pretty mb-4">
                  An Instagram reel about post-launch support was
                  about to fly past me, like everything does. I shared
                  it to Ownix, got the full transcript back, and
                  pasted it into Codex - which turned it into the
                  support-playbook rules for another project I&apos;m
                  building.
                </p>
                <p className="text-pretty mb-4">
                  A reel became rules in a production codebase.
                </p>
                <p className="text-pretty font-mono text-xs text-muted">
                  - Leon, building Ownix
                </p>
              </div>

              <div
                role="group"
                className="overflow-hidden rounded-lg border border-line bg-surface"
                aria-label="The actual transcript file"
              >
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
          aria-labelledby="h-compounds"
          className="border-t border-line py-12"
        >
          <div className="mx-auto max-w-[960px] px-6">
            <h2
              id="h-compounds"
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
              Browse by thumbnail, search by title or topic, and pull
              up every link a video ever mentioned - the course, the
              repo, the tool - long after the video itself scrolled
              away.
            </p>

            <div className="flex max-w-[58ch] items-start gap-3 rounded-lg border border-line bg-surface p-4">
              <GoogleDriveIcon className="my-auto h-[18px] w-[18px] shrink-0" />
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
          className="border-t border-line py-16 md:py-20"
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
                Sign in with Telegram and the bot will ask for your
                email. I approve every member personally, usually
                within a few hours. Then you&apos;ll get a hello from
                me, asking if you want to help build what Ownix
                becomes.
              </p>
              <Link
                href="/login"
                className="inline-flex h-9 items-center gap-2 rounded-full bg-telegram-blue px-4 text-[13px] font-medium leading-none text-canvas transition-[filter] duration-150 ease-out hover:brightness-[1.08] [@media(pointer:coarse)]:h-11"
              >
                <TelegramIcon />
                Sign in with Telegram
              </Link>
              <p className="text-pretty mt-3 font-mono text-xs text-muted">
                no password · the bot collects your email · approval
                within hours.
              </p>
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-[960px] px-6">
          <p className="text-pretty border-t border-line py-6 text-[13px] text-muted">
            A shared Brain is growing quietly underneath all of this -
            early members shape it.
          </p>
        </div>
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
                className="h-10 w-10 transition-transform duration-200 ease-out-quart hover:scale-110 hover:text-contrasignal hover:rotate-[-6deg]"
              />
            </a>
            <div className="flex flex-col">
              <span className="text-lg font-semibold text-body ">
                Ownix
              </span>
              <span className="text-sm leading-6">
                <span className="italic">your internet,</span>{' '}
                <span className="font-mono">indexed.</span>
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
