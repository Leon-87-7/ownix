'use client';

import { useId, useState } from 'react';
import { describeError } from '@/lib/fetch-utils';
import { useDomainList } from '@/lib/hooks/useDomainList';

/** One domain allowlist/denylist. Rendered twice on Settings (Allowed and
 * Ignored), which is why the input id comes from `useId` — both instances are
 * on screen at once. */
export function DomainPanel({
  apiPath,
  label,
}: {
  apiPath: string;
  label: string;
}) {
  const { domains, loading, fetchError, addDomain, removeDomain } =
    useDomainList(apiPath, label);
  const inputId = useId();
  const [input, setInput] = useState('');
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
      await addDomain(trimmed);
      setInput('');
    } catch (err: unknown) {
      setAddError(describeError(err, 'Add failed'));
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (domain: string) => {
    setRemoveError(undefined);
    try {
      await removeDomain(domain);
    } catch (err: unknown) {
      setRemoveError(describeError(err, 'Remove failed'));
    }
  };

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-line bg-surface p-4">
        <h3 className="mb-3 text-sm font-semibold text-ink">Add domain</h3>
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-3">
          <div className="flex flex-col gap-1">
            <label htmlFor={inputId} className="text-xs font-medium text-body">
              Domain or URL
            </label>
            <input
              id={inputId}
              type="text"
              required
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="example.com"
              className="w-full sm:w-72 rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={adding}
            className="h-8 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
          >
            {adding ? 'Adding…' : 'Add'}
          </button>
          {addError && (
            <p className="w-full text-xs text-status-error">{addError}</p>
          )}
        </form>
      </div>

      {loading && (
        <p className="px-4 text-sm text-body">Loading {label.toLowerCase()}…</p>
      )}
      {fetchError && (
        <p className="px-4 text-sm text-status-error">{fetchError}</p>
      )}
      {removeError && (
        <p className="px-4 text-sm text-status-error">{removeError}</p>
      )}
      {!loading && !fetchError && domains.length === 0 && (
        <p className="px-4 text-sm text-muted">
          No {label.toLowerCase()} yet. Add one above.
        </p>
      )}
      {domains.length > 0 && (
        <ul className="space-y-2">
          {domains.map((domain) => (
            <li
              key={domain}
              className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3"
            >
              <span className="min-w-0 flex-1 font-mono text-sm text-ink">
                {domain}
              </span>
              <button
                onClick={() => handleRemove(domain)}
                className="rounded px-2 py-1 text-xs font-medium text-status-error transition-ui hover:bg-raised"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
