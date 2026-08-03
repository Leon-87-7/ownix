/** Toolbar popup: read the active tab, "Send to Ownix" (issue #478). */

import { buildIntakePayload, getOwnixHost, sendToOwnix, type IntakeResponseShape } from './api.js';

export interface PopupDeps {
  getActiveTab: () => Promise<{ title?: string; url?: string } | undefined>;
  sendToOwnix: typeof sendToOwnix;
  getOwnixHost: typeof getOwnixHost;
  openTab: (url: string) => void;
}

const defaultDeps: PopupDeps = {
  getActiveTab: async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return tab;
  },
  sendToOwnix,
  getOwnixHost,
  openTab: (url: string) => {
    chrome.tabs.create({ url });
  },
};

/** Wires the popup DOM to `deps`. Exported (not auto-run) so tests can pass a jsdom document + fakes. */
export async function initPopup(doc: Document, deps: PopupDeps = defaultDeps): Promise<void> {
  const tabInfo = doc.getElementById('tab-info') as HTMLParagraphElement;
  const sendBtn = doc.getElementById('send-btn') as HTMLButtonElement;
  const status = doc.getElementById('status') as HTMLDivElement;

  const tab = await deps.getActiveTab();
  if (!tab?.url) {
    tabInfo.textContent = 'No page URL available.';
    return;
  }
  tabInfo.textContent = tab.title ? `${tab.title}\n${tab.url}` : tab.url;
  sendBtn.disabled = false;

  sendBtn.addEventListener('click', async () => {
    sendBtn.disabled = true;
    sendBtn.textContent = 'Sending…';
    status.textContent = '';
    try {
      const payload = buildIntakePayload({ url: tab.url });
      const response: IntakeResponseShape = await deps.sendToOwnix(payload);
      status.textContent = response.text;
      if (response.job_url) {
        const link = doc.createElement('a');
        link.href = '#';
        link.textContent = 'Open in dashboard';
        link.addEventListener('click', async (e) => {
          e.preventDefault();
          const host = await deps.getOwnixHost();
          deps.openTab(`${host}${response.job_url}`);
        });
        status.append(' ', link);
      }
    } catch (err) {
      status.textContent = err instanceof Error ? err.message : 'Send failed.';
    } finally {
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send to Ownix';
    }
  });
}

if (typeof document !== 'undefined' && document.getElementById('send-btn')) {
  void initPopup(document);
}
