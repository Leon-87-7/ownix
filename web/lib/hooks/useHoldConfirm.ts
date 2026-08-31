import { useEffect, useRef, useState } from 'react';

// Pointer-hold-to-confirm gesture: hold for holdMs to fire onHold; release
// early cancels. `holding` drives a CSS progress-ring class while active.
// Rely on the button's own `disabled` attribute to gate entry — browsers
// don't dispatch pointer events to a disabled control, so there's nothing
// to re-check here (mirrors how the original TelegramToggle trusted it).
//
// onTap (optional) fires on a plain short click instead of a hold — wire
// handleClick only if the caller has one; hold-only buttons can skip it.
export function useHoldConfirm(holdMs: number, onHold: () => void, onTap?: () => void) {
  const [holding, setHolding] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Hold completed → the trailing click (fires on pointerup in most browsers)
  // must be swallowed, or it would immediately also run onTap.
  const fired = useRef(false);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  function startHold() {
    setHolding(true);
    fired.current = false;
    timer.current = setTimeout(() => {
      fired.current = true;
      setHolding(false);
      onHold();
    }, holdMs);
  }

  function cancelHold() {
    setHolding(false);
    if (timer.current) clearTimeout(timer.current);
  }

  function handleClick(e: { preventDefault: () => void }) {
    e.preventDefault();
    if (fired.current) {
      fired.current = false;
      return;
    }
    onTap?.();
  }

  return { holding, startHold, cancelHold, handleClick };
}
