// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './page';

const telegramUser = {
  id: 87,
  first_name: 'Lee',
  auth_date: 1,
  hash: 'signed',
};

function telegramScript() {
  const script = document.querySelector<HTMLScriptElement>(
    'script[src="https://telegram.org/js/telegram-widget.js?22"]',
  );
  if (!script) throw new Error('Telegram script was not appended');
  return script;
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.stubEnv('NEXT_PUBLIC_TELEGRAM_BOT_USERNAME', 'ownix_bot');
    vi.stubEnv('NODE_ENV', 'development');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('shows the unavailable fallback when no bot username is configured', () => {
    vi.stubEnv('NEXT_PUBLIC_TELEGRAM_BOT_USERNAME', '');

    render(<LoginPage />);

    expect(
      screen.getByText('Telegram sign-in is unavailable right now. Refresh the page or check your connection.'),
    ).toBeInTheDocument();
    expect(
      document.querySelector('script[src="https://telegram.org/js/telegram-widget.js?22"]'),
    ).not.toBeInTheDocument();
  });

  it('reserves space while the Telegram widget loads', () => {
    render(<LoginPage />);

    expect(screen.getByText('Sign in to your Index')).toBeInTheDocument();
    expect(screen.getByText('Loading Telegram sign-in')).toBeInTheDocument();
  });

  it('shows a fallback when the Telegram widget fails to load', async () => {
    render(<LoginPage />);

    fireEvent.error(telegramScript());

    expect(
      await screen.findByText('Telegram sign-in is unavailable right now. Refresh the page or check your connection.'),
    ).toBeInTheDocument();
  });

  it('announces pending auth and redirects after a successful Telegram auth', async () => {
    let resolveFetch: (response: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve;
          }),
      ),
    );

    // Login must hard-navigate (not router.replace) so the (dashboard)
    // layout's cookie-derived restricted state is recomputed server-side
    // instead of reusing a Router Cache entry from a pre-login visit.
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, href: '' },
    });

    render(<LoginPage />);

    act(() => {
      void (window as unknown as { onTelegramAuth: (user: typeof telegramUser) => Promise<void> })
        .onTelegramAuth(telegramUser);
    });

    expect(screen.getByText('Signing you in...')).toBeInTheDocument();

    await act(async () => {
      resolveFetch(new Response(JSON.stringify({ ok: true })));
    });

    await waitFor(() => expect(window.location.href).toBe('/feed'));

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });

  it('shows the rejection message without a retry action for a 401', async () => {
    const fetchMock = vi.fn(async () => new Response('no', { status: 401 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<LoginPage />);

    await act(async () => {
      await (window as unknown as { onTelegramAuth: (user: typeof telegramUser) => Promise<void> })
        .onTelegramAuth(telegramUser);
    });

    expect(
      screen.getByText('Telegram could not verify this sign-in. Use the Telegram button again.'),
    ).toBeInTheDocument();

    // Reposting the same rejected Telegram payload can't succeed — no point offering retry.
    expect(
      screen.queryByRole('button', { name: 'Retry Telegram sign-in' }),
    ).not.toBeInTheDocument();
  });

  it('offers a working retry for a server error', async () => {
    const fetchMock = vi.fn(async () => new Response('no', { status: 500 }));
    vi.stubGlobal('fetch', fetchMock);

    render(<LoginPage />);

    await act(async () => {
      await (window as unknown as { onTelegramAuth: (user: typeof telegramUser) => Promise<void> })
        .onTelegramAuth(telegramUser);
    });

    expect(
      screen.getByText('We could not complete sign-in. Try again.'),
    ).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Retry Telegram sign-in' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it('shows a localhost dev login fallback that uses the backend dev endpoint', async () => {
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: { ...originalLocation, hostname: 'localhost', href: '' },
    });
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true })));
    vi.stubGlobal('fetch', fetchMock);

    render(<LoginPage />);

    fireEvent.click(screen.getByRole('button', { name: 'Dev login' }));

    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/auth/dev-login', { method: 'POST' }),
    );
    await waitFor(() => expect(window.location.href).toBe('/feed'));

    Object.defineProperty(window, 'location', {
      configurable: true,
      value: originalLocation,
    });
  });
});
