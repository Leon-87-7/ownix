import type { IntakeActionShape, IntakeResponseShape } from '@/lib/hooks/useIntake';

/** Client for `POST /api/intake/action` (issue #475). */
export async function applyIntakeAction(action: IntakeActionShape): Promise<IntakeResponseShape> {
  const res = await fetch('/api/intake/action', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action_id: action.action_id,
      kind: action.kind,
      job_id: action.job_id ?? null,
      payload: action.payload ?? {},
    }),
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as { detail?: string }).detail ?? `Action failed (${res.status})`);
  }
  return (await res.json()) as IntakeResponseShape;
}

/** Client for `POST /api/intake/upload` (issue #475). */
export async function submitIntakeUpload(file: File): Promise<IntakeResponseShape> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/intake/upload', {
    method: 'POST',
    headers: { 'Idempotency-Key': crypto.randomUUID() },
    body: form,
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    throw new Error((payload as { detail?: string }).detail ?? `Upload failed (${res.status})`);
  }
  return (await res.json()) as IntakeResponseShape;
}
