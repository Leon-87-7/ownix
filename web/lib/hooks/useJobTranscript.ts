'use client';

import { useCallback, useState } from 'react';

interface TranscriptSaveResponse {
  transcript: string;
}

/** Mirrors useJobAnnotation's shape, but the transcript already arrives with
 * the job payload (unlike annotations, which fetch separately) — so this
 * hook only needs to own the save path, not an initial GET.
 *
 * `initialTranscript` seeds state once at mount and is never re-synced to a
 * later `job.transcript` change — same frozen-snapshot behavior as
 * useJobAnnotation and as MarkdownEditor's own `initialMarkdown` prop. This
 * page's job never rewrites `transcript` after it's first set, so it's a
 * non-issue in practice; if that ever changes, this hook needs an effect
 * that re-syncs when there's no unsaved edit pending. */
export function useJobTranscript(jobId: string, initialTranscript: string) {
  const [transcript, setTranscript] = useState(initialTranscript);

  const handleSave = useCallback(async (md: string) => {
    try {
      const res = await fetch(`/api/jobs/${jobId}/transcript`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: md }),
      });
      if (res.ok) {
        const saved: TranscriptSaveResponse = await res.json();
        setTranscript(saved.transcript);
      }
    } catch {
      // silently ignore network errors during auto-save, mirrors useJobAnnotation
    }
  }, [jobId]);

  return { transcript, handleSave };
}
