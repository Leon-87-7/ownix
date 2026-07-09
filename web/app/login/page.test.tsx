// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './page';

const replace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace }),
}));

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
  afterEach(() => {
    vi.unstubAllGlobals();
    replace.mockReset();
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

    render(<LoginPage />);

    act(() => {
      void (window as unknown as { onTelegramAuth: (user: typeof telegramUser) => Promise<void> })
        .onTelegramAuth(telegramUser);
    });

    expect(screen.getByText('Signing you in...')).toBeInTheDocument();

    await act(async () => {
      resolveFetch(new Response(JSON.stringify({ ok: true })));
    });

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'));
  });

  it('shows an inline retry when Telegram auth is rejected', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: 'Retry Telegram sign-in' }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
