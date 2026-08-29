// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  publishAccessibilitySettings,
  resetAccessibilitySettingsForTests,
} from "./useAccessibilitySettings";
import { usePressFeedback } from "./usePressFeedback";

afterEach(() => {
  // Unmount before resetting the shared accessibility-settings store — it
  // notifies subscribed React state setters, and afterEach hooks run in
  // reverse-registration (LIFO) order, so RTL's own auto-cleanup afterEach
  // (registered first, via the `@testing-library/react` import) would
  // otherwise run *after* this one and unmount too late.
  cleanup();
  resetAccessibilitySettingsForTests();
  vi.restoreAllMocks();
});

function installMedia(coarse: boolean, reducedMotion = false) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise(() => undefined)),
  );
  window.matchMedia = vi.fn((query: string) => ({
    matches: query.includes("pointer")
      ? coarse
      : query.includes("reduced-motion")
        ? reducedMotion
        : false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("usePressFeedback", () => {
  it("animates touch input but not a desktop mouse", async () => {
    installMedia(false);
    const animate = vi.fn();
    const target = { animate } as unknown as HTMLElement;
    const { result } = renderHook(() => usePressFeedback());
    await waitFor(() => expect(window.matchMedia).toHaveBeenCalled());
    act(() =>
      result.current.onPointerDown({
        pointerType: "mouse",
        currentTarget: target,
      } as never),
    );
    expect(animate).not.toHaveBeenCalled();
    act(() =>
      result.current.onPointerDown({
        pointerType: "touch",
        currentTarget: target,
      } as never),
    );
    expect(animate).toHaveBeenCalledOnce();
  });

  it("suppresses feedback when visual motion is disabled", () => {
    installMedia(true);
    publishAccessibilitySettings({ visual_motion: false, haptic_motion: true });
    const animate = vi.fn();
    const { result } = renderHook(() => usePressFeedback());
    act(() =>
      result.current.onTouchStart({ currentTarget: { animate } } as never),
    );
    expect(animate).not.toHaveBeenCalled();
  });

  it("lets an explicit stored preference override the live OS reduced-motion default", () => {
    installMedia(true, true);
    publishAccessibilitySettings({ visual_motion: true, haptic_motion: true });
    const animate = vi.fn();
    const { result } = renderHook(() => usePressFeedback());
    act(() =>
      result.current.onTouchStart({ currentTarget: { animate } } as never),
    );
    expect(animate).toHaveBeenCalledOnce();
  });

  it("falls back to the live OS reduced-motion default when no preference is stored yet", () => {
    installMedia(true, true);
    const animate = vi.fn();
    const { result } = renderHook(() => usePressFeedback());
    act(() =>
      result.current.onTouchStart({ currentTarget: { animate } } as never),
    );
    expect(animate).not.toHaveBeenCalled();
  });

  it("fires exactly one animation trigger path for a single touch gesture", () => {
    installMedia(true);
    publishAccessibilitySettings({ visual_motion: true, haptic_motion: true });
    const animate = vi.fn();
    const target = { animate } as unknown as HTMLElement;
    const { result } = renderHook(() => usePressFeedback());
    act(() => {
      result.current.onPointerDown({
        pointerType: "touch",
        currentTarget: target,
      } as never);
      result.current.onTouchStart({ currentTarget: target } as never);
    });
    expect(animate).toHaveBeenCalledOnce();
  });
});
