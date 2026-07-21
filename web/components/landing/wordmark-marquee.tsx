import { Newspaper } from 'lucide-react';
import { PDFIcon } from '@/components/svg/pdf-icon';
import { GitHubIcon } from '../svg/github-icon';
import { GitHubWordmark } from '@/components/svg/github-wordmark';
import { InstagramIcon } from '../svg/instagram-icon';
import { InstagramWordmark } from '@/components/svg/instagram-wordmark';
import { TikTokWordmark } from '@/components/svg/tiktok-wordmark';
import { YouTubeWordmark } from '@/components/svg/youtube-wordmark';

function Items() {
  return (
    <>
      <span className="flex shrink-0 items-center gap-1 font-mono text-sm font-medium text-ink">
        <InstagramIcon
          focusable="false"
          className="h-7 mb-2 w-auto shrink-0"
        />
        <InstagramWordmark
          focusable="false"
          className="h-5 w-auto shrink-0 text-ink"
        />
      </span>
      <span className="flex shrink-0 items-center gap-1 font-mono text-sm font-medium text-ink">
        <PDFIcon
          focusable="false"
          className="h-9 w-6"
        />
        Documents
      </span>
      <YouTubeWordmark
        focusable="false"
        className="h-5 w-auto shrink-0 text-ink"
      />
      <TikTokWordmark
        focusable="false"
        className="h-5 w-auto shrink-0"
      />
      <span className="flex shrink-0 items-center gap-1 font-mono text-sm font-medium text-ink">
        <GitHubIcon
          focusable="false"
          className="h-5 w-auto shrink-0"
        />
        <GitHubWordmark
          focusable="false"
          className="h-5 w-auto shrink-0 text-ink"
        />
      </span>

      <span className="flex shrink-0 items-center gap-1 font-mono text-sm font-medium text-ink">
        <Newspaper
          focusable="false"
          className="h-9 w-6"
        />
        Articles
      </span>
    </>
  );
}

/** Looping wordmark strip above #invite, reinforcing the hero's "share from
 * any app" line. Purely decorative — the caller composes this alongside the
 * Telegram destination and owns the one accessible description for that
 * whole "from these, to Telegram" sentence (see page.tsx). The track itself
 * is aria-hidden and freezes under reduced motion via the global
 * animation-duration override in globals.css.
 *
 * The track is two identical groups, each with its own trailing `pr-16`
 * spacer matching the internal `gap-16` — not one row of a duplicated array
 * sharing a single gap. That keeps every group's width identical (including
 * the seam), so `translateX(-50%)` lands exactly on the repeat boundary
 * instead of drifting by half a gap. */
export function WordmarkMarquee() {
  return (
    <div
      aria-hidden="true"
      className="relative overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]"
    >
      <div className="flex w-max motion-safe:animate-[wordmark-marquee_28s_linear_infinite_reverse]">
        <div className="flex shrink-0 items-center gap-16 pr-16">
          <Items />
        </div>
        <div className="flex shrink-0 items-center gap-16 pr-16">
          <Items />
        </div>
      </div>
    </div>
  );
}
