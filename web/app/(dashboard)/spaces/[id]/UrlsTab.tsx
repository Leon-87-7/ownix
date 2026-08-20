"use client";

import { useState } from "react";
import Link from "next/link";
import { useSpaceUrls } from "@/lib/hooks/useSpaceUrls";
import { TypeBadge } from "@/components/ui/badges";
import { SkeletonLine } from "@/components/feed/feed-states";
import { Tooltip } from "@/components/ui/tooltip";
import { ReorderButtons } from "@/components/ui/reorder-buttons";
import { useAddSearch, type AddSearchResult } from "@/lib/hooks/useAddSearch";

export function UrlsTab({ spaceId }: { spaceId: string }) {
  const { spaceUrls, allJobs, loading, addJob, removeUrl, reorderUrl } =
    useSpaceUrls(spaceId);
  const { query, setQuery, results } = useAddSearch(allJobs);
  const [busyUrls, setBusyUrls] = useState<Set<string>>(new Set());
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const pinnedIds = new Set(spaceUrls.map((u) => u.id));
  const visibleResults = results.filter(
    (result) => !result.jobId || !pinnedIds.has(result.jobId),
  );

  const handleResult = async (result: AddSearchResult) => {
    setBusyUrls((current) => new Set(current).add(result.url));
    setRowErrors((current) => ({ ...current, [result.url]: "" }));
    try {
      let jobId = result.jobId;
      if (!jobId) {
        const response = await fetch("/api/jobs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: result.url }),
        });
        const data = (await response.json().catch(() => ({}))) as {
          job_id?: string;
          id?: string;
          detail?: string;
        };
        jobId = data.job_id || data.id;
        if (!response.ok || !jobId)
          throw new Error(data.detail || "Could not save this URL.");
      }
      await addJob(jobId);
    } catch (error) {
      setRowErrors((current) => ({
        ...current,
        [result.url]:
          error instanceof Error ? error.message : "Could not add this URL.",
      }));
    } finally {
      setBusyUrls((current) => {
        const next = new Set(current);
        next.delete(result.url);
        return next;
      });
    }
  };

  return (
    <section className="space-y-4">
      {loading ? (
        <div className="space-y-2">
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-full" />
          <SkeletonLine width="w-2/3" />
        </div>
      ) : spaceUrls.length === 0 ? (
        <p className="text-sm text-muted">No jobs added yet.</p>
      ) : (
        <ul className="space-y-2">
          {spaceUrls.map((item, idx) => {
            const display = item.title?.trim() || item.url;
            return (
              <li
                key={item.id}
                className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3"
              >
                <ReorderButtons
                  onUp={() => reorderUrl(idx, "up")}
                  onDown={() => reorderUrl(idx, "down")}
                  disableUp={idx === 0}
                  disableDown={idx === spaceUrls.length - 1}
                />
                <Tooltip content={display} mono>
                  <Link
                    href={`/jobs/${item.id}`}
                    className="min-w-0 flex-1 truncate text-sm text-ink transition-ui hover:text-signal"
                  >
                    {display}
                  </Link>
                </Tooltip>
                <TypeBadge label={item.content_type} />
                <button
                  onClick={() => removeUrl(item.id)}
                  className="ml-1 rounded border border-line px-2 py-0.5 text-xs font-medium text-status-error transition-ui hover:bg-raised"
                >
                  Remove
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="space-y-2 pt-2">
        <label htmlFor="add-search" className="sr-only">
          Search content to add
        </label>
        <input
          id="add-search"
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search saved jobs, links, and Brain…"
          className="h-9 w-full rounded-md border border-line bg-canvas px-3 text-sm text-ink placeholder:text-muted focus:border-signal focus:outline-none"
        />
        {visibleResults.length > 0 && (
          <ul className="space-y-2">
            {visibleResults.map((result) => (
              <li
                key={result.url}
                className="rounded-md border border-line bg-surface p-3"
              >
                <div className="flex items-center gap-3">
                  <span className="min-w-0 flex-1 truncate text-sm text-ink">
                    {result.title}
                  </span>
                  <button
                    type="button"
                    onClick={() => handleResult(result)}
                    disabled={busyUrls.has(result.url)}
                    className="h-8 rounded-md bg-signal px-3 text-button font-medium text-onsignal disabled:bg-surface disabled:text-muted"
                  >
                    {busyUrls.has(result.url)
                      ? "Adding…"
                      : result.jobId
                        ? "Add"
                        : "Save & Add"}
                  </button>
                </div>
                {rowErrors[result.url] && (
                  <p className="mt-2 text-xs text-status-error">
                    {rowErrors[result.url]}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
