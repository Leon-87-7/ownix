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

export function SpendingPanel() {
  const { settings, loaded, error } = useSettingsResource<SpendingSummary>(
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
      {loaded && paidPaused && (
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
