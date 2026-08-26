function SkeletonRow() {
  return (
    <div className="rounded-lg border border-line bg-surface px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="h-4 w-2/3 skeleton-shimmer rounded" />
        <div className="flex shrink-0 gap-1.5">
          <div className="h-4 w-12 skeleton-shimmer rounded" />
          <div className="h-4 w-12 skeleton-shimmer rounded" />
        </div>
      </div>
      <div className="mt-2 h-3 w-36 skeleton-shimmer rounded" />
    </div>
  );
}

/* Mirrors PreviewCard's actual structure: icon square + single title line +
   badge on row one, timestamp + tags on row two (not the generic two-line
   title block this used to show). */
function SkeletonPreviewCard() {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="aspect-video skeleton-shimmer rounded-md border border-line" />
      <div className="mt-3 flex flex-col gap-2">
        <div className="flex items-start gap-2">
          <div className="h-5 w-5 shrink-0 skeleton-shimmer rounded-md" />
          <div className="h-4 flex-1 skeleton-shimmer rounded" />
          <div className="h-4 w-10 shrink-0 skeleton-shimmer rounded" />
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="h-3 w-20 skeleton-shimmer rounded" />
          <div className="h-4 w-8 skeleton-shimmer rounded" />
        </div>
      </div>
    </div>
  );
}

export function SkeletonList() {
  return (
    <div
      className="space-y-2"
      aria-hidden="true"
    >
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
      <SkeletonRow />
    </div>
  );
}

export function SkeletonGrid() {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3"
      aria-hidden="true"
    >
      <SkeletonPreviewCard />
      <SkeletonPreviewCard />
      <SkeletonPreviewCard />
      <SkeletonPreviewCard />
      <SkeletonPreviewCard />
      <SkeletonPreviewCard />
    </div>
  );
}

export function SkeletonLine({
  width = 'w-2/3',
}: {
  width?: string;
}) {
  return (
    <div
      className={`h-4 ${width} animate-pulse rounded bg-raised`}
      aria-hidden="true"
    />
  );
}

export function SkeletonBlock({
  className = 'h-24 w-full',
}: {
  className?: string;
}) {
  return (
    <div
      className={`animate-pulse rounded-lg border border-line bg-surface ${className}`}
      aria-hidden="true"
    />
  );
}

export function ErrorBanner({
  message,
  onRetry,
}: {
  message: string;
  onRetry: () => void;
}) {
  return (
    <div className="mb-3 flex items-center justify-between gap-3 rounded-md border border-line bg-status-error-tint px-4 py-3">
      <p className="text-sm text-status-error">{message}</p>
      <button
        onClick={onRetry}
        className="h-8 shrink-0 rounded-md bg-signal px-3.5 text-button font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep"
      >
        Retry
      </button>
    </div>
  );
}

export function EmptyState({
  hasFilters,
  onClear,
}: {
  hasFilters: boolean;
  onClear: () => void;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface px-6 py-10 text-center">
      {hasFilters ? (
        <>
          <p className="text-sm font-medium text-ink">
            No jobs match these filters
          </p>
          <p className="mt-1 text-sm text-body">
            Try widening the search, or clear everything below.
          </p>
          <button
            onClick={onClear}
            className="mt-4 h-8 rounded-md border border-line px-3.5 text-button font-medium text-ink transition-ui hover:bg-raised"
          >
            Clear filters
          </button>
        </>
      ) : (
        <>
          <p className="text-sm font-medium text-ink">No jobs yet</p>
          <p className="mt-1 text-sm text-body">
            Send a video, article, or repo URL to the Telegram bot —
            it will land here as it processes.
          </p>
        </>
      )}
    </div>
  );
}
