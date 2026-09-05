'use client';

import dynamic from 'next/dynamic';
import { useSpaceContext } from '@/lib/hooks/useSpaceContext';
import { SkeletonLine } from '@/components/feed/feed-states';

const MarkdownEditor = dynamic(() => import('@/components/ui/markdown-editor'), {
  ssr: false,
  loading: () => (
    <div className="rounded-lg border border-line bg-surface p-4 text-sm text-muted">
      Loading editor...
    </div>
  ),
});

export function NewsletterContextList({ spaceId }: { spaceId: string }) {
  const { blobs, loading, blobError, updateBlob, patchBlobName } = useSpaceContext(spaceId);

  if (loading) {
    return (
      <div className="space-y-2">
        <SkeletonLine width="w-full" />
        <SkeletonLine width="w-2/3" />
      </div>
    );
  }

  if (blobs.length === 0) {
    return (
      <div className="rounded-lg border border-line bg-surface px-4 py-6">
        <p className="text-sm font-medium text-ink">No context yet</p>
        <p className="mt-1 text-sm text-body">
          The next processed issue will append a Gemini-authored context note here.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-4">
      {blobError && (
        <p role="alert" className="text-sm text-status-error">
          {blobError}
        </p>
      )}
      {blobs.map((blob) => (
        <div key={blob.id} className="space-y-2">
          <input
            type="text"
            value={blob.name}
            onChange={(event) => patchBlobName(blob.id, event.target.value)}
            onBlur={(event) => updateBlob(blob.id, event.target.value, blob.content)}
            className="w-full rounded-md border border-line bg-canvas px-3 py-1.5 text-sm text-ink transition-ui hover:border-line-strong focus:border-signal focus:outline-none"
            placeholder="Context name"
          />
          <MarkdownEditor
            initialMarkdown={blob.content}
            onSave={(markdown) => updateBlob(blob.id, blob.name, markdown)}
            label="Context"
          />
        </div>
      ))}
    </section>
  );
}
