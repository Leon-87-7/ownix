// @vitest-environment jsdom
import { renderHook } from '@/test/render';
import { act } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { useFuseSearch } from './useFuseSearch';
import type { JobSummary } from '@/components/feed/job-card';

const job = (id: string, title: string): JobSummary =>
  ({ id, title, url: `https://example.com/${id}` }) as JobSummary;

describe('useFuseSearch', () => {
  it('matches once jobs arrive after an initial empty list, on the same render', () => {
    // CodeRabbit (PR #626): the index used to rebuild in a useEffect, so a
    // query already active when `jobs` changed would search the previous
    // (stale) index for that render, with nothing forcing a re-render to
    // pick up the corrected one afterward.
    const { result, rerender } = renderHook(
      ({ jobs }) => useFuseSearch(jobs, 'video'),
      { initialProps: { jobs: [] as JobSummary[] } },
    );

    expect(result.current.displayedJobs).toEqual([]);

    act(() => {
      rerender({ jobs: [job('j1', 'My video')] });
    });

    expect(result.current.displayedJobs.map((j) => j.id)).toEqual(['j1']);
  });

  it('returns the unfiltered list when the query is blank', () => {
    const jobs = [job('j1', 'Alpha'), job('j2', 'Beta')];
    const { result } = renderHook(() => useFuseSearch(jobs));

    expect(result.current.displayedJobs).toEqual(jobs);
  });
});
