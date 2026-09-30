// @vitest-environment jsdom
import { act, render } from "@/test/render";
import { afterEach, describe, expect, it } from "vitest";
import InstallTracker from "./install-tracker";
import { DISMISS_KEY, INSTALLED_KEY } from "@/lib/install-prompt";

describe("InstallTracker", () => {
  afterEach(() => window.localStorage.clear());

  it("records an install made through the browser's own UI", () => {
    render(<InstallTracker />);
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });

  it("records it even while the dashboard card is snoozed or not mounted", () => {
    window.localStorage.setItem(DISMISS_KEY, String(Date.now()));
    render(<InstallTracker />);
    act(() => {
      window.dispatchEvent(new Event("appinstalled"));
    });
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBe("1");
  });

  it("stops listening once unmounted", () => {
    const { unmount } = render(<InstallTracker />);
    unmount();
    window.dispatchEvent(new Event("appinstalled"));
    expect(window.localStorage.getItem(INSTALLED_KEY)).toBeNull();
  });

  it("does not intercept the native install offer", () => {
    render(<InstallTracker />);
    const event = new Event("beforeinstallprompt", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(false);
  });
});
