import Link from 'next/link';
import { MoveLeft } from 'lucide-react';
import { AuthShell } from '@/components/shell/auth-shell';
import { GoogleIcon } from '@/components/svg/google-icon';
import { TelegramLoginWidget } from '@/components/shell/telegram-login-widget';

export default function LoginPage() {
  return (
    <AuthShell>
      <div className="mt-10 flex w-full max-w-[360px] flex-col items-center rounded-lg border border-line bg-surface px-8 py-7">
        <h2 className="text-balance text-2xl font-semibold tracking-[-0.02em] text-ink">
          Sign in to your Index
        </h2>
        <p className="mt-2 text-center text-sm leading-6 text-body">
          Sign in to save your own links and unlock actions.
        </p>

        <div className="mt-6 w-full">
          <TelegramLoginWidget />
        </div>

        <div
          className="mt-5 w-full px-3 py-2 text-center text-sm text-muted"
          aria-disabled="true"
        >
          <div className="inline-flex h-8 items-center justify-center rounded-md bg-signal-deep/80 px-3.5 text-[13px] font-medium text-onsignal">
            Connect to <GoogleIcon className="ml-2 h-4 w-4" />
          </div>
          <span className="ml-2">locked until approval</span>
        </div>

        <Link
          href="/"
          className="mt-5 rounded-md px-3 py-2 text-sm font-medium text-body transition-ui hover:bg-raised hover:text-ink focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
        >
          <span className="flex items-center gap-2">
            <MoveLeft className="h-4 w-4" />
            back to Ownix home
          </span>
        </Link>
      </div>
    </AuthShell>
  );
}
