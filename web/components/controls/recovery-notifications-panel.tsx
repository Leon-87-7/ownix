'use client';

import { useSettingsResource } from '@/lib/hooks/useSettingsResource';

interface RecoverySettings {
  telegram_notifications: boolean;
}

export function RecoveryNotificationsPanel() {
  const { settings, loaded, saving, error, update } =
    useSettingsResource<RecoverySettings>(
      '/api/controls/recovery-settings',
      { telegram_notifications: true },
      { errorLabel: 'recovery settings' },
    );

  return (
    <>
      <label className="flex items-center gap-3 text-sm text-ink">
        <input
          type="checkbox"
          checked={settings.telegram_notifications}
          disabled={!loaded || saving}
          onChange={(e) =>
            void update({ telegram_notifications: e.target.checked })
          }
          className="h-4 w-4 accent-signal"
        />
        <span className="font-medium">
          Feed recovery Telegram notifications
        </span>
      </label>
      <p className="ml-7 mt-1.5 text-xs text-muted">
        Send a Telegram message when a stuck job is recovered from the Feed.
      </p>
      {error && (
        <p role="alert" className="ml-7 mt-2 text-sm text-status-error">
          {error}
        </p>
      )}
    </>
  );
}
