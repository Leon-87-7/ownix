// @vitest-environment jsdom
import { readFileSync, readdirSync } from "node:fs";
import { resolve } from "node:path";
import { act, fireEvent, render, screen } from "@/test/render";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import InstallPrompt, { SHOW_DELAY_MS } from "./install-prompt";
import {
  DISMISS_COOLDOWN_MS,
  DISMISS_KEY,
  INSTALLED_KEY,
  detectInstallPlatform,
} from "@/lib/install-prompt";

const IPHONE_UA =
  "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1";
const ANDROID_UA =
  "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Mobile Safari/537.36";
const DESKTOP_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36";

const IPAD_DESKTOP_SAFARI_UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15";

function setUserAgent(ua: string) {
  vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ua);
}

function setStandalone(matches: boolean) {
  window.matchMedia = vi
    .fn()
    .mockReturnValue({ matches }) as unknown as typeof window.matchMedia;
}

function renderAndWait() {
  render(<InstallPrompt />);
  act(() => {
    vi.advanceTimersByTime(SHOW_DELAY_MS);
  });
}

function fakeInstallEvent(outcome: "accepted" | "dismissed") {
  const event = new Event("beforeinstallprompt") as Event & {
    prompt: ReturnType<typeof vi.fn>;
    userChoice: Promise<{ outcome: string }>;
  };
  event.prompt = vi.fn().mockResolvedValue(undefined);
  event.userChoice = Promise.resolve({ outcome });
  return event;
}

describe("detectInstallPlatform", () => {
  it.each([
    [{ userAgent: IPHONE_UA }, "ios"],
    [{ userAgent: ANDROID_UA }, "android"],
    [{ userAgent: DESKTOP_UA }, null],
    // iPadOS Safari masquerades as desktop Safari
    [
      {
        userAgent: IPAD_DESKTOP_SAFARI_UA,
        platform: "MacIntel",
        maxTouchPoints: 5,
      },
      "ios",
    ],
    // real Mac: no touch points
    [
      {
        userAgent: IPAD_DESKTOP_SAFARI_UA,
        platform: "MacIntel",
        maxTouchPoints: 0,
      },
      null,
    ],
    // desktop-mode iPad WKWebView: Mac UA without the Safari/ token
    [
      {
        userAgent:
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko)",
        platform: "MacIntel",
        maxTouchPoints: 5,
      },
      null,
    ],
  ])("%o -> %s", (nav, expected) => {
    expect(detectInstallPlatform(nav)).toBe(expected);
  });
});

describe("public/install-capture.js", () => {
  const source = readFileSync(
    resolve(__dirname, "../../public/install-capture.js"),
    "utf8",
  );
  const holder = window as { __ownixInstallPrompt?: unknown };
  // Registers one listener for the whole describe; each test just moves the path.
  new Function(source)();

  function fireAt(path: string, ua = ANDROID_UA) {
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue(ua);
    window.history.replaceState(null, "", path);
    const event = new Event("beforeinstallprompt", { cancelable: true });
    window.dispatchEvent(event);
    const stashed = holder.__ownixInstallPrompt === event;
    delete holder.__ownixInstallPrompt;
    vi.restoreAllMocks();
    return { prevented: event.defaultPrevented, stashed };
  }

  afterEach(() => window.history.replaceState(null, "", "/"));

  it("stashes the event and suppresses the native offer on dashboard routes", () => {
    expect(fireAt("/feed")).toEqual({ prevented: true, stashed: true });
  });

  // Desktop Chromium fires the event too, but the card never renders there.
  it("leaves Chrome's native offer alone on desktop, even on dashboard routes", () => {
    expect(fireAt("/feed", DESKTOP_UA)).toEqual({
      prevented: false,
      stashed: false,
    });
  });

  it.each([
    "/",
    "/login",
    "/privacy",
    "/terms",
    "/restricted",
    "/mini",
    "/intake/share",
    "/feedback",
  ])("leaves Chrome's native offer alone on public route %s", (path) => {
    expect(fireAt(path)).toEqual({ prevented: false, stashed: false });
  });

  // Guards the hand-written route list against drift: every page under
  // app/(dashboard) must be intercepted.
  it("covers every dashboard page", () => {
    const root = resolve(__dirname, "../../app/(dashboard)");
    const routes = (readdirSync(root, { recursive: true }) as string[])
      .filter((f) => f.endsWith("page.tsx"))
      .map(
        (f) =>
          "/" +
          f
            .replace(/\\/g, "/")
            .replace(/\/?page\.tsx$/, "")
            .replace(/\[[^\]]+\]/g, "x"),
      );
    expect(routes.length).toBeGreaterThan(5);
    for (const route of routes) {
      expect({ route, ...fireAt(route) }).toEqual({
        route,
        prevented: true,
        stashed: true,
      });
    }
  });
});

describe("in-app browsers get no prompt", () => {
  it.each([
    [
      "Android WebView (Telegram)",
      "Mozilla/5.0 (Linux; Android 14; Pixel 8 Build/UQ1A; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0 Mobile Safari/537.36 Telegram-Android/11.2.3",
    ],
    [
      "bare Android WebView",
      "Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/128.0 Mobile Safari/537.36",
    ],
    [
      "iOS WKWebView",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    ],
    [
      "iOS Instagram",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 350.0",
    ],
    [
      "iOS Google app",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) GSA/350.0 Mobile/15E148 Safari/604.1",
    ],
  ])("%s", (_label, userAgent) => {
    expect(detectInstallPlatform({ userAgent })).toBeNull();
  });

  it.each([
    [
      "iOS Chrome",
      "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/128.0 Mobile/15E148 Safari/604.1",
      "ios",
    ],
    [
      "Samsung Internet",
      "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0 Mobile Safari/537.36",
      "android",
    ],
  ])("still prompts in %s", (_label, userAgent, expected) => {
    expect(detectInstallPlatform({ userAgent })).toBe(expected);
  });
});

describe("InstallPrompt", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.localStorage.clear();
    setStandalone(false);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    delete (window as { __ownixInstallPrompt?: unknown }).__ownixInstallPrompt;
  });

  it("stays hidden until the page has settled", () => {
    setUserAgent(IPHONE_UA);
    render(<InstallPrompt />);
    expect(screen.queryByRole("region")).toBeNull();
    act(() => {
      vi.advanceTimersByTime(SHOW_DELAY_MS);
    });
    expect(
      screen.getByRole("region", { name: /add ownix to your home screen/i }),
    ).toBeInTheDocument();
  });

  it("shows Share-sheet steps on iPhone (no install API exists there)", () => {
    setUserAgent(IPHONE_UA);
    renderAndWait();
    expect(screen.getByLabelText("Share")).toBeInTheDocument();
    expect(screen.getByText("Add to Home Screen")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add to home screen/i }),
    ).toBeNull();
  });

  it("never shows on desktop", () => {
    setUserAgent(DESKTOP_UA);
    renderAndWait();
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("never shows when already launched from the Home Screen", () => {
    setUserAgent(ANDROID_UA);
    setStandalone(true);
    renderAndWait();
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("shows browser-menu steps on Android before the install event arrives", () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    expect(screen.getByText("Install app")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /add to home screen/i }),
    ).toBeNull();
  });

  it("opens the native install dialog on Android and remembers an accepted install", async () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    const event = fakeInstallEvent("accepted");
    act(() => {
      window.dispatchEvent(event);
    });

    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /add to home screen/i }),
      );
    });

    expect(event.prompt).toHaveBeenCalledOnce();
    expect(screen.queryByRole("region")).toBeNull();
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });

  it("picks up an install event captured before hydration", () => {
    setUserAgent(ANDROID_UA);
    (window as { __ownixInstallPrompt?: unknown }).__ownixInstallPrompt =
      fakeInstallEvent("accepted");
    renderAndWait();
    expect(
      screen.getByRole("button", { name: /add to home screen/i }),
    ).toBeInTheDocument();
  });

  it("clears the capture script's copy when it receives the event live", () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    const event = fakeInstallEvent("dismissed");
    // What public/install-capture.js does with the same dispatch.
    (window as { __ownixInstallPrompt?: unknown }).__ownixInstallPrompt = event;
    act(() => {
      window.dispatchEvent(event);
    });
    expect(
      (window as { __ownixInstallPrompt?: unknown }).__ownixInstallPrompt,
    ).toBeUndefined();
  });

  it("treats a declined native dialog as a dismissal", async () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    act(() => {
      window.dispatchEvent(fakeInstallEvent("dismissed"));
    });
    await act(async () => {
      fireEvent.click(
        screen.getByRole("button", { name: /add to home screen/i }),
      );
    });
    expect(screen.queryByRole("region")).toBeNull();
    expect(window.localStorage.getItem(DISMISS_KEY)).not.toBeNull();
  });

  it("closing it hides it and snoozes it for the cooldown window", () => {
    setUserAgent(IPHONE_UA);
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
    renderAndWait();
    fireEvent.click(screen.getByRole("button", { name: /not now/i }));
    expect(screen.queryByRole("region")).toBeNull();
    expect(window.localStorage.getItem(DISMISS_KEY)).toBe(String(Date.now()));
  });

  it("stays snoozed inside the cooldown and returns after it", () => {
    setUserAgent(IPHONE_UA);
    const now = new Date("2026-02-01T00:00:00Z").getTime();
    vi.setSystemTime(now);

    window.localStorage.setItem(
      DISMISS_KEY,
      String(now - DISMISS_COOLDOWN_MS + 1000),
    );
    const first = render(<InstallPrompt />);
    act(() => {
      vi.advanceTimersByTime(SHOW_DELAY_MS);
    });
    expect(screen.queryByRole("region")).toBeNull();
    first.unmount();

    window.localStorage.setItem(
      DISMISS_KEY,
      String(now - DISMISS_COOLDOWN_MS - 1000),
    );
    renderAndWait();
    expect(screen.getByRole("region")).toBeInTheDocument();
  });

  it("lets iPhone users confirm a manual Share-sheet install", () => {
    setUserAgent(IPHONE_UA);
    renderAndWait();
    fireEvent.click(screen.getByRole("button", { name: /i.ve added it/i }));
    expect(screen.queryByRole("region")).toBeNull();
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });

  it("offers the manual confirmation on Android's menu-steps fallback too", () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    expect(
      screen.getByRole("button", { name: /i.ve added it/i }),
    ).toBeInTheDocument();
  });

  it("omits the manual confirmation when the native install button is available", () => {
    setUserAgent(ANDROID_UA);
    renderAndWait();
    act(() => {
      window.dispatchEvent(fakeInstallEvent("accepted"));
    });
    expect(screen.queryByRole("button", { name: /i.ve added it/i })).toBeNull();
  });

  it("never returns after an install", () => {
    setUserAgent(ANDROID_UA);
    window.localStorage.setItem(INSTALLED_KEY, "1");
    renderAndWait();
    expect(screen.queryByRole("region")).toBeNull();
  });

  it("records an install made while the card is snoozed", () => {
    setUserAgent(ANDROID_UA);
    window.localStorage.setItem(DISMISS_KEY, String(Date.now()));
    render(<InstallPrompt />);
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });

  it("never appears when the app is installed before the delay elapses", () => {
    setUserAgent(ANDROID_UA);
    render(<InstallPrompt />);
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
      vi.advanceTimersByTime(SHOW_DELAY_MS);
    });
    expect(screen.queryByRole("region")).toBeNull();
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });
});
