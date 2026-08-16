'use client';

import { useState } from 'react';

import { useFetchList, apiPost } from '@/lib/fetch-utils';

interface RepoCandidate {
  url: string;
  name: string;
}

/** Cached GitHub repo candidates offered after a long/short job finishes
 * (src/services/repo_followup.py) — Telegram's only surface for this until
 * now. Index into `candidates` doubles as the backend's pick index, so a
 * picked entry is disabled in place rather than removed (removing would
 * shift later indices out of sync with the server's cached list). */
export function RepoFollowupPanel({ jobId }: { jobId: string }) {
  const { data, loading } = useFetchList<RepoCandidate>(
    `/api/jobs/${jobId}/repo-followups`,
    'repo follow-ups',
  );
  const [picked, setPicked] = useState<Set<number>>(new Set());

  // A same-origin `/api/jobs` mock/proxy that isn't specifically shaped for
  // this nested route can hand back a non-array body — never trust the
  // network response's shape blindly.
  const candidates = Array.isArray(data) ? data : [];
  if (loading || candidates.length === 0) return null;

  const pick = async (idx: number) => {
    setPicked((prev) => new Set(prev).add(idx));
    await apiPost(`/api/jobs/${jobId}/repo-followups/${idx}`, {});
  };

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-line bg-surface p-4">
      <p className="text-sm font-medium text-ink">Found GitHub repos — analyze one next?</p>
      <div className="flex flex-wrap gap-2">
        {candidates.map((candidate, idx) => (
          <button
            key={candidate.url}
            type="button"
            disabled={picked.has(idx)}
            onClick={() => void pick(idx)}
            className="h-8 rounded-md border border-line px-3 text-button font-medium text-ink transition-ui hover:bg-raised disabled:opacity-50"
          >
            {picked.has(idx) ? (
              <span className="ownix-shimmer">Queued: {candidate.name}</span>
            ) : (
              `Analyze ${candidate.name}`
            )}
          </button>
        ))}
      </div>
    </div>
  );
}
