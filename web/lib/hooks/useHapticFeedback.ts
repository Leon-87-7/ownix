"use client";

import { useCallback } from "react";
import { useAccessibilitySettings } from "./useAccessibilitySettings";

export type HapticOutcome = "success" | "error";
const PATTERNS: Record<HapticOutcome, number | number[]> = {
  success: 20,
  error: [40, 30, 40],
};

export function vibrateOutcome(
  enabled: boolean,
  outcome: HapticOutcome,
): boolean {
  if (!enabled || typeof navigator === "undefined" || !("vibrate" in navigator))
    return false;
  return navigator.vibrate(PATTERNS[outcome]);
}

export function useHapticFeedback() {
  const { haptic_motion: enabled, loaded } = useAccessibilitySettings();
  return useCallback(
    // haptic_motion defaults to true until the stored preference loads, so
    // an action fired in that window could vibrate past a saved opt-out.
    (outcome: HapticOutcome) => (loaded ? vibrateOutcome(enabled, outcome) : false),
    [enabled, loaded],
  );
}
