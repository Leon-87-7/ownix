import { useCallback, useEffect, useRef, useState } from 'react';

/** Turns a caught error into user-facing copy. `fetch()` rejects with a bare
 * TypeError ("Failed to fetch") when the request never reaches the server —
 * offline, DNS, CORS — which reads as a cryptic browser internal rather than
 * guidance. Anything else is a real Error (usually the server's `detail`)
 * and passes through unchanged. */
export function describeError(err: unknown, fallback: string): string {
  if (err instanceof TypeError) {
    return 'Check your internet connection and try again.';
  }
  return err instanceof Error ? err.message : fallback;
}

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
  // Guards against an older in-flight request (e.g. a manual reload() fired
  // while the mount fetch is still pending) resolving last and clobbering
  // fresher state.
  const requestGeneration = useRef(0);

  const load = useCallback(async (signal?: AbortSignal) => {
    const generation = ++requestGeneration.current;
    setLoading(true);
    try {
      const res = await fetch(url, { signal });
      if (!res.ok) throw new Error(`Failed to load ${errorLabel}`);
      const json = (await res.json()) as T[];
      if (generation !== requestGeneration.current) return;
      setData(json);
      setFetchError(undefined);
    } catch (err: unknown) {
      if (generation !== requestGeneration.current) return;
      if (err instanceof Error && err.name === 'AbortError') return;
      setFetchError(err instanceof Error ? err.message : String(err));
    } finally {
      if (generation === requestGeneration.current) setLoading(false);
    }
  }, [url, errorLabel]);

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal);
    return () => {
      requestGeneration.current += 1;
      controller.abort();
    };
  }, [load]);

  return { data, setData, loading, fetchError, reload: load };
}

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; detail: string; status: number };

/** POST JSON, reporting failure as a value rather than an exception — for UI
 * flows that render the message inline.
 *
 * Total: it never throws. A request that never reaches the server used to
 * reject with a bare TypeError while HTTP errors came back as `{ ok: false }`,
 * so every caller needed a try/catch *and* an `!result.ok` branch for the same
 * one call. Network failures are now the same shape, with `status: 0` to say
 * "no response".
 *
 * The `*OrThrow` helpers below are the other, deliberate family: they raise, for
 * data-layer callers that already work in try/catch. */
export async function apiPost<T>(
  url: string,
  body: unknown,
  fallback = 'Create failed',
): Promise<ApiResult<T>> {
  let res: Response;
  try {
    // nosemgrep -- same-origin relative API path built by the caller, not user input
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (err) {
    return { ok: false, detail: describeError(err, fallback), status: 0 };
  }
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const detail = (payload as { detail?: string }).detail ?? fallback;
    return { ok: false, detail, status: res.status };
  }
  return { ok: true, data: (await res.json()) as T };
}

export async function parseApiJsonOrThrow<T>(
  res: Response,
  fallback: string | ((status: number) => string),
): Promise<T> {
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const fallbackMessage = typeof fallback === 'function' ? fallback(res.status) : fallback;
    throw new Error((payload as { detail?: string }).detail ?? fallbackMessage);
  }
  return (await res.json()) as T;
}

export async function apiPostJsonOrThrow<T>(
  url: string,
  body: unknown,
  options: { fallback: string | ((status: number) => string); headers?: HeadersInit },
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('Content-Type', 'application/json');
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return parseApiJsonOrThrow<T>(res, options.fallback);
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

  const requestGeneration = useRef(0);
  const load = useCallback(async (signal?: AbortSignal) => {
    const generation = ++requestGeneration.current;
    try {
      const result = await fetchJson<T>(url, { signal });
      if (generation !== requestGeneration.current) return;
      if (!result.ok) { setFetchState(result.state); return; }
      setData(result.data);
      setFetchState('ok');
    } catch (err) {
      if (generation === requestGeneration.current && (err as Error).name !== 'AbortError') {
        setFetchState('error');
      }
    }
  }, [url]);

  useEffect(() => {
    // Reset on url change: without this, navigating /jobs/A → /jobs/B keeps
    // rendering A's data (and state derived from it) until B's fetch resolves.
    setData(null);
    setFetchState('loading');
    const controller = new AbortController();
    void load(controller.signal);
    return () => { requestGeneration.current += 1; controller.abort(); };
  }, [load]);

  return { data, setData, fetchState, reload: load };
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

/** DELETE; throw the server's detail message unless 2xx. */
export async function apiDelete(url: string, fallback = 'Delete failed'): Promise<void> {
  const res = await fetch(url, { method: 'DELETE' });
  if (res.ok) return;
  const data = await res.json().catch(() => ({}));
  throw new Error((data as { detail?: string }).detail ?? fallback);
}
