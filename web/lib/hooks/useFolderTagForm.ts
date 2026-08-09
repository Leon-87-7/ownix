'use client';

import { useCallback, useState } from 'react';
import { PRESET_COLORS, TAG_ICON_NAMES } from '@/components/ui/tag-picker';
import { apiPost } from '@/lib/fetch-utils';

export interface FolderAssignment {
  topic: string;
  linkIds: string[];
  count: number;
  checked: boolean;
  color: string;
  icon: string;
}

function shuffled<T>(items: readonly T[]): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

/** Folder-to-tag opt-in form (#497): fetches the distinct folders a Bookmark
 * import's links carry (topic is persisted at import regardless, so this is
 * safe to re-open any time — see CONTEXT.md "Bookmark import"), pre-assigns
 * a color/icon per folder by cycling a shuffled palette, and on confirm
 * creates one tag per checked folder and attaches it to every link in that
 * folder. A 409 name collision reuses the existing tag rather than failing —
 * a folder name may already be a tag from a prior import or manual creation. */
export function useFolderTagForm(jobId: string) {
  const [assignments, setAssignments] = useState<FolderAssignment[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/link-topics`);
      if (!res.ok) throw new Error('Could not load folders');
      const topics = (await res.json()) as {
        topic: string;
        link_ids: string[];
        count: number;
      }[];
      const colors = shuffled(PRESET_COLORS);
      const icons = shuffled(TAG_ICON_NAMES);
      setAssignments(
        topics.map((t, i) => ({
          topic: t.topic,
          linkIds: t.link_ids,
          count: t.count,
          checked: true,
          color: colors[i % colors.length],
          icon: icons[i % icons.length],
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load folders');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  const toggle = useCallback((topic: string) => {
    setAssignments((current) =>
      current.map((a) => (a.topic === topic ? { ...a, checked: !a.checked } : a)),
    );
  }, []);

  const setColor = useCallback((topic: string, color: string) => {
    setAssignments((current) =>
      current.map((a) => (a.topic === topic ? { ...a, color } : a)),
    );
  }, []);

  const setIcon = useCallback((topic: string, icon: string | undefined) => {
    setAssignments((current) =>
      current.map((a) => (a.topic === topic ? { ...a, icon: icon ?? '' } : a)),
    );
  }, []);

  const confirm = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    const skipped: string[] = [];
    let vocabCache: { id: string; name: string }[] | null = null;
    try {
      for (const a of assignments.filter((row) => row.checked)) {
        let tagId: string | null = null;
        const created = await apiPost<{ id: string }>('/api/controls/tags', {
          name: a.topic,
          meaning: '',
          color: a.color,
          icon: a.icon || null,
        });
        if (created.ok) {
          tagId = created.data.id;
        } else if (created.status === 409) {
          if (vocabCache === null) {
            const vocab = await fetch('/api/controls/tags');
            vocabCache = vocab.ok
              ? ((await vocab.json()) as { id: string; name: string }[])
              : [];
          }
          tagId = vocabCache.find((t) => t.name === a.topic)?.id ?? null;
          if (!tagId) skipped.push(a.topic);
        } else {
          // e.g. a folder name over the 80-char tag name limit — surfaced,
          // never silently dropped.
          skipped.push(a.topic);
        }
        if (!tagId) continue;
        const attachResults = await Promise.all(
          a.linkIds.map((linkId) =>
            fetch(
              `/api/brain/links/${encodeURIComponent(linkId)}/tags/${encodeURIComponent(tagId!)}`,
              { method: 'POST' },
            ),
          ),
        );
        if (attachResults.some((res) => !res.ok)) skipped.push(a.topic);
      }
      if (skipped.length > 0) {
        setError(`Could not create ${skipped.length === 1 ? 'tag' : 'tags'} for: ${skipped.join(', ')}`);
        return false;
      }
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create tags');
      return false;
    } finally {
      setSubmitting(false);
    }
  }, [assignments]);

  return {
    assignments,
    loading,
    error,
    submitting,
    load,
    toggle,
    setColor,
    setIcon,
    confirm,
  };
}
