import { useEffect, useState } from 'react';

export type FetchState = "loading" | "ok" | "not_found" | "forbidden" | "error";

const FETCH_STATE_MAP: Record<number, 'not_found' | 'forbidden' | 'error'> = {
  404: 'not_found',
  403: 'forbidden',
  401: 'forbidden',
};

function mapFetchState(res: Response): 'not_found' | 'forbidden' | 'error' | null {
  return FETCH_STATE_MAP[res.status] ?? (res.ok ? null : 'error');
}

async function fetchJson<T>(
  url: string,
  options?: RequestInit,
): Promise<{ ok: true; data: T } | { ok: false; state: 'not_found' | 'forbidden' | 'error' }> {
  const res = await fetch(url, options);
  const errState = mapFetchState(res);
  if (errState) return { ok: false, state: errState };
  return { ok: true, data: (await res.json()) as T };
}

export function useFetchList<T>(url: string, errorLabel: string) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | undefined>();

  useEffect(() => {
    const controller = new AbortController();
    fetch(url, { signal: controller.signal })
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load ${errorLabel}`);
        return res.json() as Promise<T[]>;
      })
      .then(setData)
      .catch((err: unknown) => {
        if (err instanceof Error && err.name === 'AbortError') return;
        const msg = err instanceof Error ? err.message : String(err);
        setFetchError(msg);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [url, errorLabel]);

  return { data, setData, loading, fetchError };
}

export async function apiPost<T>(
  url: string,
  body: unknown,
  fallback = 'Create failed',
): Promise<{ ok: true; data: T } | { ok: false; detail: string; status: number }> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const detail = (payload as { detail?: string }).detail ?? fallback;
    return { ok: false, detail, status: res.status };
  }
  return { ok: true, data: (await res.json()) as T };
}

export async function swapSortOrder(
  urlA: string, newOrderA: number,
  urlB: string, newOrderB: number,
): Promise<void> {
  await Promise.all([
    fetch(urlA, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sort_order: newOrderA }),
    }),
    fetch(urlB, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sort_order: newOrderB }),
    }),
  ]);
}

/** Fetch a single resource, mapping HTTP status to a FetchState. */
export function useFetchDetail<T>(url: string) {
  const [data, setData] = useState<T | null>(null);
  const [fetchState, setFetchState] = useState<FetchState>('loading');

  useEffect(() => {
    const controller = new AbortController();
    fetchJson<T>(url, { signal: controller.signal })
      .then((result) => {
        if (!result.ok) { setFetchState(result.state); return; }
        setData(result.data);
        setFetchState('ok');
      })
      .catch((err) => {
        if ((err as Error).name !== 'AbortError') setFetchState('error');
      });
    return () => controller.abort();
  }, [url]);

  return { data, setData, fetchState };
}

/** PUT JSON; resolve with the parsed row or throw the server's detail message. */
export async function apiPut<T>(url: string, body: unknown, fallback = 'Save failed'): Promise<T> {
  const res = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail ?? fallback);
  }
  return (await res.json()) as T;
}

/** DELETE; throw the server's detail message unless 2xx/204. */
export async function apiDelete(url: string, fallback = 'Delete failed'): Promise<void> {
  const res = await fetch(url, { method: 'DELETE' });
  if (res.ok || res.status === 204) return;
  const data = await res.json().catch(() => ({}));
  throw new Error((data as { detail?: string }).detail ?? fallback);
}
