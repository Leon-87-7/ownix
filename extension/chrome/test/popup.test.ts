import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { initPopup, type PopupDeps } from '../src/popup.ts';
import type { IntakeResponseShape } from '../src/api.ts';

function buildDom(): Document {
  const dom = new JSDOM(
    '<body><p id="tab-info"></p><button id="send-btn" disabled>Send to Ownix</button><div id="status"></div><ul id="shortcuts"></ul><p id="shortcut-help"></p></body>',
  );
  return dom.window.document;
}

function fakeDeps(overrides: Partial<PopupDeps> = {}): PopupDeps {
  return {
    getActiveTab: async () => ({ title: 'Example', url: 'https://example.com/page' }),
    sendToOwnix: vi.fn(),
    getOwnixHost: vi.fn(async () => 'https://ownix.test'),
    openTab: vi.fn(),
    getCommands: vi.fn(async () => [
      { name: 'capture-automatic', shortcut: 'Ctrl+Shift+1' },
      { name: 'capture-article', shortcut: 'Ctrl+Shift+2' },
      { name: 'capture-link', shortcut: 'Ctrl+Shift+3' },
      { name: 'capture-document', shortcut: 'Ctrl+Shift+4' },
    ]),
    ...overrides,
  };
}

describe('initPopup', () => {
  it('shows the active tab title/url and enables the button', async () => {
    const doc = buildDom();
    await initPopup(doc, fakeDeps());

    expect(doc.getElementById('tab-info')!.textContent).toBe('Example\nhttps://example.com/page');
    expect((doc.getElementById('send-btn') as HTMLButtonElement).disabled).toBe(false);
    expect(
      [...doc.querySelectorAll('#shortcuts li')].map((row) => row.textContent),
    ).toEqual([
      'AutomaticCtrl+Shift+1',
      'ArticleCtrl+Shift+2',
      'LinkCtrl+Shift+3',
      'DocumentCtrl+Shift+4',
    ]);
    expect(doc.getElementById('shortcut-help')!.textContent).toContain(
      'Windows may suggest defaults',
    );
  });

  it('shows a message when there is no active tab URL', async () => {
    const doc = buildDom();
    await initPopup(doc, fakeDeps({ getActiveTab: async () => undefined }));

    expect(doc.getElementById('tab-info')!.textContent).toMatch(/no page url/i);
    expect((doc.getElementById('send-btn') as HTMLButtonElement).disabled).toBe(true);
  });

  it('success state: sends the tab URL and renders the response text + a dashboard link', async () => {
    const response: IntakeResponseShape = {
      schema_version: 1,
      kind: 'job_created',
      text: 'Received — job_abcd.',
      job_id: 'j1',
      job_url: '/jobs/j1',
      actions: [],
      artifacts: [],
      retryable: false,
    };
    const sendToOwnix = vi.fn().mockResolvedValue(response);
    const doc = buildDom();
    await initPopup(doc, fakeDeps({ sendToOwnix }));

    (doc.getElementById('send-btn') as HTMLButtonElement).click();
    await vi.waitFor(() => {
      expect(doc.getElementById('status')!.textContent).toContain('Received — job_abcd.');
    });
    expect(sendToOwnix).toHaveBeenCalledWith({ url: 'https://example.com/page' });
    expect(doc.querySelector('a')!.textContent).toBe('Open in dashboard');
  });

  it('error state: shows the failure message and re-enables the button', async () => {
    const sendToOwnix = vi.fn().mockRejectedValue(new Error('Rate limit exceeded'));
    const doc = buildDom();
    await initPopup(doc, fakeDeps({ sendToOwnix }));

    (doc.getElementById('send-btn') as HTMLButtonElement).click();
    await vi.waitFor(() => {
      expect(doc.getElementById('status')!.textContent).toBe('Rate limit exceeded');
    });
    expect((doc.getElementById('send-btn') as HTMLButtonElement).disabled).toBe(false);
  });

  it('shows runtime remaps and clearly labels unbound commands', async () => {
    const doc = buildDom();
    await initPopup(doc, fakeDeps({
      getCommands: async () => [
        { name: 'capture-automatic', shortcut: 'Alt+A' },
        { name: 'capture-article', shortcut: '' },
      ],
    }));
    expect(doc.getElementById('shortcuts')!.textContent).toContain('AutomaticAlt+A');
    expect(doc.getElementById('shortcuts')!.textContent).toContain('ArticleUnbound');
    expect(doc.getElementById('shortcuts')!.textContent).toContain('LinkUnbound');
    expect(doc.getElementById('shortcuts')!.textContent).toContain('DocumentUnbound');
    expect(doc.getElementById('shortcut-help')!.textContent).toContain('chrome://extensions/shortcuts');
  });
});
