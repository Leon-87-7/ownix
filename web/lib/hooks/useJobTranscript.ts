'use client';

import { useCallback, useState } from 'react';

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
    // Set optimistically, from the debounce call's own argument rather than
    // the fetch response, so Copy/Download always reflect the latest edit
    // even if this save fails — and so two in-flight saves can't apply out
    // of order (the update order is JS call order, not network order). The
    // backend echoes body.transcript back unchanged, so there's nothing the
    // response would tell us that `md` doesn't already.
    setTranscript(md);
    try {
      await fetch(`/api/jobs/${encodeURIComponent(jobId)}/transcript`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: md }),
      });
    } catch {
      // ponytail: no retry queue — add one if autosave failures start
      // actually losing data in practice.
    }
  }, [jobId]);

  return { transcript, handleSave };
}
