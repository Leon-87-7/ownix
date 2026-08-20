"use client";

import { useEffect, useMemo, useState } from "react";
import type { JobSummary } from "@/components/feed/job-card";
import { useFuseSearch } from "@/lib/hooks/useFuseSearch";

export interface AddSearchResult {
  url: string;
  title: string;
  jobId?: string;
}
interface RemoteHit {
  url: string;
  title?: string | null;
}

export function mergeAddSearchResults(
  jobs: JobSummary[],
  fuseHits: JobSummary[],
  links: RemoteHit[],
  brain: RemoteHit[],
) {
  const jobsByUrl = new Map(jobs.map((job) => [job.url.toLowerCase(), job]));
  const merged = new Map<string, AddSearchResult>();
  const add = (hit: RemoteHit, jobId?: string) => {
    const key = hit.url.toLowerCase();
    const matched = jobsByUrl.get(key);
    const next = {
      url: hit.url,
      title: hit.title?.trim() || hit.url,
      jobId: jobId || matched?.id,
    };
    const current = merged.get(key);
    if (!current || (!current.jobId && next.jobId)) merged.set(key, next);
  };
  fuseHits.forEach((hit) => add(hit, hit.id));
  links.forEach((hit) => add(hit));
  brain.forEach((hit) => add(hit));
  return [...merged.values()];
}

export async function parseHits<T>(
  result: PromiseSettledResult<Response>,
  extract: (data: unknown) => T[],
): Promise<T[]> {
  if (result.status !== "fulfilled" || !result.value.ok) return [];
  try {
    const hits = extract(await result.value.json());
    return Array.isArray(hits) ? hits : [];
  } catch {
    return [];
  }
}

export function useAddSearch(jobs: JobSummary[]) {
  const { query, setQuery, displayedJobs } = useFuseSearch(jobs);
  const [links, setLinks] = useState<RemoteHit[]>([]);
  const [brain, setBrain] = useState<RemoteHit[]>([]);

  useEffect(() => {
    const trimmed = query.trim();
    if (!trimmed) {
      setLinks([]);
      setBrain([]);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      const encoded = encodeURIComponent(trimmed);
      const [linksResult, brainResult] = await Promise.allSettled([
        fetch(`/api/brain/links?q=${encoded}`, { signal: controller.signal }),
        fetch(`/api/brain/search?q=${encoded}`, { signal: controller.signal }),
      ]);
      const nextLinks = await parseHits(linksResult, (data) => (data as { items: RemoteHit[] }).items);
      const nextBrain = await parseHits(brainResult, (data) => data as RemoteHit[]);
      if (controller.signal.aborted) return;
      setLinks(nextLinks);
      setBrain(nextBrain);
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query]);

  const results = useMemo(
    () =>
      query.trim()
        ? mergeAddSearchResults(jobs, displayedJobs, links, brain)
        : [],
    [jobs, displayedJobs, links, brain, query],
  );
  return { query, setQuery, results };
}
