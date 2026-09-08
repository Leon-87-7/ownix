'use client';

import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Search } from 'lucide-react';
import type { NewsletterArchiveResolution } from '@/lib/newsletter-digest';

const MAX_VISIBLE_ISSUES = 5;

/**
 * Subscribe form: one field → resolve → confirmation card listing recent
 * issue titles and an editable watch name → confirm (PLAN.md §8). Read-only
 * up to confirm — `onResolve` calls the resolve endpoint, which creates
 * nothing. `onConfirm` is wired to `POST /api/newsletter-digest`, which
 * re-resolves `archive_url` again server-side rather than trusting this
 * component's earlier resolution (issue #609).
 */
export function NewsletterArchiveResolver({
  onResolve,
  onConfirm,
  submitting = false,
}: {
  onResolve: (query: string) => Promise<NewsletterArchiveResolution>;
  // Async in practice — the caller POSTs a watch. Typed as returning void|Promise
  // so `submitting` is visibly the contract for "that call is still in flight".
  onConfirm?: (resolution: NewsletterArchiveResolution, name: string) => void | Promise<void>;
  submitting?: boolean;
}) {
  const [query, setQuery] = useState('');
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolution, setResolution] = useState<NewsletterArchiveResolution | null>(null);
  const [name, setName] = useState('');
  const mountedRef = useRef(true);
  const queryInputRef = useRef<HTMLInputElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Move focus across the step change: submitting unmounts the button that held
  // focus, so without this it drops to <body> and a screen reader gets no
  // signal that the panel swapped.
  useEffect(() => {
    if (resolution) nameInputRef.current?.focus();
  }, [resolution]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed || resolving) return;
    setResolving(true);
    setError(null);
    try {
      const result = await onResolve(trimmed);
      if (!mountedRef.current) return;
      setResolution(result);
      setName(result.fetched_title || result.archive_url);
    } catch (err) {
      if (!mountedRef.current) return;
      setResolution(null);
      setError(err instanceof Error ? err.message : 'Could not resolve that newsletter');
    } finally {
      if (mountedRef.current) setResolving(false);
    }
  }

  function handleTryAnother() {
    setResolution(null);
    setError(null);
    setName('');
    // `query` is deliberately kept so the user can tweak what they typed
    // rather than retyping a long URL.
    queryInputRef.current?.focus();
  }

  function handleConfirm(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    if (!resolution || submitting) return;
    const trimmedName = name.trim();
    if (!trimmedName) return;
    void onConfirm?.(resolution, trimmedName);
  }

  return (
    <div className="rounded-lg border border-line bg-surface p-4">
      <div className="flex items-center gap-2">
        <Search className="h-5 w-5 text-signal" aria-hidden="true" />
        <h2 className="text-title font-semibold text-ink">Find a newsletter</h2>
      </div>

      {!resolution ? (
        <form
          onSubmit={handleSubmit}
          className="mt-4 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end"
        >
          <div>
            <label className="mb-1 block text-label font-medium text-body" htmlFor="newsletter-query">
              Archive URL, issue link, or sender email
            </label>
            <input
              id="newsletter-query"
              ref={queryInputRef}
              required
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-copy text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
              placeholder="editor@example.com or https://example.com/p/latest-issue"
            />
          </div>
          <button
            type="submit"
            disabled={resolving}
            className="h-9 rounded-md bg-signal px-4 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] active:bg-signal-deep disabled:bg-surface disabled:text-muted"
          >
            {resolving ? <span className="ownix-shimmer">Looking...</span> : 'Find'}
          </button>
        </form>
      ) : (
        // Its own <form> so Enter confirms here too — the query field one step
        // earlier submits on Enter, and silently doing nothing on the very next
        // field is the kind of inconsistency keyboard users notice.
        <form onSubmit={handleConfirm} className="mt-4 rounded-md border border-line bg-canvas p-4">
          <p className="truncate text-copy font-medium text-ink">
            {resolution.fetched_title || resolution.archive_url}
          </p>
          <p className="mt-1 truncate font-mono text-label text-muted">{resolution.archive_url}</p>

          {resolution.recent_issues.length > 0 ? (
            <ul className="mt-3 space-y-1">
              {resolution.recent_issues.slice(0, MAX_VISIBLE_ISSUES).map((issue) => (
                <li key={issue.slug} className="truncate text-copy text-body">
                  {/* Linked so you can check this is the right newsletter
                      before committing to it. */}
                  <a
                    href={issue.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="transition-ui hover:text-ink hover:underline"
                  >
                    {issue.title || issue.slug}
                  </a>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-3 text-copy text-muted">
              No recent issues found yet — the archive resolved, but it listed nothing to show.
            </p>
          )}

          <div className="mt-4">
            <label
              className="mb-1 block text-label font-medium text-body"
              htmlFor="newsletter-watch-name"
            >
              Watch name
            </label>
            <input
              id="newsletter-watch-name"
              ref={nameInputRef}
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-copy text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
              placeholder="What you'll call this in Ownix"
            />
          </div>

          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              disabled={!onConfirm || !name.trim() || submitting}
              className="h-9 rounded-md bg-signal px-4 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:scale-[0.96] active:bg-signal-deep disabled:bg-surface disabled:text-muted"
            >
              {submitting ? <span className="ownix-shimmer">Adding...</span> : 'Confirm'}
            </button>
            <button
              type="button"
              onClick={handleTryAnother}
              disabled={submitting}
              className="h-9 rounded-md border border-line px-4 text-button font-medium text-body transition-ui hover:border-line-strong disabled:opacity-50"
            >
              Try another
            </button>
          </div>
        </form>
      )}

      {error && (
        <p role="alert" className="mt-3 text-sm text-status-error">
          {error}
        </p>
      )}
    </div>
  );
}
