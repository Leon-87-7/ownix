/** MV3 service worker: context menus and keyboard capture commands. */

import {
  buildIntakePayload,
  getOwnixHost,
  sendToOwnix,
  type ProcessingIntent,
} from './api.js';

export const MENU_PAGE = 'ownix-send-page';
export const MENU_LINK = 'ownix-send-link';
export const MENU_SELECTION = 'ownix-send-selection';

export const COMMAND_INTENTS: Readonly<Record<string, ProcessingIntent>> = {
  'capture-automatic': 'automatic',
  'capture-article': 'article',
  'capture-link': 'link',
  'capture-document': 'document',
};

const pending = new Set<string>();
const notificationJobs = new Map<string, string>();
let badgeGeneration = 0;

interface CaptureNotification {
  type: 'basic';
  iconUrl: string;
  title: string;
  message: string;
}

export interface CaptureDeps {
  getActiveTab: () => Promise<{ url?: string } | undefined>;
  sendToOwnix: typeof sendToOwnix;
  getOwnixHost: typeof getOwnixHost;
  createNotification: (id: string, options: CaptureNotification) => Promise<void>;
  setBadgeText: (text: string) => Promise<void>;
  setBadgeColor: (color: string) => Promise<void>;
  openOptionsPage: () => Promise<void>;
  openTab: (url: string) => void;
  clearNotification: (id: string) => Promise<void>;
  schedule: (callback: () => void, delayMs: number) => void;
  notificationId: () => string;
}

const defaultCaptureDeps: CaptureDeps = {
  getActiveTab: async () => {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    return tab;
  },
  sendToOwnix,
  getOwnixHost,
  createNotification: async (id, options) => {
    await chrome.notifications.create(id, options);
  },
  setBadgeText: (text) => chrome.action.setBadgeText({ text }),
  setBadgeColor: (color) => chrome.action.setBadgeBackgroundColor({ color }),
  openOptionsPage: () => chrome.runtime.openOptionsPage(),
  openTab: (url) => { void chrome.tabs.create({ url }); },
  clearNotification: async (id) => {
    await chrome.notifications.clear(id);
  },
  schedule: (callback, delayMs) => { setTimeout(callback, delayMs); },
  notificationId: () => `ownix-${crypto.randomUUID()}`,
};

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: MENU_PAGE, title: 'Send page to Ownix', contexts: ['page'] });
  chrome.contextMenus.create({ id: MENU_LINK, title: 'Send link to Ownix', contexts: ['link'] });
  chrome.contextMenus.create({
    id: MENU_SELECTION,
    title: 'Send selection to Ownix',
    contexts: ['selection'],
  });
});

export function payloadForContextMenuClick(
  info: Pick<chrome.contextMenus.OnClickData, 'menuItemId' | 'linkUrl' | 'selectionText'>,
  tab?: Pick<chrome.tabs.Tab, 'url'>,
): { url?: string; text?: string } {
  if (info.menuItemId === MENU_LINK && info.linkUrl) return { url: info.linkUrl };
  if (info.menuItemId === MENU_SELECTION && info.selectionText) return { text: info.selectionText };
  if (info.menuItemId === MENU_PAGE && tab?.url) return { url: tab.url };
  return {};
}

function safePage(url: string | undefined): URL | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed : null;
  } catch {
    return null;
  }
}

async function notify(
  deps: CaptureDeps,
  title: string,
  message: string,
  jobUrl?: string,
): Promise<void> {
  const id = deps.notificationId();
  await deps.createNotification(id, {
    type: 'basic', iconUrl: 'icons/icon48.png', title, message,
  });
  if (jobUrl) notificationJobs.set(id, jobUrl);
}

async function setBadge(deps: CaptureDeps, text: string, color = '#d99a45'): Promise<void> {
  await deps.setBadgeColor(color);
  await deps.setBadgeText(text);
}

function scheduleBadgeClear(deps: CaptureDeps, generation: number): void {
  deps.schedule(() => {
    if (badgeGeneration === generation) void deps.setBadgeText('');
  }, 1500);
}

export async function captureCommand(
  command: string,
  deps: CaptureDeps = defaultCaptureDeps,
): Promise<void> {
  const intent = COMMAND_INTENTS[command];
  if (!intent) return;
  const tab = await deps.getActiveTab();
  const page = safePage(tab?.url);
  if (!page) {
    const generation = ++badgeGeneration;
    await setBadge(deps, '!', '#f87171');
    await notify(deps, 'Ownix capture unavailable', `${intent}: protected tab — failed`);
    scheduleBadgeClear(deps, generation);
    return;
  }

  const key = `${page.href}\n${command}`;
  if (pending.has(key)) {
    await setBadge(deps, '…');
    return;
  }
  pending.add(key);
  const generation = ++badgeGeneration;
  await setBadge(deps, '…');
  try {
    const response = await deps.sendToOwnix(buildIntakePayload({ url: page.href, intent }));
    const domain = page.hostname.toLowerCase();
    if (response.job_id) {
      await setBadge(deps, '✓', '#4ade80');
      const host = await deps.getOwnixHost();
      const jobUrl = new URL(`/jobs/${encodeURIComponent(response.job_id)}`, host).toString();
      await notify(deps, 'Ownix capture complete', `${intent}: ${domain} — saved`, jobUrl);
    } else {
      await setBadge(deps, '!', '#eab308');
      const hint = intent === 'automatic' ? ' Try Article, Link, or Document.' : '';
      await notify(deps, 'Ownix capture not saved', `${intent}: ${domain} — unsupported.${hint}`);
    }
  } catch (err) {
    await setBadge(deps, '!', '#f87171');
    const message = err instanceof Error ? err.message : '';
    if (/not paired/i.test(message)) {
      await deps.openOptionsPage();
      await notify(
        deps,
        'Ownix pairing required',
        `${intent}: ${page.hostname.toLowerCase()} — pairing required`,
      );
    } else {
      await notify(deps, 'Ownix capture failed', `${intent}: ${page.hostname.toLowerCase()} — failed`);
    }
  } finally {
    pending.delete(key);
    scheduleBadgeClear(deps, generation);
  }
}

chrome.commands.onCommand.addListener((command) => void captureCommand(command));

export async function handleNotificationClick(
  notificationId: string,
  deps: CaptureDeps = defaultCaptureDeps,
): Promise<void> {
  const url = notificationJobs.get(notificationId);
  if (!url) return;
  notificationJobs.delete(notificationId);
  deps.openTab(url);
  await deps.clearNotification(notificationId);
}

chrome.notifications.onClicked.addListener((notificationId) => {
  void handleNotificationClick(notificationId);
});

chrome.notifications.onClosed?.addListener((notificationId) => {
  notificationJobs.delete(notificationId);
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    const response = await sendToOwnix(buildIntakePayload(payloadForContextMenuClick(info, tab)));
    await notify(defaultCaptureDeps, 'Sent to Ownix', response.text);
  } catch (err) {
    await notify(
      defaultCaptureDeps,
      'Ownix send failed',
      err instanceof Error ? err.message : String(err),
    );
  }
});
