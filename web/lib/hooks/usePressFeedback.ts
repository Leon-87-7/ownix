"use client";

import type { PointerEventHandler, TouchEventHandler } from "react";
import { useCallback, useRef } from "react";
import { useAccessibilitySettings } from "./useAccessibilitySettings";
import { useReducedMotion } from "./useReducedMotion";

const PRESS_KEYFRAMES = [
  { transform: "scale(0.96)" },
  { transform: "scale(1)" },
];

export function usePressFeedback(): {
  onPointerDown: PointerEventHandler<HTMLElement>;
  onTouchStart: TouchEventHandler<HTMLElement>;
} {
  const { visual_motion: visualMotion } = useAccessibilitySettings();
  // Layered with the live OS preference so a stale "on" default (the backend
  // can't know prefers-reduced-motion) never survives past the first paint —
  // see ADR-0053's "Stored preference vs. live OS query: layered" decision.
  const reducedMotion = useReducedMotion();
  const pointerTouchAt = useRef(0);
  const press = useCallback(
    (element: HTMLElement) => {
      if (!visualMotion || reducedMotion) return;
      element.animate?.(PRESS_KEYFRAMES, {
        duration: 140,
        easing: "cubic-bezier(0.25, 1, 0.5, 1)",
      });
    },
    [visualMotion, reducedMotion],
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
