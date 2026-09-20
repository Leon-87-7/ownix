import Link from 'next/link';
import { HeroGradient } from '@/components/landing/hero-gradient';
import { AppSlot } from '@/components/landing/app-slot';
import { GhostButton, GhostLinkButton } from '@/components/ui/ghost-button';
import PreviewMotif from '@/components/ui/preview-motif';
import { ChromeIcon } from '@/components/svg/chrome-icon';
import { btnSignal, chromeExtensionUrl, touchTarget } from './shared';

// Same arrow stroke as OwnixChevron (components/svg/ownix-chevron-down.tsx),
// rebased to a local 0,0 origin so it works as a raw CSS clip-path() —
// unrotated, since the 90deg turn is applied afterward via `transform`
// (clip-path is computed in local space before transforms apply).
const ownixChevronClipPath =
  "path('M 2.250 1.634 C 1.563 2.330, 1.000 3.938, 1.000 5.207 L 1.000 7.513 17.750 26.343 C 43.777 55.601, 61.335 75.447, 78.149 94.611 L 93.600 112.222 94.800 116.227 C 96.485 121.852, 96.262 126.325, 94.054 131.189 C 93.009 133.492, 83.681 144.924, 73.326 156.593 C 62.972 168.262, 52.700 179.890, 50.500 182.434 C 48.300 184.977, 37.496 197.170, 26.490 209.529 C 15.485 221.888, 5.247 233.497, 3.740 235.327 C 0.445 239.327, 0.192 242.997, 3.104 244.556 L 5.208 245.682 28.854 245.262 L 52.500 244.843 58.500 242.642 C 61.800 241.432, 66.813 238.908, 69.641 237.034 L 74.781 233.625 119.017 184.812 C 144.304 156.909, 164.046 134.287, 165.104 132.000 C 167.320 127.213, 167.556 118.711, 165.597 114.218 C 164.195 111.000, 154.233 99.623, 112.000 53.004 C 99.625 39.343, 86.276 24.529, 82.336 20.083 C 74.747 11.521, 67.567 6.478, 58.127 3.082 L 52.500 1.058 28.000 0.712 L 3.500 0.367 2.250 1.634 Z')";

export function Hero({ signedIn }: { signedIn: boolean }) {
  return (
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
            <span className="mb-2 font-medium font-subtitle text-ink">
              &emsp;Ownix remembers - so you can use it. <br />
            </span>{' '}
            Three taps to share from&ensp;
            <AppSlot />
            &ensp;and a minute later you&apos;ve got the transcript:
            ready to paste into your AI as spec and context, or pull
            back up for a script, a citation, a note. <br />
            Even if all you remember is a glimpse.
          </p>
          {/* Mobile-only: variant B from the CTA sketches (prototype:
            agent-knowledge/skills/prototype) — one dominant button, the
            second action demoted to a plain link instead of a second
            full-width button in a bordered card. Desktop keeps the
            three-up card below untouched. */}
          <div className="hero-rise flex flex-col items-center gap-3 sm:hidden [animation-delay:270ms]">
            <a
              href="#invite"
              className={`${btnSignal} w-full`}
            >
              Get an invite
            </a>
            <Link
              href="/restricted"
              className="font-subtitle inline-flex items-center gap-1 py-1 text-button font-medium text-body underline decoration-contrasignal-bright underline-offset-4 transition-ui  [@media(pointer:coarse)]:py-3"
            >
              {signedIn ? 'Go to your Feed page' : 'Look inside the product'}{' '}
            </Link>
          </div>

          <div className="hero-rise hidden overflow-hidden rounded-lg border border-line bg-surface/50 sm:grid sm:bg-surface/80 sm:grid-cols-3 sm:divide-x sm:divide-line [animation-delay:270ms]">
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
              <GhostLinkButton
                accent="contrasignal"
                href="/restricted"
                className={`h-8 w-full bg-canvas/70 px-3.5 text-button font-medium leading-none text-ink focus-visible:ring-offset-canvas ${touchTarget}`}
              >
                {signedIn ? 'Open Feed' : 'Look inside'}
              </GhostLinkButton>
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

      {/* The fixed-height fold (see comment above) centers its content,
        leaving empty space below it on lg. Rather than leave that dead
        air unexplained, it doubles as a real jump-to-next-section link.
        `pointer-events-none` on the link plus `-auto` on the clipped
        glyph is deliberate: clip-path clips hit-testing as well as
        paint, so this makes only the chevron's own silhouette
        clickable rather than its whole invisible bounding box. */}
      <a
        href="#onboarding"
        aria-label="Scroll to see how it works"
        className="hero-scroll-cue pointer-events-none absolute inset-x-0 bottom-8 hidden justify-center focus:outline-none focus-visible:ring-2 focus-visible:ring-signal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas lg:flex"
      >
        <span className="relative h-7 w-10">
          <span
            className="ownix-shimmer-bg pointer-events-auto absolute left-1/2 top-1/2 h-[246px] w-[168px] blur-[1px]"
            style={{
              clipPath: ownixChevronClipPath,
              transform: 'translate(-50%, -50%) rotate(90deg) scale(0.1626)',
            }}
          />
        </span>
      </a>
    </header>
  );
}
