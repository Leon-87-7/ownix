// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { vibrateOutcome } from "./useHapticFeedback";

afterEach(() => {
  Reflect.deleteProperty(navigator, "vibrate");
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
