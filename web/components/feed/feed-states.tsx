/* @ds
name: SkeletonList / SkeletonGrid / SkeletonLine / SkeletonBlock / ErrorBanner / EmptyState
purpose: The shared loading/error/empty vocabulary for feed-like views — skeleton placeholders shaped like JobCard/PreviewCard rows, plus a retryable error banner and a two-message empty state (filtered vs genuinely empty).
when-not: SkeletonList/Grid are shaped specifically like job rows/cards — for a generic block placeholder elsewhere, SkeletonBlock is the primitive other features (e.g. ExportModal) reuse instead.
notes: EmptyState's copy branches on hasFilters — "no matches, try clearing" reads very differently from "nothing here yet."
status: inferred
*/

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

function SkeletonPreviewCard() {
  return (
    <div className="rounded-lg border border-line bg-surface p-3">
      <div className="aspect-video animate-pulse rounded-md border border-line bg-raised" />
      <div className="mt-3 space-y-2">
        <div className="h-4 w-5/6 animate-pulse rounded bg-raised" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-raised" />
        <div className="flex items-center justify-between gap-3 pt-1">
          <div className="h-3 w-24 animate-pulse rounded bg-raised" />
          <div className="h-4 w-14 animate-pulse rounded bg-raised" />
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
