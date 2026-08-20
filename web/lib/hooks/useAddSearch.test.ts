import { describe, expect, it } from 'vitest';
import { mergeAddSearchResults, parseHits } from './useAddSearch';
import type { JobSummary } from '@/components/feed/job-card';

const job = { id: 'j1', url: 'HTTPS://example.com/a', title: 'Saved', content_type: 'article', status: 'done', created_at: '' } as JobSummary;
describe('mergeAddSearchResults', () => {
  it('dedupes case-insensitive URLs and prefers/resolves saved jobs', () => {
    const results = mergeAddSearchResults([job], [job], [{ url: 'https://EXAMPLE.com/a', title: 'Link' }, { url: 'https://example.com/b', title: 'Only link' }], [{ url: 'https://example.com/a', title: 'Brain' }]);
    expect(results).toEqual([
      { url: job.url, title: 'Saved', jobId: 'j1' },
      { url: 'https://example.com/b', title: 'Only link', jobId: undefined },
    ]);
  });

  it('resolves a brain-only hit against the loaded job list', () => {
    const results = mergeAddSearchResults([job], [], [], [{ url: 'https://EXAMPLE.com/a', title: 'Brain' }]);
    expect(results).toEqual([{ url: 'https://EXAMPLE.com/a', title: 'Brain', jobId: 'j1' }]);
  });
});

describe('parseHits', () => {
  it('returns an empty array when a successful response has no items field', async () => {
    const response = new Response(JSON.stringify({}), { status: 200 });
    const hits = await parseHits<{ url: string }>(
      { status: 'fulfilled', value: response },
      (data) => (data as { items: { url: string }[] }).items,
    );
    expect(hits).toEqual([]);
  });
});
