// @vitest-environment jsdom
import { render, screen } from '@/test/render';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { JobCardTags } from './job-card-tags';
import { useJobTags } from '@/lib/hooks/useJobTags';
import { useLinkTags } from '@/lib/hooks/useLinkTags';

vi.mock('@/lib/hooks/useJobTags', () => ({ useJobTags: vi.fn() }));
vi.mock('@/lib/hooks/useLinkTags', () => ({ useLinkTags: vi.fn() }));
vi.mock('@/components/ui/tag-picker', () => ({
  TagChips: ({ jobTags }: { jobTags: { name: string }[] }) => <div>{jobTags[0]?.name}</div>,
  TagMenu: () => <button>Tags</button>,
}));

const jobState = {
  jobTags: [{ id: 'job-tag', name: 'Job tag', color: '', meaning: '' }],
  allTags: [],
  toggleTag: vi.fn(),
  createTag: vi.fn(),
  refetchTags: vi.fn(),
};
const linkState = {
  linkTags: [{ id: 'link-tag', name: 'Link tag', color: '', meaning: '' }],
  allTags: [],
  toggleTag: vi.fn(),
  createTag: vi.fn(),
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(useJobTags).mockReturnValue(jobState);
  vi.mocked(useLinkTags).mockReturnValue(linkState);
});

describe('JobCardTags', () => {
  it.each(['link', 'article', 'repo'])('uses link tags for a resolved %s job', (contentType) => {
    render(<JobCardTags jobId="job-1" contentType={contentType} linkId="link-1" />);
    expect(screen.getByText('Link tag')).toBeInTheDocument();
    expect(useJobTags).toHaveBeenCalledWith('job-1', 'ok', true);
    expect(useLinkTags).toHaveBeenCalledWith('link-1', [], false, true);
  });

  it.each(['article', 'repo'])('keeps the normal editor while an %s link is absent', (contentType) => {
    render(<JobCardTags jobId="job-1" contentType={contentType} />);
    expect(screen.getByText('Job tag')).toBeInTheDocument();
    expect(useJobTags).toHaveBeenCalledWith('job-1', 'ok', false);
    expect(useLinkTags).toHaveBeenCalledWith('', [], true, true);
  });

  it.each(['short', 'long', 'photo', 'document'])('leaves %s job tags unchanged', (contentType) => {
    render(<JobCardTags jobId="job-1" contentType={contentType} linkId="link-1" />);
    expect(screen.getByText('Job tag')).toBeInTheDocument();
    expect(useLinkTags).toHaveBeenCalledWith('link-1', [], true, true);
  });
});
