'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

/** Mirrors useJobAnnotation's shape, but the transcript already arrives with
 * the job payload (unlike annotations, which fetch separately) — so this
 * hook only needs to own the save path, not an initial GET.
 *
 * `initialTranscript` re-syncs into state whenever it changes, until the
 * user's first edit — a still-processing job mounts this hook with '' and
 * can pick up its real transcript later via the 'enriching' status poll
 * (TranscriptCard renders null until then, but the hook underneath it is
 * already live). Once the user edits, later `initialTranscript` changes are
 * ignored so a stale poll can't clobber an in-flight edit. */
export function useJobTranscript(jobId: string, initialTranscript: string) {
  const [transcript, setTranscript] = useState(initialTranscript);
  const editedRef = useRef(false);
  const latestSaveRef = useRef(0);

  useEffect(() => {
    if (!editedRef.current && initialTranscript) {
      setTranscript(initialTranscript);
    }
  }, [initialTranscript]);

  const handleSave = useCallback(async (md: string) => {
    editedRef.current = true;
    // Captured before the optimistic set below, so a rejected save can
    // revert to it - but only if no newer save has since superseded this
    // one (latestSaveRef), so a slow, stale failure can't stomp a later
    // edit that already saved fine.
    const previous = transcript;
    const attempt = ++latestSaveRef.current;
    // Set optimistically, from the debounce call's own argument rather than
    // the fetch response, so Copy/Download always reflect the latest edit
    // even if this save fails — and so two in-flight saves can't apply out
    // of order (the update order is JS call order, not network order). The
    // backend echoes body.transcript back unchanged, so there's nothing the
    // response would tell us that `md` doesn't already.
    setTranscript(md);
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/transcript`, {
        method: 'PUT',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: md }),
      });
      if (!res.ok && latestSaveRef.current === attempt) setTranscript(previous);
    } catch {
      if (latestSaveRef.current === attempt) setTranscript(previous);
    }
  }, [jobId, transcript]);

  return { transcript, handleSave };
}
