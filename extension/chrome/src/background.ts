/** MV3 service worker: context-menu registration + click handling (issue #478). */

import { buildIntakePayload, sendToOwnix } from './api';

export const MENU_PAGE = 'ownix-send-page';
export const MENU_LINK = 'ownix-send-link';
export const MENU_SELECTION = 'ownix-send-selection';

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: MENU_PAGE, title: 'Send page to Ownix', contexts: ['page'] });
  chrome.contextMenus.create({ id: MENU_LINK, title: 'Send link to Ownix', contexts: ['link'] });
  chrome.contextMenus.create({
    id: MENU_SELECTION,
    title: 'Send selection to Ownix',
    contexts: ['selection'],
  });
});

/** Pure normalization, unit-tested without touching chrome.* APIs. */
export function payloadForContextMenuClick(
  info: Pick<chrome.contextMenus.OnClickData, 'menuItemId' | 'linkUrl' | 'selectionText'>,
  tab?: Pick<chrome.tabs.Tab, 'url'>,
): { url?: string; text?: string } {
  if (info.menuItemId === MENU_LINK && info.linkUrl) {
    return { url: info.linkUrl };
  }
  if (info.menuItemId === MENU_SELECTION && info.selectionText) {
    return { text: info.selectionText };
  }
  if (info.menuItemId === MENU_PAGE && tab?.url) {
    return { url: tab.url };
  }
  return {};
}

async function notify(title: string, message: string): Promise<void> {
  await chrome.notifications.create({
    type: 'basic',
    iconUrl: 'icons/icon48.png',
    title,
    message,
  });
}

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  try {
    const raw = payloadForContextMenuClick(info, tab);
    const payload = buildIntakePayload(raw);
    const response = await sendToOwnix(payload);
    await notify('Sent to Ownix', response.text);
  } catch (err) {
    await notify('Ownix send failed', err instanceof Error ? err.message : String(err));
  }
});
