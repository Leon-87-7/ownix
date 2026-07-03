'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';

// Google connection (CONTEXT.md): one provider owns the status so every
// consumer (sidebar affordance, Feed nudge) updates instantly on
// connect/disconnect — no desync between surfaces.
interface GoogleStatus {
  /** null = not yet known (initial fetch in flight or failed). */
  connected: boolean | null;
  refresh: () => Promise<void>;
  /** POSTs /api/google/disconnect; returns false on failure. */
  disconnect: () => Promise<boolean>;
}

const GoogleStatusContext = createContext<GoogleStatus>({
  connected: null,
  refresh: async () => {},
  disconnect: async () => false,
});

export function useGoogleStatus(): GoogleStatus {
  return useContext(GoogleStatusContext);
}

export function GoogleStatusProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch('/api/google/status');
      if (!res.ok) return;
      const data = (await res.json()) as { connected: boolean };
      setConnected(data.connected);
    } catch {
      // Leave connected as-is; consumers treat null as "unknown".
    }
  }, []);

  const disconnect = useCallback(async () => {
    try {
      const res = await fetch('/api/google/disconnect', { method: 'POST' });
      if (!res.ok) return false;
      setConnected(false);
      return true;
    } catch {
      return false;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <GoogleStatusContext.Provider value={{ connected, refresh, disconnect }}>
      {children}
    </GoogleStatusContext.Provider>
  );
}
