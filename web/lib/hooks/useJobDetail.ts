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
  checklists_md?: string | null;
  checklists_generated_at?: string | null;
  // Not a jobs column — a live COUNT of this job's Brain links, only used by
  // the delete-confirm checkbox (ADR-0046). Optional so fixtures elsewhere
  // in the test suite don't all need updating for a field only one UI reads.
  link_count?: number;
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
  code: string | null;
  code_lang: string | null;
  links: string | null;
}

export function useJobDetail(jobId: string, restricted = false) {
  const { data: job, setData, fetchState, reload } = useFetchDetail<JobDetail>(`${restricted ? '/api/preview/jobs' : '/api/jobs'}/${jobId}`);
  return { job, setData, fetchState, reload };
}
