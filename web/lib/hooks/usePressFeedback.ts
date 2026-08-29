"use client";

import type { PointerEventHandler, TouchEventHandler } from "react";
import { useCallback, useRef } from "react";
import { useAccessibilitySettings } from "./useAccessibilitySettings";

const PRESS_KEYFRAMES = [
  { transform: "scale(0.96)" },
  { transform: "scale(1)" },
];

export function usePressFeedback(): {
  onPointerDown: PointerEventHandler<HTMLElement>;
  onTouchStart: TouchEventHandler<HTMLElement>;
} {
  // useAccessibilitySettings() already layers this correctly on its own: it
  // seeds visual_motion from the live prefers-reduced-motion query until a
  // stored preference exists, then the stored value is authoritative — see
  // ADR-0053's "Stored preference vs. live OS query: layered (stored wins
  // once set)" decision. Don't re-gate on the OS query here too, or an
  // explicit stored "on" can never override a reduced-motion OS default.
  const { visual_motion: visualMotion } = useAccessibilitySettings();
  const pointerTouchAt = useRef(0);
  const press = useCallback(
    (element: HTMLElement) => {
      if (!visualMotion) return;
      element.animate?.(PRESS_KEYFRAMES, {
        duration: 140,
        easing: "cubic-bezier(0.25, 1, 0.5, 1)",
      });
    },
    [visualMotion],
  );
  return {
    onPointerDown: (event) => {
      const coarse = window.matchMedia?.("(pointer: coarse)").matches;
      if (event.pointerType !== "touch" && !coarse) return;
      pointerTouchAt.current = Date.now();
      press(event.currentTarget);
    },
    onTouchStart: (event) => {
      if (Date.now() - pointerTouchAt.current < 500) return;
      press(event.currentTarget);
    },
  };
}
