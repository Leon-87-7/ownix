'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

interface RestrictedModeValue {
  restricted: boolean;
  showRestrictedToast: (body?: string) => void;
}

const RestrictedModeContext = createContext<RestrictedModeValue>({
  restricted: false,
  showRestrictedToast: () => {},
});

export function useRestrictedMode() {
  return useContext(RestrictedModeContext);
}

export function RestrictedModeProvider({ children, restricted }: { children: ReactNode; restricted: boolean }) {
  const [toast, setToast] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    };
  }, []);
  const showRestrictedToast = useCallback((body = 'Sign in to unlock actions in your own Index.') => {
    setToast(body);
    if (toastTimerRef.current !== null) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToast(null), 3600);
  }, []);
  const value = useMemo(() => ({ restricted, showRestrictedToast }), [restricted, showRestrictedToast]);
  return (
    <RestrictedModeContext.Provider value={value}>
      {children}
      {toast && (
        <div role="status" className="fixed bottom-4 right-4 z-[70] max-w-sm rounded-lg border border-line bg-surface p-4 text-sm shadow-overlay">
          <p className="font-semibold text-ink">Restricted mode on</p>
          <p className="mt-1 text-body">{toast}</p>
        </div>
      )}
    </RestrictedModeContext.Provider>
  );
}
