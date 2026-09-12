import { describe, expect, it } from 'vitest';
import {
  adjacentScopeQuery,
  buildJobHref,
  feedScopeQuery,
  parseFeedScope,
  type FeedScope,
} from '@/lib/feed-scope';

const FULL: FeedScope = {
  contentType: 'short',
  status: 'done',
  query: 'react',
  checklistOnly: true,
  tags: ['t1', 't2'],
  view: 'links',
};

describe('feedScopeQuery / parseFeedScope', () => {
  it('round-trips a full scope', () => {
    const params = new URLSearchParams(feedScopeQuery(FULL));
    expect(parseFeedScope(params)).toEqual(FULL);
  });

  it('round-trips an empty scope as a bare feed', () => {
    const empty = feedScopeQuery({});
    expect(empty).toEqual({});
    expect(parseFeedScope(new URLSearchParams(empty))).toEqual({
      contentType: '',
      status: '',
      query: '',
      checklistOnly: false,
      tags: [],
      view: 'jobs',
    });
  });

  it('writes only the non-default view', () => {
    expect(feedScopeQuery({ view: 'jobs' })).toEqual({});
    expect(feedScopeQuery({ view: 'links' })).toEqual({ view: 'links' });
  });

  it('drops an unknown ?type= instead of narrowing by it', () => {
    const params = new URLSearchParams({ type: 'bogus', status: 'done' });
    expect(parseFeedScope(params).contentType).toBe('');
    expect(parseFeedScope(params).status).toBe('done');
  });

  it('trims the query and omits a whitespace-only one', () => {
    expect(feedScopeQuery({ query: '  spaced  ' })).toEqual({ q: 'spaced' });
    expect(feedScopeQuery({ query: '   ' })).toEqual({});
  });
});

describe('adjacentScopeQuery', () => {
  it('emits the job APIs vocabulary, not the feed’s', () => {
    expect(adjacentScopeQuery(FULL)).toEqual({
      content_type: 'short',
      status: 'done',
      has_checklist: 'true',
      tags: 't1,t2',
    });
  });
});

describe('buildJobHref', () => {
  it('carries both vocabularies so Back can rebuild the feed', () => {
    expect(buildJobHref('job-1', FULL)).toEqual({
      pathname: '/jobs/job-1',
      query: {
        content_type: 'short',
        status: 'done',
        q: 'react',
        checklist: '1',
        tags: 't1,t2',
      },
    });
  });
});
