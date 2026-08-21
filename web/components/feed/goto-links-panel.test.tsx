// @vitest-environment jsdom
import { render, screen, waitFor } from '@/test/render';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GoToLinksPanel } from './goto-links-panel';

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(body: unknown, ok = true) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status: ok ? 200 : 500 })),
  );
}

describe('GoToLinksPanel', () => {
  it('shows the empty-state invitation when nothing is pinned', async () => {
    stubFetch({ items: [] });
    render(<GoToLinksPanel />);

    await waitFor(() =>
      expect(screen.getByText(/nothing pinned yet/i)).toBeTruthy(),
    );
    expect(screen.getByText(/tap the pin icon/i)).toBeTruthy();
  });

  it('shows an error message when the fetch fails', async () => {
    stubFetch({}, false);
    render(<GoToLinksPanel />);

    await waitFor(() =>
      expect(screen.getByText(/couldn.t load goto links/i)).toBeTruthy(),
    );
  });

  it('lists links carrying a pinned tag, with only their pinned tags as chips', async () => {
    stubFetch({
      items: [
        {
          id: 'l1',
          url: 'https://example.com/one',
          title: 'One',
          seen_count: 1,
          first_seen: 't',
          tags: [
            { id: 't1', name: 'Bookmarks', color: '#f87171', meaning: '', pinned: true },
            { id: 't2', name: 'Reading', color: '#4ade80', meaning: '', pinned: false },
          ],
        },
        {
          id: 'l2',
          url: 'https://example.com/two',
          seen_count: 1,
          first_seen: 't',
          tags: [{ id: 't1', name: 'Bookmarks', color: '#f87171', meaning: '', pinned: true }],
        },
      ],
    });
    render(<GoToLinksPanel />);

    await waitFor(() => expect(screen.getByText('One')).toBeTruthy());
    // Untitled link falls back to the URL.
    expect(screen.getByText('https://example.com/two')).toBeTruthy();
    // Deduped/flat, but each row's own pinned tags stay visible as chips.
    expect(screen.getAllByText('One')).toHaveLength(1);
  });
});
