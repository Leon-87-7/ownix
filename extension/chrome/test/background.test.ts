import { beforeAll, describe, expect, it, vi } from 'vitest';
import manifest from '../manifest.json';
import type { CaptureDeps } from '../src/background.ts';
import type { IntakeResponseShape } from '../src/api.ts';

// background.ts registers listeners at module load — stub chrome before import.
const onInstalledListeners: Array<() => void> = [];
const onClickedListeners: Array<(info: unknown, tab: unknown) => void> = [];
const onCommandListeners: Array<(command: string) => void> = [];

vi.stubGlobal('chrome', {
  runtime: {
    onInstalled: { addListener: (fn: () => void) => onInstalledListeners.push(fn) },
    openOptionsPage: vi.fn(),
  },
  commands: { onCommand: { addListener: (fn: (command: string) => void) => onCommandListeners.push(fn) } },
  tabs: { query: vi.fn(async () => []), create: vi.fn() },
  action: { setBadgeText: vi.fn(), setBadgeBackgroundColor: vi.fn() },
  contextMenus: {
    create: vi.fn(),
    onClicked: { addListener: (fn: (info: unknown, tab: unknown) => void) => onClickedListeners.push(fn) },
  },
  notifications: {
    create: vi.fn(async () => 'notification-id'),
    clear: vi.fn(),
    onClicked: { addListener: vi.fn() },
    onClosed: { addListener: vi.fn() },
  },
  storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
});

let payloadForContextMenuClick: typeof import('../src/background.ts').payloadForContextMenuClick;
let MENU_LINK: string;
let MENU_SELECTION: string;
let MENU_PAGE: string;
let captureCommand: typeof import('../src/background.ts').captureCommand;
let handleNotificationClick: typeof import('../src/background.ts').handleNotificationClick;

beforeAll(async () => {
  const mod = await import('../src/background.ts');
  payloadForContextMenuClick = mod.payloadForContextMenuClick;
  MENU_LINK = mod.MENU_LINK;
  MENU_SELECTION = mod.MENU_SELECTION;
  MENU_PAGE = mod.MENU_PAGE;
  captureCommand = mod.captureCommand;
  handleNotificationClick = mod.handleNotificationClick;
});

const savedResponse: IntakeResponseShape = {
  schema_version: 1,
  kind: 'job_created',
  text: 'Received.',
  job_id: 'job-1',
  job_url: '/jobs/job-1',
  actions: [],
  artifacts: [],
  retryable: false,
};

function captureDeps(overrides: Partial<CaptureDeps> = {}) {
  const notifications: Array<{ id: string; title: string; message: string }> = [];
  const scheduled: Array<() => void> = [];
  const openedTabs: string[] = [];
  const deps: CaptureDeps = {
    getActiveTab: async () => ({ url: 'https://News.Example.com/story?private=1' }),
    sendToOwnix: vi.fn(async () => savedResponse),
    getOwnixHost: async () => 'https://app.leondev.xyz',
    createNotification: vi.fn(async (id, options) => {
      notifications.push({ id, title: options.title, message: options.message });
    }),
    setBadgeText: vi.fn(async () => undefined),
    setBadgeColor: vi.fn(async () => undefined),
    openOptionsPage: vi.fn(async () => undefined),
    openTab: vi.fn((url) => { openedTabs.push(url); }),
    clearNotification: vi.fn(async () => undefined),
    schedule: vi.fn((callback) => { scheduled.push(callback); }),
    notificationId: () => `notification-${notifications.length + 1}`,
    ...overrides,
  };
  return { deps, notifications, scheduled, openedTabs };
}

describe('payloadForContextMenuClick', () => {
  it('normalizes a right-clicked link', () => {
    const result = payloadForContextMenuClick(
      { menuItemId: MENU_LINK, linkUrl: 'https://example.com/link', selectionText: undefined },
      { url: 'https://example.com/page' },
    );
    expect(result).toEqual({ url: 'https://example.com/link' });
  });

  it('normalizes a selection', () => {
    const result = payloadForContextMenuClick(
      { menuItemId: MENU_SELECTION, linkUrl: undefined, selectionText: 'some selected text' },
      { url: 'https://example.com/page' },
    );
    expect(result).toEqual({ text: 'some selected text' });
  });

  it('normalizes a whole-page capture', () => {
    const result = payloadForContextMenuClick(
      { menuItemId: MENU_PAGE, linkUrl: undefined, selectionText: undefined },
      { url: 'https://example.com/page' },
    );
    expect(result).toEqual({ url: 'https://example.com/page' });
  });

  it('returns an empty payload when nothing usable is present', () => {
    const result = payloadForContextMenuClick(
      { menuItemId: MENU_PAGE, linkUrl: undefined, selectionText: undefined },
      undefined,
    );
    expect(result).toEqual({});
  });
});

describe('capture commands', () => {
  it('declares Windows-only suggestions for all four commands', () => {
    expect(manifest.commands).toEqual({
      'capture-automatic': {
        suggested_key: { windows: 'Ctrl+Shift+1' },
        description: 'Capture automatically',
      },
      'capture-article': {
        suggested_key: { windows: 'Ctrl+Shift+2' },
        description: 'Capture as article',
      },
      'capture-link': {
        suggested_key: { windows: 'Ctrl+Shift+3' },
        description: 'Capture as link',
      },
      'capture-document': {
        suggested_key: { windows: 'Ctrl+Shift+4' },
        description: 'Capture as document',
      },
    });
  });

  it.each([
    ['capture-automatic', 'automatic'],
    ['capture-article', 'article'],
    ['capture-link', 'link'],
    ['capture-document', 'document'],
  ])('maps %s to the %s shared-intake intent', async (command, intent) => {
    const { deps } = captureDeps();
    await captureCommand(command, deps);
    expect(deps.sendToOwnix).toHaveBeenCalledWith({
      url: 'https://news.example.com/story?private=1',
      intent,
    });
  });

  it('shows safe failure feedback for a protected tab without submitting', async () => {
    const { deps, notifications } = captureDeps({
      getActiveTab: async () => ({ url: 'chrome://extensions/' }),
    });

    await captureCommand('capture-automatic', deps);

    expect(deps.sendToOwnix).not.toHaveBeenCalled();
    expect(notifications).toHaveLength(1);
    expect(notifications[0].message).toBe('automatic: protected tab — failed');
    expect(deps.setBadgeText).toHaveBeenCalledWith('!');
  });

  it('opens setup and reports pairing without exposing the backend error', async () => {
    const rawError = 'Not paired — secret token abc123';
    const { deps, notifications } = captureDeps({
      sendToOwnix: vi.fn(async () => { throw new Error(rawError); }),
    });

    await captureCommand('capture-article', deps);

    expect(deps.openOptionsPage).toHaveBeenCalledOnce();
    expect(notifications[0].title).toBe('Ownix pairing required');
    expect(notifications[0].message).toBe('article: news.example.com — pairing required');
    expect(JSON.stringify(notifications)).not.toContain('abc123');
    expect(JSON.stringify(notifications)).not.toContain('/story');
  });

  it('opens the resulting Ownix job and clears its notification mapping', async () => {
    const { deps, notifications, openedTabs } = captureDeps();
    await captureCommand('capture-link', deps);

    await handleNotificationClick(notifications[0].id, deps);
    await handleNotificationClick(notifications[0].id, deps);

    expect(openedTabs).toEqual(['https://app.leondev.xyz/jobs/job-1']);
    expect(deps.clearNotification).toHaveBeenCalledOnce();
  });

  it('suppresses an identical in-flight command without a second toast', async () => {
    let resolveRequest!: (response: IntakeResponseShape) => void;
    let markStarted!: () => void;
    const started = new Promise<void>((resolve) => { markStarted = resolve; });
    const request = new Promise<IntakeResponseShape>((resolve) => { resolveRequest = resolve; });
    const send = vi.fn(() => {
      markStarted();
      return request;
    });
    const { deps, notifications } = captureDeps({ sendToOwnix: send });

    const first = captureCommand('capture-document', deps);
    await started;
    await captureCommand('capture-document', deps);

    expect(send).toHaveBeenCalledOnce();
    expect(notifications).toHaveLength(0);

    resolveRequest(savedResponse);
    await first;
    expect(notifications).toHaveLength(1);
  });

  it('does not let an older cleanup timer erase a newer badge', async () => {
    const { deps, scheduled } = captureDeps();
    await captureCommand('capture-automatic', deps);
    await captureCommand('capture-article', deps);

    vi.mocked(deps.setBadgeText).mockClear();
    scheduled[0]();
    expect(deps.setBadgeText).not.toHaveBeenCalledWith('');

    scheduled[1]();
    expect(deps.setBadgeText).toHaveBeenCalledWith('');
  });
});
