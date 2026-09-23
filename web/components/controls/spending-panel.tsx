'use client';

import { useSettingsResource } from '@/lib/hooks/useSettingsResource';

interface SpendingSummary {
  currency: string;
  daily_limit_micros: number | null;
  monthly_limit_micros: number | null;
  allow_paid_gemini: boolean;
  enabled: boolean;
  daily_spent_micros: number;
  monthly_spent_micros: number;
  daily_remaining_micros: number | null;
  monthly_remaining_micros: number | null;
  is_operator: boolean;
}

const DEFAULT_SUMMARY: SpendingSummary = {
  currency: 'USD',
  daily_limit_micros: null,
  monthly_limit_micros: null,
  allow_paid_gemini: false,
  enabled: true,
  daily_spent_micros: 0,
  monthly_spent_micros: 0,
  daily_remaining_micros: null,
  monthly_remaining_micros: null,
  is_operator: false,
};

function formatMicros(micros: number | undefined, currency: string | undefined): string {
  const amount = Number.isFinite(micros) ? (micros as number) / 1_000_000 : 0;
  return amount.toLocaleString(undefined, {
    style: 'currency',
    currency: currency || DEFAULT_SUMMARY.currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  });
}

function Row({ label, spent, remaining, limit, currency }: {
  label: string;
  spent: number;
  remaining: number | null;
  limit: number | null;
  currency: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 text-sm">
      <span className="text-ink">{label}</span>
      <span className="font-mono text-mono-label tabular-nums text-muted">
        {formatMicros(spent, currency)}
        {limit !== null && (
          <>
            {' / '}
            {formatMicros(limit, currency)}
            {' ('}
            {remaining !== null ? formatMicros(remaining, currency) : '—'}
            {' left)'}
          </>
        )}
        {limit === null && ' (no limit set)'}
      </span>
    </div>
  );
}

/** Dollar input for one hard cap. Commits on blur/Enter; empty = no limit. */
function LimitInput({ label, micros, disabled, onCommit }: {
  label: string;
  micros: number | null;
  disabled: boolean;
  onCommit: (micros: number | null) => void;
}) {
  const shown = micros === null ? '' : String(micros / 1_000_000);
  const commit = (raw: string) => {
    const trimmed = raw.trim();
    const next = trimmed === '' ? null : Math.round(Number(trimmed) * 1_000_000);
    if (next !== null && (!Number.isFinite(next) || next < 0)) return;
    if (next !== micros) onCommit(next);
  };
  return (
    <label className="flex items-center justify-between gap-3 text-sm">
      <span className="text-ink">{label}</span>
      <input
        // Remount when the saved value changes so defaultValue resyncs.
        key={shown}
        type="number"
        inputMode="decimal"
        min={0}
        step={0.01}
        placeholder="No limit"
        defaultValue={shown}
        disabled={disabled}
        onBlur={(e) => commit(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') e.currentTarget.blur();
        }}
        className="h-8 w-28 rounded-md border border-line bg-canvas px-2 text-right font-mono text-mono-label tabular-nums text-ink outline-none transition-ui focus:border-signal disabled:opacity-70"
      />
    </label>
  );
}

export function SpendingPanel() {
  const { settings, loaded, saving, error, update } = useSettingsResource<SpendingSummary>(
    '/api/controls/spending',
    DEFAULT_SUMMARY,
    { errorLabel: 'spending summary' },
  );

  const paidPaused = !settings.enabled || !settings.allow_paid_gemini;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-ink">Paid Gemini</span>
        <span
          role="status"
          className={`font-mono text-mono-label uppercase tracking-wider ${
            paidPaused ? 'text-status-error' : 'text-signal'
          }`}
        >
          {loaded ? (paidPaused ? 'Paused' : 'Enabled') : '—'}
        </span>
      </div>
      {loaded && settings.is_operator && (
        <div className="space-y-2 rounded-md border border-line p-3">
          <label className="flex items-center gap-3 text-sm text-ink">
            <input
              type="checkbox"
              checked={settings.enabled && settings.allow_paid_gemini}
              disabled={saving}
              onChange={(e) =>
                void update({ allow_paid_gemini: e.target.checked, enabled: true })
              }
              className="h-4 w-4 accent-signal"
            />
            <span className="font-medium">Allow paid Gemini</span>
          </label>
          <LimitInput
            label="Daily limit (USD)"
            micros={settings.daily_limit_micros}
            disabled={saving}
            onCommit={(micros) => void update({ daily_limit_micros: micros })}
          />
          <LimitInput
            label="Monthly limit (USD)"
            micros={settings.monthly_limit_micros}
            disabled={saving}
            onCommit={(micros) => void update({ monthly_limit_micros: micros })}
          />
          <p className="text-xs text-muted">
            Used when the free-tier key fails. Leave a limit empty to remove that cap.
          </p>
        </div>
      )}
      {loaded && paidPaused && !settings.is_operator && (
        <p className="text-xs text-muted">
          Paid processing is paused for your account — only free-tier Gemini
          calls run. Contact the Operator to enable it.
        </p>
      )}
      {loaded && (
        <div className="space-y-1.5">
          <Row
            label="Today"
            spent={settings.daily_spent_micros}
            remaining={settings.daily_remaining_micros}
            limit={settings.daily_limit_micros}
            currency={settings.currency}
          />
          <Row
            label="This month"
            spent={settings.monthly_spent_micros}
            remaining={settings.monthly_remaining_micros}
            limit={settings.monthly_limit_micros}
            currency={settings.currency}
          />
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
