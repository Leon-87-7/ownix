// @vitest-environment jsdom
import { act, fireEvent, render, screen, waitFor } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GoogleStatusProvider, useGoogleStatus } from './google-status';

function Probe() {
  const { connected, disconnect } = useGoogleStatus();
  return (
    <div>
      <span>state: {connected === null ? 'unknown' : String(connected)}</span>
      <button onClick={() => disconnect()}>disconnect</button>
    </div>
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('GoogleStatusProvider', () => {
  it('fetches /api/google/status once and exposes connected', async () => {
    const fetchMock = vi.fn(async (_input?: RequestInfo | URL) =>
      new Response(JSON.stringify({ connected: true })),
    );
    vi.stubGlobal('fetch', fetchMock);

    render(
      <GoogleStatusProvider>
        <Probe />
      </GoogleStatusProvider>,
    );

    expect(await screen.findByText('state: true')).toBeTruthy();
    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/google/status')).toHaveLength(1);
  });

  it('disconnect POSTs and flips connected for all consumers', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: RequestInfo | URL, init?: RequestInit) =>
        new Response(JSON.stringify({ connected: init?.method !== 'POST' })),
      ),
    );

    render(
      <GoogleStatusProvider>
        <Probe />
      </GoogleStatusProvider>,
    );
    await screen.findByText('state: true');

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'disconnect' }));
    });

    await waitFor(() => expect(screen.getByText('state: false')).toBeTruthy());
    expect(vi.mocked(fetch)).toHaveBeenCalledWith('/api/google/disconnect', { method: 'POST' });
  });

  it('stays unknown when the status fetch fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(null, { status: 500 })));

    render(
      <GoogleStatusProvider>
        <Probe />
      </GoogleStatusProvider>,
    );

    await waitFor(() => expect(screen.getByText('state: unknown')).toBeTruthy());
  });
});
