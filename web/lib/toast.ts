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

export function useToasts(): ToastMessage[] {
  const [state, setState] = useState(toasts);
  useEffect(() => {
    listeners.add(setState);
    return () => {
      listeners.delete(setState);
    };
  }, []);
  return state;
}
