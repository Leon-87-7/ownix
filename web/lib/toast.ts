'use client';

import { useEffect, useState } from 'react';

export interface ToastMessage {
  id: number;
  text: string;
  variant: 'success' | 'error';
}

const TOAST_DURATION_MS = 3000;

let nextId = 0;
let toasts: ToastMessage[] = [];
const listeners = new Set<(toasts: ToastMessage[]) => void>();

function emit() {
  for (const listener of listeners) listener(toasts);
}

/** Fires a brief, dismissing-itself confirmation. Call it after an action
 * whose success wouldn't otherwise be visible (e.g. a delete that navigates
 * away before a user can register the item is gone). */
export function toast(text: string, variant: ToastMessage['variant'] = 'success') {
  const id = ++nextId;
  toasts = [...toasts, { id, text, variant }];
  emit();
  window.setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id);
    emit();
  }, TOAST_DURATION_MS);
}

/** Test-only: clears module-level toast state between tests. */
export function resetToastsForTests() {
  toasts = [];
}

export function useToasts(): ToastMessage[] {
  const [state, setState] = useState(toasts);
  useEffect(() => {
    // A toast() call between this component's render and this effect
    // committing (e.g. from another effect earlier in the same commit)
    // would emit() to a listener set that doesn't include setState yet,
    // leaving `state` stuck on the stale snapshot captured by useState
    // above. Catch up to the current module state right after subscribing.
    setState(toasts);
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
  }, []);
  return state;
}
