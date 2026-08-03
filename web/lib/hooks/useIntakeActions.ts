import type { IntakeActionShape, IntakeResponseShape } from '@/lib/hooks/useIntake';
import { apiPostJsonOrThrow, parseApiJsonOrThrow } from '@/lib/fetch-utils';

/** Client for `POST /api/intake/action` (issue #475). */
export async function applyIntakeAction(action: IntakeActionShape): Promise<IntakeResponseShape> {
  return apiPostJsonOrThrow<IntakeResponseShape>(
    '/api/intake/action',
    {
      action_id: action.action_id,
      kind: action.kind,
      job_id: action.job_id ?? null,
      payload: action.payload ?? {},
    },
    { fallback: (status) => `Action failed (${status})` },
  );
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
  return parseApiJsonOrThrow<IntakeResponseShape>(res, (status) => `Upload failed (${status})`);
}
