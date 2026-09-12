// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MagicLinkForm } from './magic-link-form';

beforeEach(() => {
  vi.restoreAllMocks();
});

function typeEmailAndSubmit(email: string) {
  fireEvent.change(screen.getByLabelText('Email address'), {
    target: { value: email },
  });
  fireEvent.click(screen.getByRole('button', { name: /send link/i }));
}

describe('MagicLinkForm', () => {
  it('posts the address and shows the server message', async () => {
    const fetchMock = vi.fn(
      async (..._args: unknown[]) =>
        new Response(
          JSON.stringify({ ok: true, message: 'If that address can receive email, a sign-in link was sent.' }),
        ),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(<MagicLinkForm />);
    typeEmailAndSubmit('reader@example.com');

    expect(
      await screen.findByText(/a sign-in link was sent/i),
    ).toBeTruthy();
    // The test render wrapper fires its own calls (accessibility settings),
    // so pick ours out rather than assuming it lands first.
    const call = fetchMock.mock.calls.find(
      ([url]) => url === '/api/auth/email/request',
    ) as [string, RequestInit] | undefined;
    expect(call).toBeDefined();
    const [, init] = call!;
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ email: 'reader@example.com' });
  });

  it("surfaces the server's detail when the request is rejected", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(JSON.stringify({ detail: 'Too many requests' }), { status: 429 }),
      ),
    );

    render(<MagicLinkForm />);
    typeEmailAndSubmit('reader@example.com');

    await waitFor(() => {
      expect(screen.getByRole('status').textContent).toBe('Too many requests');
    });
  });
});
