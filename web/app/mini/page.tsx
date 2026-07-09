'use client';

import { useEffect, useMemo, useState } from 'react';

declare global {
  interface Window {
    Telegram?: { WebApp?: { initData?: string; ready?: () => void; openLink?: (url: string) => void } };
  }
}

type State = 'booting' | 'ready' | 'connecting' | 'connected' | 'error';

export default function MiniAppPage() {
  const [state, setState] = useState<State>('booting');
  const [message, setMessage] = useState('Verifying Telegram launch data…');
  const [connectUrl, setConnectUrl] = useState('/api/google/connect');

  const initData = useMemo(() => {
    if (typeof window === 'undefined') return '';
    return window.Telegram?.WebApp?.initData || new URLSearchParams(window.location.search).get('tgWebAppData') || '';
  }, []);

  useEffect(() => {
    window.Telegram?.WebApp?.ready?.();
    if (!initData) {
      setState('error');
      setMessage('Open this from the Telegram bot button so Ownix can verify your account.');
      return;
    }

    let cancelled = false;
    fetch('/api/auth/miniapp/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ init_data: initData }),
    })
      .then(async (response) => {
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || 'Telegram verification failed.');
        if (!cancelled) {
          setConnectUrl(body.google_connect_url || '/api/google/connect');
          setState('ready');
          setMessage('Telegram verified. Connect Google to let Ownix create Drive and Sheets outputs for your Index.');
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setState('error');
          setMessage(error.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [initData]);

  function connectGoogle() {
    setState('connecting');
    if (window.Telegram?.WebApp?.openLink) {
      // openLink requires an absolute URL — on native iOS/Android clients it hands
      // the string straight to the platform's URL opener, which can't resolve a
      // relative path and silently does nothing.
      window.Telegram.WebApp.openLink(new URL(connectUrl, window.location.origin).href);
      return;
    }
    window.location.assign(connectUrl);
  }

  const disabled = state !== 'ready';

  return (
    <main className="min-h-dvh bg-canvas px-5 py-6 text-ink">
      <section className="mx-auto flex min-h-[calc(100dvh-3rem)] max-w-md flex-col justify-between rounded-xl border border-line bg-surface p-5">
        <div className="space-y-5">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-balance text-2xl font-semibold tracking-[-0.02em]">Connect Google inside Ownix</h1>
            </div>
            <span className="rounded-md border border-telegram-blue/40 bg-telegram-blue/10 px-2 py-1 font-mono text-[11px] text-telegram-blue">TG</span>
          </div>

          <div className="rounded-lg border border-line bg-canvas p-4">
            <p className="text-sm leading-6 text-body">{message}</p>
          </div>
        </div>

        <button
          type="button"
          disabled={disabled}
          onClick={connectGoogle}
          className="mt-8 h-11 rounded-md bg-signal px-4 text-sm font-medium text-onsignal transition-ui hover:bg-signal-bright focus:outline-none focus:ring-2 focus:ring-signal focus:ring-offset-2 focus:ring-offset-canvas disabled:cursor-not-allowed disabled:bg-raised disabled:text-muted"
        >
          {state === 'connecting' ? 'Opening Google…' : 'Connect Google'}
        </button>
      </section>
    </main>
  );
}
