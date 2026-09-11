import type { Metadata } from 'next';
import Link from 'next/link';
import { AuthShell } from '@/components/shell/auth-shell';
import { OwnixChevronRight } from '@/components/svg/ownix-chevron-right';
import { GitHubIcon } from '@/components/svg/github-icon';
import { GoogleIcon } from '@/components/svg/google-icon';
import { TelegramLoginWidget } from '@/components/shell/telegram-login-widget';
import { MagicLinkForm } from '@/components/shell/magic-link-form';
import { GhostButton } from '@/components/ui/ghost-button';

// Thin auth page - index space is better spent on the landing page.
// follow: true so link equity still flows through to pages this one links to.
export const metadata: Metadata = {
  title: 'Sign in - Ownix',
  robots: { index: false, follow: true },
};

export default function LoginPage() {
  return (
    <AuthShell>
      <div className="mt-10 flex w-full max-w-[360px] flex-col items-center rounded-lg border border-line bg-surface px-8 py-7">
        <h2 className="text-balance text-2xl font-semibold tracking-[-0.02em] text-ink">
          Sign in to your Index
        </h2>
        <p className="mt-2 text-center text-sm leading-6 text-body">
          However you sign in, everything you share starts landing in
          an Index that belongs to you.
        </p>

        <div className="mt-6 flex w-full flex-col gap-3">
          <TelegramLoginWidget />

          {/* Side by side, short labels: two account-only sign-ins are peers,
            so they share one row instead of stacking two full-width blocks.
            aria-label keeps the full phrase for screen readers. */}
          <div className="grid grid-cols-2 gap-2">
            <GhostButton
              as="a"
              href="/api/auth/github/connect"
              aria-label="Continue with GitHub"
              accent="contrasignal"
              className="h-11 w-full gap-2 px-2 text-sm font-medium text-ink"
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
              className="h-11 w-full gap-2 px-2 text-sm font-medium text-ink"
            >
              <GoogleIcon
                aria-hidden="true"
                className="h-[18px] w-[18px] shrink-0"
              />
              Google
            </GhostButton>
          </div>

          <div className="flex items-center gap-3 py-1">
            <span
              aria-hidden="true"
              className="h-px flex-1 bg-line"
            />
            <span className="text-xs text-muted">or</span>
            <span
              aria-hidden="true"
              className="h-px flex-1 bg-line"
            />
          </div>

          <MagicLinkForm />
        </div>

        <p className="mt-2 text-center text-xs leading-5 text-muted">
          Telegram may remember the account shown here. Ownix signs
          you in only after you choose it. GitHub and Google use your
          account email.
        </p>

        <Link
          href="/"
          className="mt-5 rounded-md px-3 py-2 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
        >
          <span className="flex items-center gap-2">
            <OwnixChevronRight className="h-4 w-4 rotate-180" />
            back to Ownix home
          </span>
        </Link>
      </div>
    </AuthShell>
  );
}
