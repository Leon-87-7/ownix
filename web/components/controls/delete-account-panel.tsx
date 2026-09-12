'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { apiDelete, describeError } from '@/lib/fetch-utils';

const DELETE_ACCOUNT_CONSEQUENCES =
  "This deletes every job, Brain link, tag, and domain rule you own, disconnects Google, and revokes your session. This can't be undone.";

export function DeleteAccountPanel() {
  const router = useRouter();
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | undefined>();
  const [confirmText, setConfirmText] = useState('');

  const handleDelete = async () => {
    setDeleting(true);
    setError(undefined);
    try {
      await apiDelete('/api/auth/me', 'Could not delete account');
      router.replace('/login');
    } catch (err) {
      setError(describeError(err, 'Could not delete account'));
      setDeleting(false);
      throw err;
    }
  };

  return (
    <div className="flex items-stretch gap-4 max-[620px]:flex-col">
      <p className="text-sm text-body">{DELETE_ACCOUNT_CONSEQUENCES}</p>
      <div className="border-l border-line max-[620px]:hidden" />
      <div className="flex-shrink-0">
        <ConfirmDialog
          title="Permanently delete your account?"
          description={DELETE_ACCOUNT_CONSEQUENCES}
          confirmLabel="Yes, delete my account"
          pending={deleting}
          confirmDisabled={confirmText.trim().toLowerCase() !== 'delete'}
          onConfirm={handleDelete}
          trigger={
            <button
              onClick={() => {
                setConfirmText('');
                setError(undefined);
              }}
              className="h-8 rounded-md border border-line px-3 text-button font-medium text-status-error transition-ui hover:bg-raised"
            >
              Delete my account
            </button>
          }
        >
          <label className="flex flex-col gap-1 text-xs text-body">
            Type <span className="font-mono font-semibold text-ink">delete</span>{' '}
            to confirm
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
              className="w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted focus:border-signal focus:outline-none"
            />
          </label>
          {error && (
            <p className="mt-2 text-xs text-status-error" role="alert">
              {error}
            </p>
          )}
        </ConfirmDialog>
      </div>
    </div>
  );
}
