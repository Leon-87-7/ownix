'use client';

import type { FetchState } from '@/lib/fetch-utils';
import { useJobTags } from '@/lib/hooks/useJobTags';
import { useLinkTags } from '@/lib/hooks/useLinkTags';

// Mirrors src/api/jobs.py LINK_BACKED_CONTENT_TYPES.
export const LINK_BACKED_CONTENT_TYPES = new Set(['link', 'article', 'repo']);

// Once a link/article/repo job's URL resolves to a link row, the backend
// sweeps its job_tags onto the link (src/database.py sweep_job_tags_to_link)
// and this hook reads/writes through the link's tags instead. Carrier
// content types (short/long/photo/document) and not-yet-linked jobs keep
// using their own job_tags — no special-cased UI, same editable control.
export function useMergedTags(
  jobId: string,
  contentType: string,
  linkId: string | undefined,
  fetchState: FetchState = 'ok',
  disabled = false,
) {
  const useLink = LINK_BACKED_CONTENT_TYPES.has(contentType) && Boolean(linkId);
  const job = useJobTags(jobId, fetchState, disabled || useLink);
  const link = useLinkTags(linkId ?? '', [], disabled || !useLink, true);
  return useLink
    ? { jobTags: link.linkTags, allTags: link.allTags, toggleTag: link.toggleTag, createTag: link.createTag }
    : { jobTags: job.jobTags, allTags: job.allTags, toggleTag: job.toggleTag, createTag: job.createTag };
}
