'use client';

import type { FormEvent } from 'react';
import { useCallback, useEffect, useId, useRef, useState } from 'react';
import { consumePostLoginRedirect } from '@/lib/intake-share-redirect';

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
  const reviewerEmailId = useId();
  const reviewerPasswordId = useId();
  const botUsername = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME;
  const containerRef = useRef<HTMLDivElement>(null);
  const lastAuthUser = useRef<TelegramUser | null>(null);
  const [authState, setAuthState] = useState<AuthState>('idle');
  const [authError, setAuthError] = useState<string | null>(null);
  const [reviewerEmail, setReviewerEmail] = useState('');
  const [reviewerPassword, setReviewerPassword] = useState('');
  // 4xx means Telegram/the server rejected this specific sign-in attempt —
  // reposting the same payload would just fail again, so only network
  // failures and 5xx (worth retrying as-is) get a Retry action.
  const [canRetry, setCanRetry] = useState(false);
  const [widgetState, setWidgetState] = useState<WidgetState>(() =>
    botUsername ? 'loading' : 'error',
  );
  const showDevLogin =
    process.env.NODE_ENV === 'development' &&
    typeof window !== 'undefined' &&
    window.location.hostname === 'localhost';
  const showReviewerLogin =
    process.env.NEXT_PUBLIC_REVIEWER_LOGIN_ENABLED === '1' ||
    process.env.NEXT_PUBLIC_REVIEWER_LOGIN_ENABLED === 'true';

  /**
   * Owns the pending/error state transitions shared by all three sign-in
   * paths below. `catchNetworkRetryable` preserves each path's original
   * behavior on a network failure (dev login never offered Retry there).
   */
  const runAuthAttempt = useCallback(
    async (
      doFetch: () => Promise<Response>,
      onSuccess: () => void,
      statusToError: (status: number) => { message: string; retryable: boolean },
      catchNetworkRetryable = true,
    ) => {
      setAuthState('pending');
      setAuthError(null);
      setCanRetry(false);

      try {
        const res = await doFetch();
        if (res.ok) {
          onSuccess();
          return;
        }
        const { message, retryable } = statusToError(res.status);
        setAuthState('error');
        setCanRetry(retryable);
        setAuthError(message);
      } catch {
        setAuthState('error');
        setCanRetry(catchNetworkRetryable);
        setAuthError(
          'We could not reach the login service. Check your connection and try again.',
        );
      }
    },
    [],
  );

  const authenticate = useCallback(
    (user: TelegramUser) => {
      lastAuthUser.current = user;
      return runAuthAttempt(
        () =>
          fetch('/api/auth/telegram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(user),
          }),
        () => {
          // Hard nav, not router.replace: the (dashboard) layout's restricted
          // flag is derived from cookies server-side, and a soft nav can reuse
          // the Router Cache entry seeded by an earlier anonymous/restricted
          // visit to /feed, landing back on the stale pre-login render.
          window.location.href = consumePostLoginRedirect();
        },
        (status) => {
          const retryable = status >= 500;
          if (!retryable) lastAuthUser.current = null;
          return {
            retryable,
            message:
              status === 401
                ? 'Telegram could not verify this sign-in. Use the Telegram button again.'
                : retryable
                  ? 'We could not complete sign-in. Try again.'
                  : 'We could not complete sign-in. Use the Telegram button again.',
          };
        },
      );
    },
    [runAuthAttempt],
  );

  function retryAuth() {
    if (lastAuthUser.current) {
      void authenticate(lastAuthUser.current);
    }
  }

  function devLogin() {
    return runAuthAttempt(
      () => fetch('/api/auth/dev-login', { method: 'POST' }),
      () => {
        window.location.href = '/feed';
      },
      (status) => ({
        retryable: false,
        message:
          status === 404
            ? 'Dev login is disabled. Set DEV_LOGIN_ENABLED=true in the backend .env.local and restart uvicorn.'
            : 'Dev login failed. Check the backend log and try again.',
      }),
      false,
    );
  }

  function reviewerLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    return runAuthAttempt(
      () =>
        fetch('/api/auth/reviewer-login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: reviewerEmail,
            password: reviewerPassword,
          }),
        }),
      () => {
        window.location.href = consumePostLoginRedirect();
      },
      (status) => ({
        retryable: false,
        message:
          status === 404
            ? 'Reviewer access is disabled.'
            : 'Reviewer sign-in failed. Check the email and code.',
      }),
    );
  }

  useEffect(() => {
    if (!botUsername) {
      return;
    }

    const container = containerRef.current;
    if (!container) return;

    // Scoped to this effect run so cleanup only ever deletes its own
    // handler — never a newer instance's, if one somehow mounted first.
    const handleAuth = async (user: TelegramUser) => {
      await authenticate(user);
    };
    const win = window as unknown as Record<string, unknown>;
    win.onTelegramAuth = handleAuth;

    let cancelled = false;
    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', botUsername);
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
      // Drops the script tag and any iframe telegram-widget.js injected,
      // so a remount never finds a stale widget still sitting in the DOM.
      container.replaceChildren();
      if (win.onTelegramAuth === handleAuth) delete win.onTelegramAuth;
    };
  }, [authenticate, botUsername]);

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
          ref={containerRef}
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
        {showDevLogin && (
          <button
            type="button"
            onClick={devLogin}
            className="inline-flex min-h-10 items-center justify-center rounded-md border border-line bg-raised px-4 text-sm font-medium text-ink transition-ui hover:bg-surface focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface"
          >
            Dev login
          </button>
        )}
        {showReviewerLogin && (
          <form
            onSubmit={reviewerLogin}
            className={`mt-2 flex w-full max-w-[280px] flex-col gap-3 ${align === 'start' ? 'items-start' : 'items-stretch'}`}
          >
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={reviewerEmailId}
                className="text-xs font-medium uppercase text-muted"
              >
                Reviewer access
              </label>
              <input
                id={reviewerEmailId}
                type="email"
                value={reviewerEmail}
                onChange={(event) => setReviewerEmail(event.target.value)}
                autoComplete="email"
                required
                className="min-h-10 rounded-md border border-line bg-raised px-3 text-sm text-ink outline-none transition-ui placeholder:text-muted focus:border-signal focus:ring-2 focus:ring-signal/30"
                placeholder="email"
              />
            </div>
            <input
              id={reviewerPasswordId}
              type="password"
              value={reviewerPassword}
              onChange={(event) => setReviewerPassword(event.target.value)}
              autoComplete="one-time-code"
              required
              aria-label="Reviewer code"
              className="min-h-10 rounded-md border border-line bg-raised px-3 text-sm text-ink outline-none transition-ui placeholder:text-muted focus:border-signal focus:ring-2 focus:ring-signal/30"
              placeholder="code"
            />
            <button
              type="submit"
              disabled={authState === 'pending'}
              className="inline-flex min-h-10 items-center justify-center rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-[background-color,transform] duration-150 ease-out-quart hover:bg-signal-bright disabled:cursor-not-allowed disabled:opacity-60 active:scale-[0.96] focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface motion-reduce:transition-none motion-reduce:active:scale-100"
            >
              Sign in for review
            </button>
          </form>
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
            {canRetry && (
              <button
                type="button"
                onClick={retryAuth}
                className="inline-flex min-h-10 items-center justify-center rounded-md bg-signal px-5 text-sm font-medium text-onsignal transition-[background-color,transform] duration-150 ease-out-quart hover:bg-signal-bright active:scale-[0.96] focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-surface motion-reduce:transition-none motion-reduce:active:scale-100"
              >
                Retry Telegram sign-in
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
