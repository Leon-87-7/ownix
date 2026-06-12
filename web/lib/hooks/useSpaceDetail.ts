'use client';

import { useFetchDetail } from '@/lib/fetch-utils';

export interface SpaceDetail {
  id: string;
  chat_id: number;
  name: string;
  color: string;
  created_at: string;
  updated_at: string;
}

export function useSpaceDetail(spaceId: string) {
  const { data: space, setData: setSpace, fetchState } = useFetchDetail<SpaceDetail>(`/api/spaces/${spaceId}`);
  return { space, setSpace, fetchState };
}
