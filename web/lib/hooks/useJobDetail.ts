'use client';

import { useFetchDetail } from '@/lib/fetch-utils';

export interface JobDetail {
  id: string;
  url: string;
  content_type: string;
  status: string;
  title: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  error_msg: string | null;
  drive_url: string | null;
  // Long/article/repo enrichment fields
  ai_topic: string | null;
  ai_objective: string | null;
  ai_action_points: string | null;
  ai_tools: string | null;
  ai_market_data: string | null;
  promise_gap: string | null;
  template: string | null;
  template_analysis: string | null;
  // Short pipeline fields
  summary: string | null;
  transcript: string | null;
  links: string | null;
}

export function useJobDetail(jobId: string) {
  const { data: job, fetchState } = useFetchDetail<JobDetail>(`/api/jobs/${jobId}`);
  return { job, fetchState };
}
