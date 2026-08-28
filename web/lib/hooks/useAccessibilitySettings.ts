"use client";

import { useEffect, useState } from "react";

export interface AccessibilitySettings {
  visual_motion: boolean;
  haptic_motion: boolean;
}

const listeners = new Set<() => void>();
let stored: AccessibilitySettings | null = null;
let loading: Promise<void> | null = null;
// Guards against an older overlapping saveAccessibilitySetting call (e.g. two
// rapid toggles) resolving last and clobbering a newer save's result.
let requestGeneration = 0;

function notify() {
  listeners.forEach((listener) => listener());
}

export function publishAccessibilitySettings(value: AccessibilitySettings) {
  stored = value;
  notify();
}

/** Optimistic PUT with rollback, guarded against out-of-order responses so an
 * older overlapping call can never publish over a newer one. Mirrors the
 * requestGeneration pattern in web/lib/fetch-utils.ts's useFetchDetail. */
export async function saveAccessibilitySetting(
  key: keyof AccessibilitySettings,
  checked: boolean,
): Promise<void> {
  const generation = ++requestGeneration;
  const previous = stored ?? { visual_motion: true, haptic_motion: true };
  const next = { ...previous, [key]: checked };
  publishAccessibilitySettings(next);
  try {
    const response = await fetch("/api/controls/accessibility-settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(next),
    });
    if (!response.ok)
      throw new Error("Failed to save accessibility settings");
    const saved = (await response.json()) as AccessibilitySettings;
    if (generation === requestGeneration) publishAccessibilitySettings(saved);
  } catch (err) {
    if (generation === requestGeneration) publishAccessibilitySettings(previous);
    throw err;
  }
}

export function resetAccessibilitySettingsForTests() {
  stored = null;
  loading = null;
  notify();
}

function load() {
  if (stored || loading || typeof window === "undefined") return;
  loading = fetch("/api/controls/accessibility-settings")
    .then((response) => {
      if (!response.ok)
        throw new Error("Failed to load accessibility settings");
      return response.json() as Promise<AccessibilitySettings>;
    })
    .then(publishAccessibilitySettings)
    .catch(() => undefined)
    .finally(() => {
      loading = null;
    });
}

export function useAccessibilitySettings(): AccessibilitySettings {
  const [reducedMotion, setReducedMotion] = useState(true);
  const [, rerender] = useState(0);

  useEffect(() => {
    const media = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    const updateMotion = () => setReducedMotion(media?.matches ?? true);
    updateMotion();
    media?.addEventListener("change", updateMotion);
    const updateStored = () => rerender((value) => value + 1);
    listeners.add(updateStored);
    load();
    return () => {
      media?.removeEventListener("change", updateMotion);
      listeners.delete(updateStored);
    };
  }, []);

  return stored ?? { visual_motion: !reducedMotion, haptic_motion: true };
}
