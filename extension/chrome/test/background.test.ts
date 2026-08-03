import { beforeAll, describe, expect, it, vi } from 'vitest';

// background.ts registers listeners at module load — stub chrome before import.
const onInstalledListeners: Array<() => void> = [];
const onClickedListeners: Array<(info: unknown, tab: unknown) => void> = [];

vi.stubGlobal('chrome', {
  runtime: { onInstalled: { addListener: (fn: () => void) => onInstalledListeners.push(fn) } },
  contextMenus: {
    create: vi.fn(),
    onClicked: { addListener: (fn: (info: unknown, tab: unknown) => void) => onClickedListeners.push(fn) },
  },
  notifications: { create: vi.fn() },
  storage: { local: { get: vi.fn(async () => ({})), set: vi.fn(async () => {}) } },
});

let payloadForContextMenuClick: typeof import('../src/background').payloadForContextMenuClick;
let MENU_LINK: string;
let MENU_SELECTION: string;
let MENU_PAGE: string;

beforeAll(async () => {
  const mod = await import('../src/background');
  payloadForContextMenuClick = mod.payloadForContextMenuClick;
  MENU_LINK = mod.MENU_LINK;
  MENU_SELECTION = mod.MENU_SELECTION;
  MENU_PAGE = mod.MENU_PAGE;
});

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
