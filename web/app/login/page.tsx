'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

export default function LoginPage() {
  const router = useRouter();

  useEffect(() => {
    (window as unknown as Record<string, unknown>).onTelegramAuth =
      async (user: TelegramUser) => {
        const res = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(user),
        });
        if (res.ok) {
          router.replace('/');
        }
      };

    const container = document.getElementById('tg-login-container');
    if (!container) return;

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute(
      'data-telegram-login',
      process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME ?? '',
    );
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');
    script.setAttribute('data-request-access', 'write');
    script.async = true;
    container.appendChild(script);

    return () => {
      delete (window as unknown as Record<string, unknown>)
        .onTelegramAuth;
      script.remove();
    };
  }, [router]);

  return (
    <main className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-canvas px-6">
      {/* Layered waves, anchored to the bottom. Muted to dusty tones + dropped
          opacity so the motif recedes into the dark plate (matching the
          dashboard's PageBackground treatment) — DESIGN.md keeps orange as the
          one rationed signal, so the bg never competes with it. The top-fading
          mask melts the crest into the canvas, regardless of image height.
          Decorative → AT-hidden. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/backgrounds/layered-waves-log.svg"
        alt=""
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 bottom-0 w-full select-none opacity-50 [filter:saturate(0.5)] [mask-image:linear-gradient(to_top,black_55%,transparent)]"
      />

      <div className="relative z-10 flex -translate-y-[55px] flex-col items-center text-center">
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
        <p className="mt-10 text-xs uppercase tracking-widest text-muted">
          Sign in to your console
        </p>
        <div
          id="tg-login-container"
          className="mt-4 flex justify-center"
        />
      </div>
    </main>
  );
}
