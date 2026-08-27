'use client';

import { TagMenu, TagChips } from '@/components/ui/tag-picker';
import { useMergedTags } from '@/lib/hooks/useMergedTags';

// Attached tag badges + compact dropdown for a feed card. Eager so existing
// tags show without opening the menu.
// ponytail: N feed cards still fire N per-job tag fetches (the shared vocabulary
// fetch is deduped via useJobTags -> fetchVocabulary). If per-job also bites, fold
// tags into /api/jobs.
export function JobCardTags({
  jobId,
  contentType,
  linkId,
  countOnly = false,
}: {
  jobId: string;
  contentType: string;
  linkId?: string;
  countOnly?: boolean;
}) {
  const { jobTags, allTags, toggleTag, createTag } = useMergedTags(jobId, contentType, linkId);
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* countOnly: signal attached tags via the menu's count badge, no chips. */}
      {!countOnly && (
        <TagChips jobTags={jobTags} onRemove={(id) => toggleTag(id, true)} compact />
      )}
      <TagMenu jobTags={jobTags} allTags={allTags} onToggle={toggleTag} onCreate={createTag} />
    </div>
  );
}
