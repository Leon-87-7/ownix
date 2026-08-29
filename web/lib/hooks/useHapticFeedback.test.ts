// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  resetAccessibilitySettingsForTests,
  useAccessibilitySettings,
} from "./useAccessibilitySettings";
import { useHapticFeedback, vibrateOutcome } from "./useHapticFeedback";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterAll(() => server.close());

afterEach(() => {
  resetAccessibilitySettingsForTests();
  Reflect.deleteProperty(navigator, "vibrate");
  vi.restoreAllMocks();
  server.resetHandlers();
});

describe("vibrateOutcome", () => {
  it("uses distinct success and error patterns", () => {
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, "vibrate", {
      configurable: true,
      value: vibrate,
    });
    expect(vibrateOutcome(true, "success")).toBe(true);
    expect(vibrateOutcome(true, "error")).toBe(true);
    expect(vibrate).toHaveBeenNthCalledWith(1, 20);
    expect(vibrate).toHaveBeenNthCalledWith(2, [40, 30, 40]);
  });

  it("does nothing when disabled or unsupported", () => {
    expect(vibrateOutcome(true, "success")).toBe(false);
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, "vibrate", {
      configurable: true,
      value: vibrate,
    });
    expect(vibrateOutcome(false, "error")).toBe(false);
    expect(vibrate).not.toHaveBeenCalled();
  });
});

describe("useHapticFeedback", () => {
  it("suppresses vibration until the stored preference loads, then respects a saved opt-out", async () => {
    let resolveSettings!: () => void;
    const settingsDeferred = new Promise<void>((resolve) => {
      resolveSettings = resolve;
    });
    server.use(
      http.get("/api/controls/accessibility-settings", async () => {
        await settingsDeferred;
        return HttpResponse.json({ visual_motion: true, haptic_motion: false });
      }),
    );
    const vibrate = vi.fn(() => true);
    Object.defineProperty(navigator, "vibrate", {
      configurable: true,
      value: vibrate,
    });

    const settings = renderHook(() => useAccessibilitySettings());
    const { result } = renderHook(() => useHapticFeedback());

    act(() => {
      result.current("success");
    });
    expect(vibrate).not.toHaveBeenCalled();

    await act(async () => {
      resolveSettings();
    });
    await waitFor(() => expect(settings.result.current.loaded).toBe(true));

    act(() => {
      result.current("success");
    });
    expect(vibrate).not.toHaveBeenCalled();
  });
});
