'use client';

import { ListenButton } from '@/components/ui/listen-button';
import { usePressFeedback } from '@/lib/hooks/usePressFeedback';
import {
  useSpeechVoices,
  groupVoicesByLanguage,
} from '@/lib/hooks/useSpeechVoices';
import {
  publishAccessibilitySettingsFromExternalWrite,
  type AccessibilitySettings,
} from '@/lib/hooks/useAccessibilitySettings';
import { useSettingsResource } from '@/lib/hooks/useSettingsResource';

const VOICE_PREVIEW_TEXT =
  'This is how your summaries will sound when read aloud.';
const VOICE_SELECT_CLASS =
  'h-10 flex-1 rounded-md border border-line bg-canvas px-3 text-sm text-ink outline-none transition-ui focus:border-signal disabled:cursor-not-allowed disabled:text-muted disabled:opacity-70';

const TOGGLES = [
  [
    'visual_motion',
    'Press animation',
    'Show tactile press animation on touch controls.',
  ],
  [
    'haptic_motion',
    'Haptic motion',
    'Vibrate for completed or failed actions when your device supports it.',
  ],
] as const;

export function AccessibilityPanel() {
  const { settings, loaded, saving, error, update } =
    useSettingsResource<AccessibilitySettings>(
      '/api/controls/accessibility-settings',
      { visual_motion: true, haptic_motion: true, voice_uri: null },
      {
        errorLabel: 'accessibility settings',
        onApply: publishAccessibilitySettingsFromExternalWrite,
      },
    );
  const pressFeedback = usePressFeedback();
  const { supported: speechSupported, voices } = useSpeechVoices();
  const voiceGroups = groupVoicesByLanguage(voices);

  // The persisted voice_uri may not be among voices on this browser/device
  // (set on another machine, or the voice was uninstalled). Silently showing
  // "System default" while the stored value is still the missing URI is a
  // dead end: the select's value already equals "" then, so choosing
  // "System default" from the list is a no-op click (onChange only fires on
  // an actual value change) and the stale URI is never cleared. Instead,
  // render it as its own disabled option so it's visibly the current
  // selection, and picking "System default" (a real value change) fires
  // onChange and persists null like any other pick.
  const isPersistedVoiceInstalled = voiceGroups.some((group) =>
    group.voices.some((voice) => voice.voiceURI === settings.voice_uri),
  );

  return (
    <div className="space-y-4">
      {TOGGLES.map(([key, label, description]) => (
        <div key={key}>
          <label className="flex items-center gap-3 text-sm text-ink">
            <input
              {...pressFeedback}
              type="checkbox"
              checked={settings[key]}
              disabled={!loaded || saving}
              onChange={(event) =>
                void update({ [key]: event.target.checked })
              }
              className="h-4 w-4 accent-signal active:scale-[0.96] motion-reduce:active:scale-100"
            />
            <span className="font-medium">{label}</span>
          </label>
          <p className="ml-7 mt-1.5 text-xs text-muted">{description}</p>
        </div>
      ))}
      {speechSupported && (
        <div>
          <label
            htmlFor="accessibility-voice-select"
            className="text-sm font-medium text-ink"
          >
            Voice
          </label>
          <p className="mt-1.5 text-xs text-muted">
            Choose which installed voice narrates text aloud. System default
            uses your browser&apos;s normal voice.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <select
              id="accessibility-voice-select"
              value={settings.voice_uri ?? ''}
              disabled={!loaded || saving}
              onChange={(event) =>
                void update({ voice_uri: event.target.value || null })
              }
              className={VOICE_SELECT_CLASS}
            >
              <option value="">System default</option>
              {settings.voice_uri && !isPersistedVoiceInstalled && (
                <option value={settings.voice_uri} disabled>
                  Unavailable voice
                </option>
              )}
              {voiceGroups.map((group) => (
                <optgroup key={group.lang} label={group.label}>
                  {group.voices.map((voice) => (
                    <option key={voice.voiceURI} value={voice.voiceURI}>
                      {voice.name}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
            <ListenButton
              text={VOICE_PREVIEW_TEXT}
              ariaLabel="Preview voice"
              voiceURI={settings.voice_uri}
            />
          </div>
        </div>
      )}
      {error && (
        <p className="ml-7 text-sm text-status-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
