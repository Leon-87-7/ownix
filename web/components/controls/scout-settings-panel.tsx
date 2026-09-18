'use client';

import { useSettingsResource } from '@/lib/hooks/useSettingsResource';

interface ScoutSettings {
  autonomous_enabled: boolean;
}

export function ScoutSettingsPanel() {
  const { settings, loaded, saving, error, update } =
    useSettingsResource<ScoutSettings>(
      '/api/controls/scout-settings',
      { autonomous_enabled: false },
      { errorLabel: 'scout settings' },
    );

  return (
    <>
      <label className="flex items-center gap-3 text-sm text-ink">
        <input
          type="checkbox"
          checked={settings.autonomous_enabled}
          disabled={!loaded || saving}
          onChange={(e) =>
            void update({ autonomous_enabled: e.target.checked })
          }
          className="h-4 w-4 accent-signal"
        />
        <span className="font-medium">Let the agent scout my Brain</span>
      </label>
      <p className="ml-7 mt-1.5 text-xs text-muted">
        Allow the agent to search your saved links on its own, without being
        asked, when it might help with what you're working on.
      </p>
      {error && (
        <p role="alert" className="ml-7 mt-2 text-sm text-status-error">
          {error}
        </p>
      )}
    </>
  );
}
