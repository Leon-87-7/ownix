import { describe, expect, it, vi, beforeEach } from 'vitest';
import { buildIntakePayload, getOwnixHost, sendToOwnix, setOwnixHost } from '../src/api';

function fakeChromeStorage(initial: Record<string, unknown> = {}) {
  const store = { ...initial };
  return {
    storage: {
      local: {
        get: vi.fn(async (key: string) => ({ [key]: store[key] })),
        set: vi.fn(async (items: Record<string, unknown>) => {
          Object.assign(store, items);
        }),
      },
    },
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
  vi.stubGlobal('crypto', { randomUUID: () => 'test-uuid' });
});

describe('buildIntakePayload', () => {
  it('prefers a URL over text when both are present', () => {
    expect(buildIntakePayload({ url: 'https://example.com', text: 'note' })).toEqual({
      url: 'https://example.com',
    });
  });

  it('falls back to text when there is no URL', () => {
    expect(buildIntakePayload({ text: 'a note' })).toEqual({ text: 'a note' });
  });

  it('trims whitespace', () => {
    expect(buildIntakePayload({ url: '  https://example.com  ' })).toEqual({
      url: 'https://example.com',
    });
  });

  it('throws when neither URL nor text is present', () => {
    expect(() => buildIntakePayload({})).toThrow(/nothing to send/i);
  });
});

describe('getOwnixHost / setOwnixHost', () => {
  it('returns the default host when nothing is stored', async () => {
    vi.stubGlobal('chrome', fakeChromeStorage());
    expect(await getOwnixHost()).toBe('https://app.leondev.xyz');
  });

  it('returns a saved allowlisted host, normalized to its origin', async () => {
    vi.stubGlobal('chrome', fakeChromeStorage());
    await setOwnixHost('http://localhost:8000/path');
    expect(await getOwnixHost()).toBe('http://localhost:8000');
  });

  it('rejects anything outside the Ownix host allowlist instead of storing it', async () => {
    vi.stubGlobal('chrome', fakeChromeStorage());
    await expect(setOwnixHost('javascript:alert(1)')).rejects.toThrow(/must be one of/i);
    await expect(setOwnixHost('https://custom.example.com')).rejects.toThrow(/must be one of/i);
  });
});

describe('sendToOwnix', () => {
  it('throws when the extension has not been paired yet (no stored token)', async () => {
    vi.stubGlobal('chrome', fakeChromeStorage({ ownixHost: 'http://localhost:8000' }));
    vi.stubGlobal('fetch', vi.fn());

    await expect(sendToOwnix({ url: 'https://example.com/a' })).rejects.toThrow(/not paired/i);
  });

  it('posts the payload with an Idempotency-Key header and a bearer token, never a cookie', async () => {
    vi.stubGlobal(
      'chrome',
      fakeChromeStorage({ ownixHost: 'http://localhost:8000', ownixExtensionToken: 'paired-token' }),
    );
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          schema_version: 1,
          kind: 'job_created',
          text: 'Received.',
          job_id: 'j1',
          actions: [],
          artifacts: [],
          retryable: false,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal('fetch', fetchMock);

    const result = await sendToOwnix({ url: 'https://example.com/a' });

    expect(fetchMock).toHaveBeenCalledWith(
      'http://localhost:8000/api/intake/message',
      expect.objectContaining({
        method: 'POST',
        credentials: 'omit',
        headers: expect.objectContaining({
          'Idempotency-Key': 'test-uuid',
          Authorization: 'Bearer paired-token',
        }),
      }),
    );
    expect(result.job_id).toBe('j1');
  });

  it('throws the server detail message on a non-2xx response', async () => {
    vi.stubGlobal(
      'chrome',
      fakeChromeStorage({ ownixHost: 'http://localhost:8000', ownixExtensionToken: 'paired-token' }),
    );
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: 'Rate limited' }), { status: 429 })),
    );

    await expect(sendToOwnix({ url: 'https://example.com/a' })).rejects.toThrow(/rate limited/i);
  });
});
