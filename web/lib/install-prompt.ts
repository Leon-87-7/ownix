// Platform + persistence helpers for the "Add to Home Screen" prompt
// (components/shell/install-prompt.tsx). Kept pure so the platform matrix is
// unit-testable without a browser.

export type InstallPlatform = "ios" | "android" | null;

/** Chromium's non-standard install event — not in lib.dom.d.ts. */
export interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

type NavigatorLike = {
  userAgent: string;
  platform?: string;
  maxTouchPoints?: number;
};

// In-app browsers (Telegram, Instagram, Facebook, the Google app, …) expose
// neither Add to Home Screen nor beforeinstallprompt, so the card's steps
// would be unfollowable there.
const IN_APP_BROWSER =
  /; wv\)|Telegram|FBAN|FBAV|Instagram|Line\/|MicroMessenger|Twitter|GSA\//i;

export function isInAppBrowser(ua: string): boolean {
  if (IN_APP_BROWSER.test(ua)) return true;
  // A bare iOS WKWebView omits the "Safari/" token every real iOS browser
  // (Safari, Chrome, Firefox, Edge) sends.
  return /iPhone|iPad|iPod/.test(ua) && !/Safari\//.test(ua);
}

/** Mobile platforms only — desktop browsers and in-app webviews get no prompt. */
export function detectInstallPlatform(nav: NavigatorLike): InstallPlatform {
  const ua = nav.userAgent;
  if (isInAppBrowser(ua)) return null;
  if (/iPhone|iPad|iPod/.test(ua)) return "ios";
  // iPadOS 13+ reports a desktop Mac UA; touch points give it away. Require
  // the "Safari/" token here too: a desktop-mode iPad WKWebView omits it.
  if (
    nav.platform === "MacIntel" &&
    (nav.maxTouchPoints ?? 0) > 1 &&
    /Safari\//.test(ua)
  )
    return "ios";
  if (/Android/i.test(ua)) return "android";
  return null;
}

/** Already launched from the Home Screen — nothing to install. */
export function isStandalone(win: Window): boolean {
  const iosStandalone = (win.navigator as Navigator & { standalone?: boolean })
    .standalone;
  return (
    iosStandalone === true ||
    win.matchMedia?.("(display-mode: standalone)").matches === true
  );
}

/**
 * Picks up a `beforeinstallprompt` stashed by public/install-capture.js, which
 * the root layout loads before hydration so the one-shot event isn't missed.
 */
export function takeEarlyInstallEvent(win: Window): BeforeInstallPromptEvent | null {
  const holder = win as Window & { __ownixInstallPrompt?: BeforeInstallPromptEvent };
  const event = holder.__ownixInstallPrompt ?? null;
  delete holder.__ownixInstallPrompt;
  return event;
}

export const DISMISS_KEY = "ownix-install-prompt-dismissed-at";
export const INSTALLED_KEY = "ownix-install-prompt-installed";
export const DISMISS_COOLDOWN_MS = 30 * 24 * 60 * 60 * 1000;

/** `window.localStorage` itself throws when site data is blocked. */
export function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function isSuppressed(storage: Storage | null, now: number): boolean {
  if (!storage) return false;
  try {
    if (storage.getItem(INSTALLED_KEY) === "1") return true;
    const dismissedAt = Number(storage.getItem(DISMISS_KEY));
    return (
      Number.isFinite(dismissedAt) &&
      dismissedAt > 0 &&
      now - dismissedAt < DISMISS_COOLDOWN_MS
    );
  } catch {
    // Storage blocked (private mode) — show it; dismissal just won't stick.
    return false;
  }
}

export function recordDismissal(storage: Storage | null, now: number): void {
  try {
    storage?.setItem(DISMISS_KEY, String(now));
  } catch {
    // non-persistent session is fine
  }
}

export function recordInstalled(storage: Storage | null): void {
  try {
    storage?.setItem(INSTALLED_KEY, "1");
  } catch {
    // non-persistent session is fine
  }
}
