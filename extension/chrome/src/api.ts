/** API client for the extension: POST /api/intake/message (issue #478). */

import { getExtensionToken } from './auth.js';
import {
  defaultOwnixHost,
  fetchIntakeMessage,
  isAllowedOwnixHost,
  normalizeAllowedOwnixHost,
  type AllowedOwnixOrigin,
} from './hosts.js';

export interface IntakeResponseShape {
  schema_version: number;
  kind: string;
  text: string;
  job_id?: string | null;
  job_url?: string;
  actions: Array<Record<string, unknown>>;
  state?: Record<string, unknown> | null;
  artifacts: Array<Record<string, unknown>>;
  retryable: boolean;
}

export interface IntakePayload {
  url?: string;
  text?: string;
}

const HOST_STORAGE_KEY = 'ownixHost';

export async function getOwnixHost(): Promise<AllowedOwnixOrigin> {
  const stored = await chrome.storage.local.get(HOST_STORAGE_KEY);
  const value = stored[HOST_STORAGE_KEY] as string | undefined;
  if (!value) return defaultOwnixHost();
  return normalizeAllowedOwnixHost(value);
}

/** Reject anything outside the fixed Ownix origin allowlist. */
export function isValidOwnixHost(host: string): boolean {
  return isAllowedOwnixHost(host);
}

export async function setOwnixHost(host: string): Promise<void> {
  const normalized = normalizeAllowedOwnixHost(host);
  await chrome.storage.local.set({ [HOST_STORAGE_KEY]: normalized });
}

/** URL wins over text — a URL capture (page/link) is always what the user meant to send. */
export function buildIntakePayload(input: { url?: string; text?: string }): IntakePayload {
  const url = input.url?.trim();
  const text = input.text?.trim();
  if (url) return { url };
  if (text) return { text };
  throw new Error('Nothing to send — no URL or text.');
}

/**
 * Auth: a paired bearer token (issue #479) — never a raw session cookie.
 *
 * An earlier revision of this MVP fell back to `credentials: 'include'`,
 * hoping to piggyback the dashboard's `vig_session` cookie. That never
 * actually worked: the cookie is set `SameSite=Lax` (`src/api/auth.py`), and
 * Lax cookies aren't attached to a cross-origin `fetch()`/XHR from an
 * extension-origin (`chrome-extension://…`) context — only to top-level
 * navigations. Rather than keep a fallback that silently does nothing,
 * pairing is required.
 */
export async function sendToOwnix(payload: IntakePayload, host?: string): Promise<IntakeResponseShape> {
  const base = host ? normalizeAllowedOwnixHost(host) : await getOwnixHost();
  const token = await getExtensionToken();
  if (!token) {
    throw new Error('Not paired — open the extension Options page and connect to Ownix.');
  }

  const res = await fetchIntakeMessage(base, {
    method: 'POST',
    credentials: 'omit',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': crypto.randomUUID(),
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `Ownix request failed (${res.status})`);
  }
  return (await res.json()) as IntakeResponseShape;
}
