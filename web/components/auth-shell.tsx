import type { ReactNode } from 'react';

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-canvas px-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/backgrounds/layered-waves-log.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 w-full select-none opacity-50 [filter:saturate(0.5)] [mask-image:linear-gradient(to_top,black_55%,transparent)]"
      />

      <section className="relative z-10 flex w-full -translate-y-[55px] flex-col items-center text-center">
        <div className="flex w-full animate-[auth-card-enter_480ms_cubic-bezier(0.25,1,0.5,1)_both] flex-col items-center motion-reduce:animate-none">
          <h1 className="sr-only">vig — Video Intelligence Gateway</h1>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/images/vig_logo_lockup.svg"
            alt="vig"
            className="h-16 w-auto"
          />
          <p className="mt-4 text-sm text-body">
            Video Intelligence Gateway
          </p>
          {children}
        </div>
      </section>
    </main>
  );
}
