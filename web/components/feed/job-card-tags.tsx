'use client';

/* @ds
name: JobCardTags
purpose: Thin composition of TagChips + TagMenu (ui/tag-picker) scoped to one job's attached tags — the tag affordance embedded in JobCard and PreviewCard.
variants:
  countOnly: drops the chips, showing only TagMenu's count badge — used inside PreviewCard where space is tight.
when-not: Not a general-purpose tag control — it's wired to a specific jobId via useJobTags. For a standalone tag UI use TagMenu directly.
notes: Each instance fetches its own tags (N cards = N fetches) — a known scaling limit, not addressed here.
status: inferred
*/

import { TagMenu, TagChips } from '@/components/ui/tag-picker';
import { useJobTags } from '@/lib/hooks/useJobTags';

// Attached tag badges + compact dropdown for a feed card. Eager so existing
// tags show without opening the menu.
// ponytail: N feed cards = N tag fetches. If it bites, fold tags into /api/jobs.
export function JobCardTags({ jobId, countOnly = false }: { jobId: string; countOnly?: boolean }) {
  const { jobTags, allTags, toggleTag, createTag } = useJobTags(jobId, 'ok');
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
