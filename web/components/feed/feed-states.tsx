function SkeletonRow() {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="h-4 w-2/3 animate-pulse rounded bg-raised" />
        <div className="flex shrink-0 gap-1.5">
          <div className="h-4 w-12 animate-pulse rounded bg-raised" />
          <div className="h-4 w-12 animate-pulse rounded bg-raised" />
        </div>
      </div>
      <div className="mt-2 h-3 w-36 animate-pulse rounded bg-raised" />
    </div>
  );
}

export function SkeletonList() {
  return (
    <div className="space-y-2" aria-hidden="true">
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
    </div>
  );
}

export function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3 rounded-md border border-line bg-status-error-tint px-4 py-3">
      <p className="text-sm text-status-error">{message}</p>
      <button
        onClick={onRetry}
        className="h-8 shrink-0 rounded-md bg-signal px-3.5 text-[13px] font-medium text-onsignal transition-colors duration-150 ease-out-quart hover:bg-signal-bright active:bg-signal-deep"
      >
        Retry
      </button>
    </div>
  );
}

export function EmptyState({ hasFilters, onClear }: { hasFilters: boolean; onClear: () => void }) {
  return (
    <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
      {hasFilters ? (
        <>
          <p className="text-sm font-medium text-ink">No jobs match these filters</p>
          <p className="mt-1 text-sm text-body">
            Try widening the search, or clear everything below.
          </p>
          <button
            onClick={onClear}
            className="mt-4 h-8 rounded-md border border-line px-3.5 text-[13px] font-medium text-ink transition-colors duration-150 ease-out-quart hover:bg-raised"
          >
            Clear filters
          </button>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-ink">No jobs yet</p>
          <p className="mt-1 text-sm text-body">
            Send a video, article, or repo URL to the Telegram bot — it will land here as it processes.
          </p>
        </>
      )}
    </div>
  );
}
