'use client';

import { useCallback, useEffect, useId, useRef, useState } from 'react';

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

// The real telegram-widget.js button, not a styled link to /login — a page
// that links to /login just to show this same widget costs the user an extra
// click-and-wait for no reason. Shared by the landing page's invite section
// and /login itself.
export function TelegramLoginWidget({
  align = 'center',
}: {
  align?: 'center' | 'start';
}) {
  const containerId = useId();
  const lastAuthUser = useRef<TelegramUser | null>(null);
  const [authState, setAuthState] = useState<AuthState>('idle');
  const [authError, setAuthError] = useState<string | null>(null);
  const [widgetState, setWidgetState] =
    useState<WidgetState>('loading');

  const authenticate = useCallback(async (user: TelegramUser) => {
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
        // Hard nav, not router.replace: the (dashboard) layout's restricted
        // flag is derived from cookies server-side, and a soft nav can reuse
        // the Router Cache entry seeded by an earlier anonymous/restricted
        // visit to /feed, landing back on the stale pre-login render.
        window.location.href = '/feed';
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
  }, []);

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

    const container = document.getElementById(containerId);
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
  }, [authenticate, containerId]);

  return (
    <div className="flex w-full flex-col">
      <div
        className={`flex min-h-12 w-full flex-col gap-3 ${align === 'start' ? 'items-start' : 'items-center'}`}
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
          id={containerId}
          className={
            widgetState === 'error'
              ? 'hidden'
              : `flex ${align === 'start' ? 'justify-start' : 'justify-center'}`
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
        className="mt-3 min-h-6"
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
            className={`flex flex-col gap-3 ${align === 'start' ? 'items-start' : 'items-center'}`}
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
  );
}
