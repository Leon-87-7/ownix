/**
 * Client for `POST /api/intake/message` (issue #472) — the versioned
 * `IntakeResponse` contract mirrored 1:1 from `src/intake/models.py`.
 */

import { apiPostJsonOrThrow } from '@/lib/fetch-utils';

export interface IntakeActionShape {
  action_id: string;
  kind: string;
  label?: string | null;
  job_id?: string | null;
  payload: Record<string, unknown>;
}

export interface IntakeResponseShape {
  schema_version: number;
  kind: string;
  text: string;
  job_id?: string | null;
  job_url?: string;
  actions: IntakeActionShape[];
  state?: Record<string, unknown> | null;
  artifacts: Array<Record<string, unknown>>;
  retryable: boolean;
}

/** Absolute http(s) URL only — anything else (a note, a slash command) goes as `text`. */
function looksLikeUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

async function submitIntakeMessage(
  body: { text?: string; url?: string },
  idempotencyKey: string = crypto.randomUUID(),
): Promise<IntakeResponseShape> {
  return apiPostJsonOrThrow<IntakeResponseShape>('/api/intake/message', body, {
    headers: {
      'Idempotency-Key': idempotencyKey,
    },
    fallback: (status) => `Intake request failed (${status})`,
  });
}

export function submitIntakeText(value: string): Promise<IntakeResponseShape> {
  return looksLikeUrl(value) ? submitIntakeMessage({ url: value }) : submitIntakeMessage({ text: value });
}
