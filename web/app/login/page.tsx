'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { MoveLeft } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { AuthShell } from '@/components/auth-shell';
import { GoogleIcon } from '@/components/svg/google-icon';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  photo_url?: string;
  auth_date: number;
  hash: string;
}

type AuthState = 'idle' | 'pending' | 'error';
type WidgetState = 'loading' | 'ready' | 'error';

export default function LoginPage() {
  const router = useRouter();
  const lastAuthUser = useRef<TelegramUser | null>(null);
  const [authState, setAuthState] = useState<AuthState>('idle');
  const [authError, setAuthError] = useState<string | null>(null);
  const [widgetState, setWidgetState] =
    useState<WidgetState>('loading');

  const authenticate = useCallback(
    async (user: TelegramUser) => {
      lastAuthUser.current = user;
      setAuthState('pending');
      setAuthError(null);

      try {
        const res = await fetch('/api/auth/telegram', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(user),
        });

        if (res.ok) {
          router.replace('/feed');
          return;
        }

        setAuthState('error');
        setAuthError(
          res.status === 401
            ? 'Telegram could not verify this sign-in. Use the Telegram button again.'
            : 'We could not complete sign-in. Try again.',
        );
      } catch {
        setAuthState('error');
        setAuthError(
          'We could not reach the login service. Check your connection and try again.',
        );
      }
    },
    [router],
  );

  function retryAuth() {
    if (lastAuthUser.current) {
      void authenticate(lastAuthUser.current);
      return;
    }

    setAuthState('idle');
    setAuthError(null);
  }

  useEffect(() => {
    (window as unknown as Record<string, unknown>).onTelegramAuth =
      async (user: TelegramUser) => {
        await authenticate(user);
      };

    const container = document.getElementById('tg-login-container');
    if (!container) return;

    let cancelled = false;
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
    script.onload = () => {
      if (!cancelled) setWidgetState('ready');
    };
    script.onerror = () => {
      if (!cancelled) setWidgetState('error');
    };
    container.appendChild(script);

    return () => {
      cancelled = true;
      delete (window as unknown as Record<string, unknown>)
        .onTelegramAuth;
      script.remove();
    };
  }, [authenticate]);

  return (
    <AuthShell>
      <div className="mt-10 flex w-full max-w-[360px] flex-col items-center rounded-lg border border-line bg-surface px-8 py-7">
        <h2 className="text-balance text-2xl font-semibold tracking-[-0.02em] text-ink">
          Sign in to your Index
        </h2>
        <p className="mt-2 text-center text-sm leading-6 text-body">
          Sign in to save your own links and unlock actions.
        </p>

        <div
          className="mt-6 flex min-h-12 w-full flex-col items-center justify-center gap-3"
          aria-busy={authState === 'pending'}
        >
          {widgetState === 'loading' && (
            <div
              role="status"
              className="h-10 w-[238px] animate-pulse rounded-md border border-line bg-raised motion-reduce:animate-none"
            >
              <span className="sr-only">
                Loading Telegram sign-in
              </span>
            </div>
          )}
          <div
            id="tg-login-container"
            className={
              widgetState === 'error'
                ? 'hidden'
                : 'flex justify-center'
            }
          />
          {widgetState === 'error' && (
            <p
              role="alert"
              className="text-sm leading-6 text-status-error"
            >
              Telegram sign-in is unavailable right now. Refresh the
              page or check your connection.
            </p>
          )}
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
            Back to landing page
          </span>
        </Link>

        <div
          className="mt-5 min-h-6"
          aria-live="polite"
        >
          {authState === 'pending' && (
            <p
              role="status"
              className="text-sm text-body"
            >
              Signing you in...
            </p>
          )}
          {authError && (
            <div
              role="alert"
              className="flex flex-col items-center gap-3"
            >
              <p className="text-sm leading-6 text-status-error">
                {authError}
              </p>
              <button
                type="button"
                onClick={retryAuth}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-signal px-5 text-sm font-medium text-onsignal transition-[background-color,transform] duration-150 ease-out-quart hover:bg-signal-bright active:scale-[0.96] focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
              >
                Retry Telegram sign-in
              </button>
            </div>
          )}
        </div>
      </div>
    </AuthShell>
  );
}
