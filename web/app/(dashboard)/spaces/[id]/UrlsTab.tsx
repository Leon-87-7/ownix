'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useSpaceUrls } from '@/lib/hooks/useSpaceUrls';
import { TypeBadge } from '@/components/badges';
import { Spinner } from '@/components/ui';
import { Tooltip } from '@/components/ui/tooltip';

export function UrlsTab({ spaceId }: { spaceId: string }) {
  const { spaceUrls, allJobs, loading, addJob, removeUrl, reorderUrl } = useSpaceUrls(spaceId);
  const [selectedJobId, setSelectedJobId] = useState('');
  const [addingJob, setAddingJob] = useState(false);

  const pinnedIds = new Set(spaceUrls.map((u) => u.id));
  const availableJobs = allJobs.filter((j) => !pinnedIds.has(j.id));

  const handleAddJob = async () => {
    if (!selectedJobId) return;
    setAddingJob(true);
    try {
      await addJob(selectedJobId);
      setSelectedJobId('');
    } finally {
      setAddingJob(false);
    }
  };

  return (
    <section className="space-y-4">
      {loading ? (
        <div className="flex items-center gap-2 text-sm text-body">
          <Spinner size={3} />
          Loading…
        </div>
      ) : spaceUrls.length === 0 ? (
        <p className="text-sm text-muted">No jobs added yet.</p>
      ) : (
        <ul className="space-y-2">
          {spaceUrls.map((item, idx) => {
            const display = item.title?.trim() || item.url;
            return (
              <li key={item.id} className="flex items-center gap-3 rounded-lg border border-line bg-surface px-4 py-3">
                <div className="flex flex-col gap-0.5">
                  <button
                    onClick={() => reorderUrl(idx, 'up')}
                    disabled={idx === 0}
                    className="rounded px-1 py-0.5 text-xs text-muted transition-ui hover:text-ink disabled:opacity-30"
                    aria-label="Move up"
                  >&#9650;</button>
                  <button
                    onClick={() => reorderUrl(idx, 'down')}
                    disabled={idx === spaceUrls.length - 1}
                    className="rounded px-1 py-0.5 text-xs text-muted transition-ui hover:text-ink disabled:opacity-30"
                    aria-label="Move down"
                  >&#9660;</button>
                </div>
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

      <div className="flex items-center gap-3 pt-2">
        <select
          value={selectedJobId}
          onChange={(e) => setSelectedJobId(e.target.value)}
          className="h-9 flex-1 rounded-md border border-line bg-canvas px-3 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
        >
          <option value="">Select a job to add…</option>
          {availableJobs.map((j) => (
            <option key={j.id} value={j.id}>
              {j.title?.trim() || j.url} ({j.content_type})
            </option>
          ))}
        </select>
        <button
          onClick={handleAddJob}
          disabled={!selectedJobId || addingJob}
          className="h-9 rounded-md bg-signal px-4 text-[13px] font-medium text-onsignal transition-ui hover:bg-signal-bright active:bg-signal-deep disabled:bg-surface disabled:text-muted"
        >
          {addingJob ? 'Adding…' : 'Add'}
        </button>
      </div>
    </section>
  );
}
