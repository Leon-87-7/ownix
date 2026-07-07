import Link from 'next/link';
import { AuthShell } from '@/components/auth-shell';

export default function LogoutPage() {
  return (
    <AuthShell>
      <div className="mt-10 flex w-full max-w-[360px] flex-col items-center rounded-lg border border-line bg-surface px-8 py-7">
        <div
          aria-hidden="true"
          className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-raised text-ink"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="h-5 w-5"
          >
            <path d="M20 6 9 17l-5-5" />
          </svg>
        </div>
        <h2 className="text-balance text-2xl font-semibold tracking-[-0.02em] text-ink">
          Session closed
        </h2>
        <Link
          href="/login"
          className="mt-7 inline-flex min-h-10 items-center justify-center rounded-md bg-signal px-5 text-sm font-medium text-onsignal transition-[background-color,transform] duration-150 ease-out-quart hover:bg-signal-bright active:scale-[0.96] focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
        >
          Sign in with Telegram
        </Link>
      </div>
    </AuthShell>
  );
}
