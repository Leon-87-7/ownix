'use client';

import { Suspense, useCallback, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Inbox } from 'lucide-react';

import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRestrictedMode } from '@/lib/restricted/context';
import { IntakeComposer } from '@/components/intake/intake-composer';
import { IntakeThread, type IntakeThreadItem } from '@/components/intake/intake-thread';
import { IntakeStateBanner } from '@/components/intake/intake-state-banner';
import { IntakeUploadDropzone } from '@/components/intake/intake-upload-dropzone';
import { submitIntakeText } from '@/lib/hooks/useIntake';
import type { IntakeActionShape } from '@/lib/hooks/useIntake';
import { applyIntakeAction, submitIntakeUpload } from '@/lib/hooks/useIntakeActions';

export default function IntakePage() {
  const { restricted } = useRestrictedMode();
  if (restricted) {
    return (
      <RestrictedFacade
        icon={Inbox}
        title="Intake"
      >
        Intake is Ownix&apos;s native submit surface — paste a URL, run a
        command, or upload a file. Submitting is locked in this read-only
        preview.
      </RestrictedFacade>
    );
  }
  return (
    <Suspense fallback={null}>
      <IntakeWorkspace />
    </Suspense>
  );
}

function IntakeWorkspace() {
  const searchParams = useSearchParams();
  const prefillUrl = searchParams.get('url') ?? '';
  const [items, setItems] = useState<IntakeThreadItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);

  const handleSubmit = useCallback(async (value: string): Promise<boolean> => {
    setError(null);
    try {
      const response = await submitIntakeText(value);
      setItems((prev) => [{ id: crypto.randomUUID(), response }, ...prev]);
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Intake submit failed.');
      return false;
    }
  }, []);

  const handleAction = useCallback(async (action: IntakeActionShape) => {
    setPendingActionId(action.action_id);
    try {
      const response = await applyIntakeAction(action);
      setItems((prev) => [{ id: crypto.randomUUID(), response }, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setPendingActionId(null);
    }
  }, []);

  const handleUpload = useCallback(async (file: File) => {
    setError(null);
    const response = await submitIntakeUpload(file);
    setItems((prev) => [{ id: crypto.randomUUID(), response }, ...prev]);
  }, []);

  return (
    <PageShell width="narrow">
      <PageHeader
        icon={Inbox}
        title="Intake"
        description="Paste a URL, run a command, or write a note — one surface for everything you send Ownix."
      />

      <IntakeStateBanner />

      <section className="rounded-lg border border-line bg-surface p-4">
        <IntakeComposer
          onSubmit={handleSubmit}
          initialValue={prefillUrl}
        />
        <div className="mt-3">
          <IntakeUploadDropzone
            onUploaded={handleUpload}
            onError={setError}
          />
        </div>
        {error && (
          <p
            role="alert"
            className="mt-3 rounded-md border border-status-error/40 bg-status-error-tint px-3 py-2 text-sm text-status-error"
          >
            {error}
          </p>
        )}
      </section>

      <IntakeThread
        items={items}
        onAction={handleAction}
        pendingActionId={pendingActionId}
      />
    </PageShell>
  );
}
