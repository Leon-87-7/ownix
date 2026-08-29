// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  resetAccessibilitySettingsForTests,
  useAccessibilitySettings,
} from "./useAccessibilitySettings";
import { useHapticFeedback, vibrateOutcome } from "./useHapticFeedback";

afterEach(() => {
  resetAccessibilitySettingsForTests();
  Reflect.deleteProperty(navigator, "vibrate");
  vi.restoreAllMocks();
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
    let resolveLoad!: (response: Response) => void;
    const deferred = new Promise<Response>((resolve) => {
      resolveLoad = resolve;
    });
    vi.stubGlobal("fetch", vi.fn(() => deferred));
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
      resolveLoad(
        new Response(
          JSON.stringify({ visual_motion: true, haptic_motion: false }),
        ),
      );
    });
    await waitFor(() => expect(settings.result.current.loaded).toBe(true));

    act(() => {
      result.current("success");
    });
    expect(vibrate).not.toHaveBeenCalled();
  });
});
