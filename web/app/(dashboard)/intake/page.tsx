'use client';

import { Suspense, useCallback, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { Inbox } from 'lucide-react';

import { PageHeader, PageShell } from '@/components/shell/page-shell';
import { RestrictedFacade } from '@/components/shell/restricted-facade';
import { useRestrictedMode } from '@/lib/restricted/context';
import { IntakeComposer } from '@/components/intake/intake-composer';
import { IntakeThread } from '@/components/intake/intake-thread';
import { useIntakeThread } from '@/lib/hooks/useIntakeThread';
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
  const { items, add, clear, removeAction } = useIntakeThread();
  const [error, setError] = useState<string | null>(null);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);
  const [openOfferId, setOpenOfferId] = useState<string | null>(null);

  // Declared before the submit handlers so each can hand the card a `retry`
  // that replays its own original input. Upload retries only work in the
  // session that made them — a `File` can't be persisted (issue #483).
  //
  // Each closes over its own identity (`sendText` inside `sendText`), which
  // eslint's react-hooks/immutability rule flags as "accessed before
  // declared" — a style warning, not a bug: `retry` is a lazily-invoked
  // closure, so by the time it runs the surrounding `const` is long assigned.
  // Routed through a stable ref instead of silencing the rule, so a future
  // `add` change can't leave `retry` pointing at a stale submit function.
  const sendTextRef = useRef<(value: string) => Promise<void>>(async () => {});
  const sendText = useCallback(
    async (value: string) => {
      const response = await submitIntakeText(value);
      add({ echo: value, response, retry: () => sendTextRef.current(value) });
    },
    [add],
  );
  sendTextRef.current = sendText;

  const sendUploadRef = useRef<(file: File) => Promise<void>>(async () => {});
  const sendUpload = useCallback(
    async (file: File) => {
      const response = await submitIntakeUpload(file);
      add({ echo: file.name, response, retry: () => sendUploadRef.current(file) });
    },
    [add],
  );
  sendUploadRef.current = sendUpload;

  // The newest un-answered create-tag offer, if any. `y` in the composer opens
  // it — presentation over the action envelope, never server-side pending state
  // (ADR-0047).
  const nextOffer = items
    .flatMap((i) => i.response.actions)
    .find((a) => a.kind === 'create_tag');

  const handleSaveOffer = useCallback(
    async (action: IntakeActionShape) => {
      setError(null);
      const response = await applyIntakeAction(action);
      setOpenOfferId(null);
      // Retire the offer so a later `y` can't find and resubmit it.
      removeAction(action.action_id);
      add({ response });
    },
    [add, removeAction],
  );

  const handleSubmit = useCallback(
    async (value: string): Promise<boolean> => {
      setError(null);
      if (/^y(es)?$/i.test(value.trim()) && nextOffer) {
        setOpenOfferId(nextOffer.action_id);
        return true;
      }
      try {
        await sendText(value);
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Intake submit failed.');
        return false;
      }
    },
    [sendText, nextOffer],
  );

  const handleAction = useCallback(
    async (action: IntakeActionShape) => {
      setError(null);
      setPendingActionId(action.action_id);
      try {
        const response = await applyIntakeAction(action);
        add({ response });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Action failed.');
      } finally {
        setPendingActionId(null);
      }
    },
    [add],
  );

  const handleUpload = useCallback(
    async (file: File) => {
      setError(null);
      await sendUpload(file);
    },
    [sendUpload],
  );

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
        openOfferId={openOfferId}
        onOpenOffer={setOpenOfferId}
        onSaveOffer={handleSaveOffer}
        onClear={clear}
      />
    </PageShell>
  );
}
