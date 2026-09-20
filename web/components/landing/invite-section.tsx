import { WordmarkMarquee } from '@/components/landing/wordmark-marquee';
import { DestinationSlot } from '@/components/landing/destination-slot';
import { MagicLinkForm } from '@/components/shell/magic-link-form';
import { TelegramLoginWidget } from '@/components/shell/telegram-login-widget';
import { GhostButton } from '@/components/ui/ghost-button';
import { GitHubIcon } from '@/components/svg/github-icon';
import { GoogleIcon } from '@/components/svg/google-icon';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { Share } from 'lucide-react';
import { touchTarget } from './shared';

export function InviteSection() {
  return (
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
                <span className="block mb-2">Invite-only for now</span>
                <span className="block font-subtitle italic text-pretty text-[clamp(1rem,3.4vw,1.3rem)]">
                  Here&apos;s exactly what happens next.
                </span>
              </h2>
              <ol className="max-w-[52ch] list-decimal space-y-2 pl-5 text-pretty text-prose leading-relaxed">
                <li>
                  Sign in with Telegram, GitHub, Google, or an emailed
                  link. No password either way.
                </li>
                <li>
                  I approve every member myself, usually within a few
                  hours.
                </li>
                <li>
                  Your saves start landing in your own Google Drive that
                  day - not just ours.
                </li>
                <li>
                  Then you hear from me, with one question: what do you
                  want Ownix to become?
                </li>
              </ol>
            </div>
            <div>
              {/* Telegram sits alone above the divider on purpose: it is
                the only route that also connects the bot you send links
                to, so it is the recommended path rather than one of four
                equal options. The rest are account-only sign-ins. */}
              <div className="mb-3 flex max-w-[320px] flex-col gap-3">
                <span className="font-mono text-xs text-muted">
                  Sign in with Telegram
                </span>
                <TelegramLoginWidget align="start" />
                <span className="text-pretty text-xs leading-5 text-muted">
                  Connects the bot you send links to, so you can start
                  saving straight away.
                </span>

                <div className="flex items-center gap-3 py-1">
                  <span
                    aria-hidden="true"
                    className="h-px flex-1 bg-line"
                  />
                  <span className="font-mono text-xs text-muted">or</span>
                  <span
                    aria-hidden="true"
                    className="h-px flex-1 bg-line"
                  />
                </div>

                {/* Side by side, short labels: two account-only sign-ins
                  are peers, so they share one row instead of stacking two
                  full-width blocks. aria-label keeps the full phrase for
                  screen readers. */}
                <div className="grid grid-cols-2 gap-2">
                  <GhostButton
                    as="a"
                    href="/api/auth/github/connect"
                    aria-label="Continue with GitHub"
                    accent="contrasignal"
                    className={`h-11 w-full gap-2 px-2 text-button font-medium text-ink ${touchTarget}`}
                  >
                    <GitHubIcon
                      aria-hidden="true"
                      className="h-[18px] w-[18px] shrink-0"
                    />
                    GitHub
                  </GhostButton>
                  <GhostButton
                    as="a"
                    href="/api/auth/google/connect"
                    aria-label="Continue with Google"
                    accent="contrasignal"
                    className={`h-11 w-full gap-2 px-2 text-button font-medium text-ink ${touchTarget}`}
                  >
                    <GoogleIcon
                      aria-hidden="true"
                      className="h-[18px] w-[18px] shrink-0"
                    />
                    Google
                  </GhostButton>
                </div>
                <MagicLinkForm />
                <span className="text-pretty text-xs leading-5 text-muted">
                  Pair Telegram or Discord later from Settings.
                </span>
              </div>
              <p className="text-pretty font-mono text-xs text-muted">
                no password ◉ approval within hours ◉ your files leave
                with you
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
                <OwnixChevronRight
                  aria-hidden="true"
                  className="h-6 w-6 shrink-0 text-muted/60"
                />
              </span>
              <div className="min-w-0 flex-1">
                <WordmarkMarquee />
              </div>
              <OwnixChevronRight
                aria-hidden="true"
                className="h-6 w-6 shrink-0 text-muted/60"
              />
              <DestinationSlot />
            </div>
            <span className="sr-only">
              Share from Instagram, YouTube, TikTok, GitHub, or articles
              to Telegram, Discord, or the Chrome extension, and it
              lands transcribed and searchable in your Index.
            </span>
            <p className="mt-6 text-balance text-center text-lead font-medium leading-normal text-ink">
              Your internet.&emsp;Find it, use it, own it -
              <span className="italic font-subtitle">
                even from a glimpse.
              </span>
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
