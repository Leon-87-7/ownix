import type { ReactNode } from 'react';
import { DemoVideo } from '@/components/landing/demo-video';
import { GhostButton } from '@/components/ui/ghost-button';
import { ChromeIcon } from '@/components/svg/chrome-icon';
import { DesktopIcon } from '@/components/svg/desktop';
import { DiscordIcon } from '@/components/svg/discord-icon';
import { MobileDeviceIcon } from '@/components/svg/mobile-device-icon';
import { PuzzlePieceIcon } from '@/components/svg/puzzle-piece';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { Inbox } from 'lucide-react';
import { chromeExtensionUrl, touchTarget } from './shared';

// Cards that share the same shape: a decorative oversized bg icon in the
// corner, a small icon row, a heading, and a body paragraph. The Chrome
// capture card below is the odd one out (it spans both columns and carries
// a CTA), so it stays hand-written rather than forced into this shape.
const simpleCards: {
  key: string;
  bgIcon: ReactNode;
  iconRow: ReactNode;
  heading: string;
  body: string;
}[] = [
  {
    key: 'share-sheet',
    bgIcon: (
      <MobileDeviceIcon
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 -rotate-[35deg] text-line"
      />
    ),
    iconRow: (
      <div className="relative mb-3 flex items-center gap-2.5">
        <TelegramIcon
          aria-hidden="true"
          className="h-6 w-6"
        />
        <DiscordIcon
          aria-hidden="true"
          className="h-6 w-6"
        />
      </div>
    ),
    heading: 'Share sheet muscle memory',
    body: 'Hit share, tap Ownix. Same reflex as sending a friend a reel.',
  },
  {
    key: 'in-app-intake',
    bgIcon: (
      <DesktopIcon
        aria-hidden="true"
        className="pointer-events-none absolute -bottom-4 -right-4 h-28 w-28 -rotate-[35deg] text-line"
      />
    ),
    iconRow: (
      <Inbox
        aria-hidden="true"
        className="relative mb-3 h-6 w-6 text-muted"
      />
    ),
    heading: 'In app intake',
    body: 'Paste a link, run a command, or drop a file straight into the dashboard. Best for PWA users and desktop-first workflows.',
  },
];

export function CaptureSection() {
  return (
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
                selection. Ownix sends it without breaking your flow.
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

          {simpleCards.map((card) => (
            <div
              key={card.key}
              className="relative overflow-hidden rounded-lg border border-line bg-surface p-4"
            >
              {card.bgIcon}
              {card.iconRow}
              <h3 className="font-subtitle relative mb-1 text-title font-semibold leading-snug text-ink">
                {card.heading}
              </h3>
              <p className="relative text-pretty text-copy leading-relaxed text-body">
                {card.body}
              </p>
            </div>
          ))}
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
  );
}
