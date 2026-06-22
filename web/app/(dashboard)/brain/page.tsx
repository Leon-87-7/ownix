'use client';

import { useRef, useState } from 'react';
import { BrainGraph } from '@/components/brain-graph';
import { useSemanticSearch } from '@/lib/hooks/useSemanticSearch';
import type { BrainResult } from '@/lib/hooks/useSemanticSearch';

function IdleBanner() {
  return (
    <div className="rounded-lg border border-line bg-surface px-6 py-12 text-center">
      <p className="text-lg font-medium text-ink">Search your Second Brain</p>
      <p className="mt-1 text-sm text-body">Type a query above to find semantically similar videos and articles you have saved.</p>
    </div>
  );
}

function EmptyBanner() {
  return <p className="rounded-lg border border-line bg-surface px-6 py-8 text-center text-sm text-body">No results found. Try a different query or add more videos to your Brain.</p>;
}

function ErrorBanner({ message }: { message: string }) {
  return <p className="rounded-md border border-line bg-status-error-tint px-4 py-3 text-sm text-status-error">{message}</p>;
}

function safeUrl(url: string): string | undefined {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? url : undefined;
  } catch {
    return undefined;
  }
}

function ResultRow({ result }: { result: BrainResult }) {
  return (
    <li className="flex flex-col gap-1 rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-ink">{result.title}</span>
        {result.topic && <span className="rounded border border-line px-2 py-0.5 font-mono text-[11px] font-medium tracking-wider text-body">{result.topic}</span>}
        <span className="ml-auto shrink-0 font-mono text-xs text-muted">{result.score.toFixed(4)}</span>
      </div>
      {safeUrl(result.url) ? (
        <a
          href={safeUrl(result.url)}
          target="_blank"
          rel="noopener noreferrer"
          className="block max-w-full truncate font-mono text-xs text-body transition-ui hover:text-signal hover:underline"
        >
          {result.url}
        </a>
      ) : (
        <span className="block max-w-full truncate font-mono text-xs text-muted">{result.url}</span>
      )}
    </li>
  );
}

export default function BrainPage() {
  const { query, setQuery, results, searchState, errorMessage, runSearch } = useSemanticSearch();
  const [blankWarning, setBlankWarning] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleRun = () => {
    if (!query.trim()) { setBlankWarning(true); inputRef.current?.focus(); return; }
    setBlankWarning(false);
    runSearch();
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleRun();
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setQuery(e.target.value);
    if (blankWarning && e.target.value.trim()) setBlankWarning(false);
  };

  const loading = searchState === 'loading';

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="mb-1 text-2xl font-semibold tracking-tight text-ink">Brain</h1>
        <p className="text-sm text-body">Semantic search across everything saved to your Second Brain.</p>
      </div>

      <section className="flex gap-2">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder="e.g. machine learning, startup advice…"
          aria-label="Semantic search query"
          className="h-9 flex-1 rounded-md border border-line bg-canvas px-3 text-sm text-ink placeholder-muted transition-ui hover:border-line-strong focus:border-signal focus:outline-none disabled:opacity-50"
        />
        <button
          onClick={handleRun}
          disabled={loading}
          className="h-9 rounded-md bg-signal px-4 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <span aria-hidden="true" className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-muted border-t-ink" />
              Searching…
            </span>
          ) : 'Search'}
        </button>
      </section>

      {blankWarning && <p className="text-xs text-status-pending">Please enter a search query.</p>}

      <BrainGraph results={results} searchState={searchState} />

      {searchState === 'idle' && <IdleBanner />}
      {searchState === 'error' && <ErrorBanner message={errorMessage} />}
      {searchState === 'empty' && <EmptyBanner />}
      {searchState === 'results' && (
        <section>
          <p className="mb-2 font-mono text-xs text-muted">{results.length} result{results.length === 1 ? '' : 's'}</p>
          <ul className="space-y-2">
            {results.map((r) => <ResultRow key={r.url} result={r} />)}
          </ul>
        </section>
      )}
    </div>
  );
}
