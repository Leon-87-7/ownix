'use client';

import { TagMenu, TagChips } from '@/components/TagPicker';
import { useJobTags } from '@/lib/hooks/useJobTags';

// Attached tag badges + compact dropdown for a feed card. Eager so existing
// tags show without opening the menu.
// ponytail: N feed cards = N tag fetches. If it bites, fold tags into /api/jobs.
export function JobCardTags({ jobId, countOnly = false }: { jobId: string; countOnly?: boolean }) {
  const { jobTags, allTags, toggleTag, createTag } = useJobTags(jobId, 'ok');
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {/* countOnly: signal attached tags via the menu's count badge, no chips. */}
      {!countOnly && <TagChips jobTags={jobTags} onRemove={(id) => toggleTag(id, true)} />}
      <TagMenu jobTags={jobTags} allTags={allTags} onToggle={toggleTag} onCreate={createTag} />
    </div>
  );
}
