'use client';

import { useFetchList } from '@/lib/fetch-utils';
import type { SpaceSummary } from '@/components/spaces/space-card';

export function useSpaceList() {
  const { data: spaces, loading, fetchError, reload } = useFetchList<SpaceSummary>('/api/spaces', 'spaces');
  return { spaces, loading, error: fetchError ?? null, reload };
}
