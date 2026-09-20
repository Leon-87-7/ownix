import type { ReactNode } from 'react';
import { GhostButton, GhostLinkButton } from '@/components/ui/ghost-button';
import { DiscordIcon } from '@/components/svg/discord-icon';
import { TelegramIcon } from '@/components/svg/telegram-icon';
import { touchTarget } from './shared';

function ChannelRow({
  icon,
  heading,
  body,
  cta,
}: {
  icon: ReactNode;
  heading: string;
  body: ReactNode;
  cta: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center">
      {icon}
      <div className="min-w-0 flex-1">
        <h3 className="font-subtitle mb-0.5 text-title font-semibold italic leading-snug text-ink">
          {heading}
        </h3>
        <p className="text-pretty text-copy leading-relaxed text-body">
          {body}
        </p>
      </div>
      {cta}
    </div>
  );
}

export function SubmissionChannelsSection({
  telegramDeepLink,
}: {
  telegramDeepLink: string | null;
}) {
  return (
    <section
      aria-labelledby="submission-channels"
      className="border-t border-line py-16"
    >
      <div className="mx-auto max-w-[960px] px-6">
        <h2
          id="submission-channels"
          className="mb-3 font-title text-[clamp(1.375rem,3.4vw,1.75rem)] font-semibold leading-tight tracking-[-0.25px] text-ink"
        >
          Two ways to send it in.
        </h2>
        <p className="text-pretty mb-8 max-w-[58ch] text-prose leading-relaxed">
          DM the bot on Telegram, or drop it in our Discord - either way
          it lands transcribed and searchable in your Index within a
          minute.
        </p>

        <div className="overflow-hidden rounded-lg border border-line bg-surface">
          <div className="border-b border-line">
            <ChannelRow
              icon={
                <TelegramIcon
                  aria-hidden="true"
                  className="h-7 w-7 shrink-0"
                />
              }
              heading="DM the bot directly"
              body="Paste a link straight into the chat - same account you sign in with, no share sheet required."
              cta={
                <GhostButton
                  as="a"
                  accent="contrasignal"
                  href={telegramDeepLink ?? '#invite'}
                  {...(telegramDeepLink
                    ? { target: '_blank', rel: 'noopener noreferrer' }
                    : {})}
                  className={`h-9 shrink-0 px-3.5 text-button font-medium leading-none text-ink ${touchTarget}`}
                >
                  Message the bot
                </GhostButton>
              }
            />
          </div>

          <ChannelRow
            icon={
              <DiscordIcon
                aria-hidden="true"
                className="h-7 w-7 shrink-0"
              />
            }
            heading="Drop it in Discord"
            body="Sign in, then pair your account from the dashboard and DM the bot - same pipeline, same Index."
            cta={
              <GhostLinkButton
                accent="contrasignal"
                href="/login"
                className={`h-9 shrink-0 px-3.5 text-button font-medium leading-none text-ink ${touchTarget}`}
              >
                Sign in to pair
              </GhostLinkButton>
            }
          />
        </div>

        <p className="mt-4 font-mono text-xs text-muted">
          no share sheet ◉ no context switch ◉ same Index either way
        </p>
      </div>
    </section>
  );
}
