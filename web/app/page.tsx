import Link from 'next/link';
import Header from '@/components/ui/public-header';
import { HeroGradient } from '@/components/hero-gradient';
import OwnixLogo from '@/app/ownix-logo.svg';

const linkClasses =
  'transition-ui hover:text-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface';
const pipelines = [
  [
    'Videos',
    'Shorts, reels, TikToks, and long YouTube videos become searchable summaries, transcripts, and source-aware notes.',
  ],
  [
    'Repos',
    'Code references can be collected beside the rest of your internet, not stranded in chat history.',
  ],
  [
    'Articles',
    'Links and documents settle into an owned Feed with the context needed to return later.',
  ],
];

const previewRows = [
  ['Indexed', 'Private', 'youtube.com/watch…', 'text-status-done'],
  ['Enriching', 'Feed', 'research paper', 'text-status-enriching'],
  ['Shared', 'Brain', 'semantic link', 'text-contrasignal'],
];

export default function LandingPage() {
  return (
    <main className="relative isolate min-h-screen overflow-hidden bg-canvas text-ink">
      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-6xl flex-col px-5 py-5 sm:px-6 lg:px-8">
        <Header />

        <section className="relative isolate mt-5 grid flex-1 items-center gap-10 overflow-hidden rounded-xl border border-line px-6 py-14 sm:px-10 lg:grid-cols-[minmax(0,1fr)_27rem] lg:px-14 lg:py-[clamp(4rem,8vh,6rem)]">
          <HeroGradient />
          {/* Legibility scrim: text column sits on near-canvas, the shader's
              hot corners stay visible on the panel side. */}
          <div
            aria-hidden="true"
            className="absolute inset-0 -z-10 bg-[linear-gradient(100deg,rgba(13,14,16,0.92)_0%,rgba(13,14,16,0.72)_42%,rgba(13,14,16,0.28)_70%,rgba(13,14,16,0.05)_100%)]"
          />
          <div>
            <p className="font-mono text-xs text-muted">
              Private Index · Owned Feed · Optional Brain
            </p>
            <h1 className="mt-5 max-w-3xl text-balance text-5xl font-semibold leading-[1.02] tracking-[-0.04em] text-ink sm:text-6xl">
              Collect the internet you care about. Return to it with
              context.
            </h1>
            <p className="mt-6 max-w-2xl text-pretty text-base leading-7 text-body sm:text-lg sm:leading-8">
              Ownix saves videos, articles, repos, documents, and
              ideas into a quiet personal Index. Your Feed keeps the
              saved material legible; the Brain turns chosen
              contributions into shared signal.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href="/restricted"
                className="inline-flex h-10 items-center justify-center rounded-md bg-signal px-5 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas"
              >
                Look inside
              </Link>
              <span className="font-mono text-xs text-muted">
                Invite-only while young
              </span>
            </div>
          </div>

          <div className="rounded-lg border border-line bg-canvas/90 p-4">
            <div className="flex items-center justify-between gap-4 border-b border-line pb-3">
              <div>
                <p className="font-mono text-[11px] text-muted">
                  Feed state
                </p>
                <h2 className="mt-1 text-lg font-semibold text-ink">
                  Today’s Index
                </h2>
              </div>
              <span className="rounded border border-line px-2 py-1 font-mono text-[11px] text-contrasignal">
                42 items
              </span>
            </div>
            <div className="mt-4 space-y-2">
              {previewRows.map(([state, scope, item, stateColor]) => (
                <div
                  key={item}
                  className="grid grid-cols-[4.5rem_4rem_minmax(0,1fr)] items-center gap-3 rounded-md border border-line bg-surface px-3 py-2 text-sm"
                >
                  <span
                    className={`font-mono text-[11px] ${stateColor}`}
                  >
                    {state}
                  </span>
                  <span className="font-mono text-[11px] text-muted">
                    {scope}
                  </span>
                  <span className="truncate text-body">{item}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid gap-y-10 py-14 md:grid-cols-3 md:gap-x-12 lg:py-16">
          {pipelines.map(([title, body]) => (
            <div
              key={title}
              className="max-w-[38ch]"
            >
              <h2 className="text-base font-semibold text-ink">
                {title}
              </h2>
              <p className="mt-3 text-sm leading-6 text-body">
                {body}
              </p>
            </div>
          ))}
        </section>
        <footer className="z-10 border-t border-line py-6 text-sm text-muted w-11/12 max-w-7xl mx-auto">
          {/* Below 450px: logo+wordmark grid stacked above a centered nav. At
          450px and up (landing page has no width cap, unlike auth-shell's
          narrower container, so this needs its own breakpoint) they share a
          row — wordmark left, nav right — no dividers either way. */}
          <div className="flex flex-col px-3 gap-3 min-[450px]:flex-row min-[450px]:items-center min-[450px]:justify-between">
            <div className="grid grid-cols-[auto_1fr] items-center gap-x-3">
              <OwnixLogo
                aria-hidden="true"
                focusable="false"
                className="h-10 w-10 "
              />
              <div className="flex flex-col">
                <span className="text-lg font-semibold text-body">
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
      </div>
    </main>
  );
}
