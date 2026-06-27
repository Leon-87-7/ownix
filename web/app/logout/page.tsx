import Link from 'next/link';

export default function LogoutPage() {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-canvas px-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/backgrounds/layered-waves-log.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 w-full select-none opacity-50 [filter:saturate(0.5)] [mask-image:linear-gradient(to_top,black_55%,transparent)]"
      />

      <section className="relative z-10 flex -translate-y-[55px] flex-col items-center text-center">
        <div className="flex animate-[logout-card-enter_480ms_cubic-bezier(0.25,1,0.5,1)_both] flex-col items-center motion-reduce:animate-none">
          <h1 className="sr-only">vig — Video Intelligence Gateway</h1>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/vig_logo_lockup.svg"
            alt="vig"
            className="h-16 w-auto"
          />
          <p className="mt-4 text-sm text-body">Video Intelligence Gateway</p>

          <div className="mt-10 rounded-xl bg-surface/85 p-3 shadow-[0_0_0_1px_rgba(38,42,49,0.9),0_18px_60px_-34px_rgba(246,146,30,0.55)] backdrop-blur-sm">
            <div className="flex max-w-[360px] flex-col items-center rounded-lg bg-canvas/70 px-8 py-7 shadow-[inset_0_0_0_1px_rgba(52,58,68,0.75)]">
              <div
                aria-hidden="true"
                className="mb-5 flex h-10 w-10 items-center justify-center rounded-lg bg-status-done-tint text-status-done shadow-[inset_0_0_0_1px_rgba(74,222,128,0.18)]"
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
              <p className="text-xs uppercase tracking-widest text-muted">
                Session closed
              </p>
              <h2 className="mt-3 text-balance text-2xl font-semibold tracking-[-0.02em] text-ink">
                See you soon
              </h2>
              <p className="mt-3 text-pretty text-sm leading-6 text-body">
                You&apos;ve been signed out successfully.
              </p>
              <Link
                href="/login"
                className="mt-7 inline-flex min-h-10 items-center justify-center rounded-md bg-signal px-5 text-sm font-medium text-onsignal transition-[background-color,transform] duration-150 ease-out-quart hover:bg-signal-bright active:scale-[0.96] focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas"
              >
                Sign in with Telegram
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
