/** Toolbar popup: read the active tab, "Send to Ownix" (issue #478). */

import { buildIntakePayload, getOwnixHost, sendToOwnix, type IntakeResponseShape } from './api.js';

export interface PopupDeps {
  getActiveTab: () => Promise<{ title?: string; url?: string } | undefined>;
  sendToOwnix: typeof sendToOwnix;
  getOwnixHost: typeof getOwnixHost;
  openTab: (url: string) => void;
  getCommands: () => Promise<Array<{ name?: string; shortcut?: string }>>;
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
  getCommands: () => chrome.commands.getAll(),
};

const COMMANDS = [
  ['capture-automatic', 'Automatic'],
  ['capture-article', 'Article'],
  ['capture-link', 'Link'],
  ['capture-document', 'Document'],
] as const;

/** Wires the popup DOM to `deps`. Exported (not auto-run) so tests can pass a jsdom document + fakes. */
export async function initPopup(doc: Document, deps: PopupDeps = defaultDeps): Promise<void> {
  const tabInfo = doc.getElementById('tab-info') as HTMLParagraphElement;
  const sendBtn = doc.getElementById('send-btn') as HTMLButtonElement;
  const status = doc.getElementById('status') as HTMLDivElement;
  const shortcuts = doc.getElementById('shortcuts');
  if (shortcuts) {
    const runtime = await deps.getCommands();
    const bindings = new Map(runtime.map((command) => [command.name, command.shortcut ?? '']));
    for (const [name, label] of COMMANDS) {
      const row = doc.createElement('li');
      const binding = bindings.get(name) || 'Unbound';
      const commandLabel = doc.createElement('span');
      commandLabel.textContent = label;
      const commandBinding = doc.createElement('kbd');
      commandBinding.textContent = binding;
      row.append(commandLabel, commandBinding);
      shortcuts.append(row);
    }
    const help = doc.getElementById('shortcut-help');
    if (help) {
      const unbound = COMMANDS.some(([name]) => !bindings.get(name));
      help.textContent = unbound
        ? 'Unbound commands are inactive. Set or change bindings at chrome://extensions/shortcuts.'
        : 'Chrome controls these bindings. Windows may suggest defaults; other platforms may show Unbound.';
    }
  }

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
