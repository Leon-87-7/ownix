/**
 * Client for `POST /api/intake/message` (issue #472) — the versioned
 * `IntakeResponse` contract mirrored 1:1 from `src/intake/models.py`.
 */

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
export function looksLikeUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

export async function submitIntakeMessage(
  body: { text?: string; url?: string },
  idempotencyKey: string = crypto.randomUUID(),
): Promise<IntakeResponseShape> {
  const res = await fetch('/api/intake/message', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error(
      (payload as { detail?: string }).detail ?? `Intake request failed (${res.status})`,
    );
  }
  return (await res.json()) as IntakeResponseShape;
}

export function submitIntakeText(value: string): Promise<IntakeResponseShape> {
  return looksLikeUrl(value) ? submitIntakeMessage({ url: value }) : submitIntakeMessage({ text: value });
}
