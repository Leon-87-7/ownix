import { JSDOM } from 'jsdom';
import { readFileSync } from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { initOptions } from '../src/options';

function buildDom(): Document {
  const html = readFileSync('options.html', 'utf8');
  const dom = new JSDOM(html);
  return dom.window.document;
}

function fakeChromeStorage(initial: Record<string, unknown> = {}) {
  const store = { ...initial };
  return {
    storage: {
      local: {
        get: vi.fn(async (key: string) => ({ [key]: store[key] })),
        set: vi.fn(async (items: Record<string, unknown>) => {
          Object.assign(store, items);
        }),
        remove: vi.fn(async (key: string) => {
          delete store[key];
        }),
      },
    },
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('initOptions', () => {
  it('pairs without host controls on the production options page', async () => {
    vi.stubGlobal('chrome', fakeChromeStorage());
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ token: 'paired-token' }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    const doc = buildDom();
    await initOptions(doc);
    expect(doc.getElementById('connection-status')!.textContent).toBe('Not connected.');

    (doc.getElementById('pairing-code') as HTMLInputElement).value = 'abc123';
    (doc.getElementById('pair') as HTMLButtonElement).click();

    await vi.waitFor(() => {
      expect(doc.getElementById('pairing-status')!.textContent).toBe('Paired successfully.');
    });
    expect(fetchMock).toHaveBeenCalledWith(
      'https://app.leondev.xyz/api/extension/token',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(doc.getElementById('connection-status')!.textContent).toBe('Connected to Ownix.');
  });
});
