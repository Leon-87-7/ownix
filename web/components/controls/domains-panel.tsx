'use client';

import { useId, useState } from 'react';
import { GlobeOff, X } from 'lucide-react';
import { describeError } from '@/lib/fetch-utils';
import { useDomainList } from '@/lib/hooks/useDomainList';

type Kind = 'allowed' | 'ignored';

const LABEL: Record<Kind, string> = { allowed: 'Allowed', ignored: 'Ignored' };

function DomainPill({
  domain,
  kind,
  onRemove,
}: {
  domain: string;
  kind: Kind;
  onRemove: () => void;
}) {
  const ignored = kind === 'ignored';
  return (
    <li
      className={`inline-flex items-center gap-1.5 rounded-full border bg-raised py-1 pl-2.5 pr-1.5 text-label font-medium text-ink transition-ui hover:border-line-strong ${
        ignored ? 'border-status-error/40' : 'border-line'
      }`}
    >
      {ignored && (
        <GlobeOff className="h-3 w-3 text-status-error" aria-hidden="true" />
      )}
      <span className="font-mono">{domain}</span>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Remove ${domain}`}
        className="rounded-full p-0.5 text-muted transition-ui hover:bg-surface hover:text-ink"
      >
        <X className="h-3 w-3" aria-hidden="true" />
      </button>
    </li>
  );
}

/** Domains section: one add form shared by both the Allowed and Ignored
 * lists, switched via a segmented control (defaults to Allowed, and snaps
 * back to Allowed after every add so the target never sticks on Ignored). */
export function DomainsPanel() {
  const allowed = useDomainList('/api/controls/allowed-domains', 'Allowed Domains');
  const ignored = useDomainList('/api/controls/ignored-domains', 'Ignored Domains');
  const lists = { allowed, ignored };
  const inputId = useId();
  const [input, setInput] = useState('');
  const [kind, setKind] = useState<Kind>('allowed');
  const [adding, setAdding] = useState(false);
  const [addError, setAddError] = useState<string | undefined>();
  const [removeError, setRemoveError] = useState<string | undefined>();

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    setAdding(true);
    setAddError(undefined);
    try {
      await lists[kind].addDomain(trimmed);
      setInput('');
      setKind('allowed');
    } catch (err: unknown) {
      setAddError(describeError(err, 'Add failed'));
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (target: Kind, domain: string) => {
    setRemoveError(undefined);
    try {
      await lists[target].removeDomain(domain);
    } catch (err: unknown) {
      setRemoveError(describeError(err, 'Remove failed'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-line bg-surface p-4">
        <h3 className="mb-3 text-copy font-semibold text-ink">Add domain</h3>
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={inputId} className="text-label font-medium text-body">
              Domain or URL
            </label>
            <input
              id={inputId}
              type="text"
              required
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="example.com"
              className="w-full sm:w-72 rounded-md border border-line bg-canvas px-3 py-1.5 text-copy text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </div>
          <div
            role="group"
            aria-label="Add to list"
            className="inline-flex gap-1 rounded-md border border-line p-0.5"
          >
            {(['allowed', 'ignored'] as const).map((k) => (
              <button
                key={k}
                type="button"
                aria-pressed={kind === k}
                onClick={() => setKind(k)}
                className={`rounded px-3 py-1 text-label font-medium transition-ui ${
                  kind !== k
                    ? 'text-muted hover:text-ink'
                    : k === 'ignored'
                      ? 'bg-status-error-tint text-status-error'
                      : 'bg-selected text-ink'
                }`}
              >
                {LABEL[k]}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={adding}
            className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
          >
            {adding ? 'Adding…' : 'Add'}
          </button>
          {addError && (
            <p className="w-full text-label text-status-error">{addError}</p>
          )}
        </form>
      </div>

      {removeError && (
        <p className="px-4 text-copy text-status-error">{removeError}</p>
      )}

      {(['allowed', 'ignored'] as const).map((k) => {
        const { domains, loading, fetchError } = lists[k];
        return (
          <div key={k}>
            <h4 className="mb-2 text-label font-semibold text-muted">
              {LABEL[k]}
            </h4>
            {loading && (
              <p className="text-copy text-body">Loading {k} domains…</p>
            )}
            {fetchError && (
              <p className="text-copy text-status-error">{fetchError}</p>
            )}
            {!loading && !fetchError && domains.length === 0 && (
              <p className="text-copy text-muted">No {k} domains yet.</p>
            )}
            {domains.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {domains.map((domain) => (
                  <DomainPill
                    key={domain}
                    domain={domain}
                    kind={k}
                    onRemove={() => handleRemove(k, domain)}
                  />
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
