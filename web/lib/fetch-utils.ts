import { useEffect, useState } from 'react';

export function useFetchList<T>(url: string, errorLabel: string) {
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | undefined>();

  useEffect(() => {
    fetch(url)
      .then(async (res) => {
        if (!res.ok) throw new Error(`Failed to load ${errorLabel}`);
        return res.json() as Promise<T[]>;
      })
      .then(setData)
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setFetchError(msg);
      })
      .finally(() => setLoading(false));
  }, [url, errorLabel]);

  return { data, setData, loading, fetchError };
}

export function mapFetchState(res: Response): 'not_found' | 'forbidden' | 'error' | null {
  if (res.status === 404) return 'not_found';
  if (res.status === 403 || res.status === 401) return 'forbidden';
  if (!res.ok) return 'error';
  return null;
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
