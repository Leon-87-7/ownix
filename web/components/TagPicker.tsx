'use client'

interface TagSummary {
  id: string
  name: string
  color: string
  meaning: string
}

interface TagPickerProps {
  jobId: string
  jobTags: TagSummary[]
  allTags: TagSummary[]
  onTagChange: () => void
}

/**
 * Renders attached tags as removable colored chips and a select dropdown
 * for attaching additional tags from the user's tag library.
 */
export default function TagPicker({ jobId, jobTags, allTags, onTagChange }: TagPickerProps) {
  const attachedIds = new Set(jobTags.map((t) => t.id))
  const unattached = allTags.filter((t) => !attachedIds.has(t.id))

  async function handleAttach(tagId: string) {
    if (!tagId) return
    const res = await fetch(`/api/jobs/${jobId}/tags/${tagId}`, {
      method: 'POST',
      credentials: 'include',
    })
    if (res.ok || res.status === 201) onTagChange()
  }

  async function handleDetach(tagId: string) {
    const res = await fetch(`/api/jobs/${jobId}/tags/${tagId}`, {
      method: 'DELETE',
      credentials: 'include',
    })
    if (res.ok || res.status === 204) onTagChange()
  }

  return (
    <div className="rounded-lg border border-gray-700 bg-gray-800 p-4">
      <span className="mb-3 block text-xs font-semibold uppercase tracking-wide text-gray-400">
        Tags
      </span>

      {/* Attached tag chips */}
      <div className="flex flex-wrap gap-2 mb-3">
        {jobTags.length === 0 && (
          <span className="text-xs text-gray-500">No tags attached.</span>
        )}
        {jobTags.map((tag) => (
          <span
            key={tag.id}
            className="inline-flex items-center gap-1.5 rounded-full border border-gray-600 bg-gray-700 px-2.5 py-1 text-xs font-medium text-gray-100"
            title={tag.meaning || undefined}
          >
            {/* Color dot */}
            <span
              className="inline-block h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: tag.color }}
            />
            {tag.name}
            <button
              onClick={() => handleDetach(tag.id)}
              className="ml-0.5 rounded-full text-gray-400 hover:text-white transition-colors focus:outline-none"
              aria-label={`Remove tag ${tag.name}`}
            >
              &times;
            </button>
          </span>
        ))}
      </div>

      {/* Add tag dropdown */}
      {unattached.length > 0 && (
        <select
          className="rounded border border-gray-600 bg-gray-700 px-2 py-1 text-xs text-gray-200 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          value=""
          onChange={(e) => handleAttach(e.target.value)}
        >
          <option value="" disabled>
            Add tag…
          </option>
          {unattached.map((tag) => (
            <option key={tag.id} value={tag.id}>
              {tag.name}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}
