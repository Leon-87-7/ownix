import { describe, expect, it, vi } from 'vitest';
import { JSDOM } from 'jsdom';
import { initPopup, type PopupDeps } from '../src/popup';
import type { IntakeResponseShape } from '../src/api';

function buildDom(): Document {
  const dom = new JSDOM(
    '<body><p id="tab-info"></p><button id="send-btn" disabled>Send to Ownix</button><div id="status"></div></body>',
  );
  return dom.window.document;
}

function fakeDeps(overrides: Partial<PopupDeps> = {}): PopupDeps {
  return {
    getActiveTab: async () => ({ title: 'Example', url: 'https://example.com/page' }),
    sendToOwnix: vi.fn(),
    getOwnixHost: vi.fn(async () => 'https://ownix.test'),
    openTab: vi.fn(),
    ...overrides,
  };
}

describe('initPopup', () => {
  it('shows the active tab title/url and enables the button', async () => {
    const doc = buildDom();
    await initPopup(doc, fakeDeps());

    expect(doc.getElementById('tab-info')!.textContent).toBe('Example\nhttps://example.com/page');
    expect((doc.getElementById('send-btn') as HTMLButtonElement).disabled).toBe(false);
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
});
