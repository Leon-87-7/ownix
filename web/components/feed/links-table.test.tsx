import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { fireEvent } from '@testing-library/react';
import { render, screen } from '@/test/render';
import { LinksTable } from '@/components/feed/links-table';
import type { UseLinksTableResult } from '@/lib/hooks/useLinksTable';

const baseLink = {
  id: 'lnk_1',
  url: 'https://thenounproject.com',
  title: '10M Free Icons & Stock Photos',
  topic: 'The video discusses consistent branding across platforms.',
  description: null as string | null,
  seen_count: 1,
  first_seen: '2026-07-14T09:05:00Z',
  last_seen: '2026-07-14T09:05:00Z',
  tags: [] as { id: string; name: string; color: string; meaning: string; icon?: string | null }[],
};

function makeLinksData(link: typeof baseLink): UseLinksTableResult {
  return {
    query: '',
    setQuery: () => {},
    view: { order: 'desc', size: 25 },
    viewLoaded: true,
    updateView: () => {},
    toggleOrder: () => {},
    data: { items: [link], limit: 25, offset: 0, total: 1 },
    state: 'ready',
    message: '',
    page: 0,
    setPage: () => {},
    jumpPage: '1',
    setJumpPage: () => {},
    submitJump: () => {},
    pageCount: 1,
    currentPage: 1,
    start: 1,
    end: 1,
    hasPrevious: false,
    hasNext: false,
    // null: no row preselected, so the preview panel's placeholder renders
    // instead of the full URL — keeps the "collapsed row never shows the
    // full URL" assertions below meaningful. Preview-panel-specific tests
    // override this.
    selectedLinkId: null,
    selectLink: () => {},
    hoverLink: () => {},
    cancelHover: () => {},
    selectAdjacent: () => {},
    preview: null,
    previewState: 'idle',
  } as unknown as UseLinksTableResult;
}

describe('LinksTable trimmed URL row', () => {
  it('renders a branded select-a-row empty preview state', () => {
    render(<LinksTable linksData={makeLinksData(baseLink)} />);

    expect(
      screen.getByRole('status', { name: 'Select a row to preview its details' }),
    ).toBeInTheDocument();
    expect(screen.getByText('◉ SELECT A ROW ◉ SELECT A ROW')).toBeInTheDocument();
  });

  it('selects the whole desktop row and cancels an unfinished hover', async () => {
    const user = userEvent.setup();
    const linksData = makeLinksData(baseLink);
    linksData.selectLink = vi.fn();
    linksData.hoverLink = vi.fn();
    linksData.cancelHover = vi.fn();
    linksData.selectAdjacent = vi.fn();
    render(<LinksTable linksData={linksData} />);
    const row = screen.getByRole('row', { name: /thenounproject\.com/i });

    expect(row).toHaveAttribute('tabindex', '0');
    fireEvent.focus(row);
    expect(linksData.selectLink).toHaveBeenCalledWith('lnk_1');
    await user.click(row);
    expect(linksData.selectLink).toHaveBeenCalledWith('lnk_1');
    fireEvent.keyDown(row, { key: 'ArrowDown' });
    expect(linksData.selectAdjacent).toHaveBeenCalledWith(1);

    await user.hover(row);
    expect(linksData.hoverLink).toHaveBeenCalledWith('lnk_1');
    await user.unhover(row);
    expect(linksData.cancelHover).toHaveBeenCalled();
  });

  it('shows pathname + query instead of the full URL', () => {
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          url: 'https://github.com/vercel-labs/skills?tab=readme',
        })}
      />,
    );
    expect(screen.getAllByText('/vercel-labs/skills?tab=readme').length).toBeGreaterThan(0);
    // The full URL never renders as collapsed row text.
    expect(
      screen.queryByText('https://github.com/vercel-labs/skills?tab=readme'),
    ).not.toBeInTheDocument();
  });

  it('falls back to the hostname for bare-domain links', () => {
    render(<LinksTable linksData={makeLinksData(baseLink)} />);
    expect(screen.getAllByText('thenounproject.com').length).toBeGreaterThan(0);
  });

  it('keeps the hostname for root-domain links with a query string', () => {
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          url: 'https://example.com/?u=1',
        })}
      />,
    );
    expect(screen.getAllByText('example.com?u=1').length).toBeGreaterThan(0);
    expect(screen.queryByText('/?u=1')).not.toBeInTheDocument();
  });

  it('provides the full URL in a tooltip for the trimmed URL', async () => {
    const user = userEvent.setup();
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          url: 'https://github.com/vercel-labs/skills?tab=readme',
        })}
      />,
    );

    await user.hover(
      screen.getAllByRole('link', { name: '/vercel-labs/skills?tab=readme' })[0],
    );
    expect(await screen.findByRole('tooltip')).toHaveTextContent(
      'https://github.com/vercel-labs/skills?tab=readme',
    );
  });

  it('renders a separate open-in-new-tab button alongside the URL anchor', () => {
    render(<LinksTable linksData={makeLinksData(baseLink)} />);
    expect(
      screen.getAllByRole('link', {
        name: 'Open https://thenounproject.com in a new tab',
      }).length,
    ).toBeGreaterThan(0);
  });

  it('reveals the full URL in the expanded More panel', async () => {
    const user = userEvent.setup();
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          url: 'https://github.com/vercel-labs/skills',
        })}
      />,
    );
    await user.click(screen.getAllByRole('button', { name: 'More' })[0]);
    expect(
      screen.getAllByText('https://github.com/vercel-labs/skills').length,
    ).toBeGreaterThan(0);
  });

  it('renders a More button even when the link has no title or description', () => {
    render(
      <LinksTable
        linksData={makeLinksData({ ...baseLink, title: null as unknown as string })}
      />,
    );
    expect(screen.getAllByRole('button', { name: 'More' }).length).toBeGreaterThan(0);
  });

  it('keeps only one mobile details card expanded', async () => {
    const user = userEvent.setup();
    const linksData = makeLinksData(baseLink);
    linksData.data.items = [
      baseLink,
      { ...baseLink, id: 'lnk_2', url: 'https://example.com/second' },
    ];
    linksData.selectLink = vi.fn();
    render(<LinksTable linksData={linksData} />);
    const moreButtons = screen.getAllByRole('button', { name: 'More' });

    await user.click(moreButtons[0]);
    expect(screen.getAllByRole('button', { name: 'Less' })).toHaveLength(1);

    await user.click(screen.getAllByRole('button', { name: 'More' })[0]);
    expect(screen.getAllByRole('button', { name: 'Less' })).toHaveLength(1);
    expect(linksData.selectLink).toHaveBeenLastCalledWith('lnk_2');
  });

  it('removes a failed desktop OG preview image', () => {
    HTMLElement.prototype.scrollIntoView = vi.fn();
    const linksData = makeLinksData(baseLink);
    linksData.selectedLinkId = 'lnk_1';
    linksData.preview = {
      id: 'lnk_1',
      og_image_url: 'https://cdn.example.com/og.jpg',
    };
    linksData.previewState = 'ready';
    const { container } = render(<LinksTable linksData={linksData} />);
    const image = container.querySelector('img[src="https://cdn.example.com/og.jpg"]');

    expect(image).not.toBeNull();
    fireEvent.error(image!);
    expect(
      container.querySelector('img[src="https://cdn.example.com/og.jpg"]'),
    ).toBeNull();
  });
});

describe('LinksTable standalone identity line', () => {
  it('shows title · description when the link has its own description', () => {
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          description: 'Over 10 million SVG and PNG icons for download.',
        })}
      />,
    );
    expect(
      screen.getAllByText(
        '10M Free Icons & Stock Photos · Over 10 million SVG and PNG icons for download.',
      ).length,
    ).toBeGreaterThan(0);
    // The video topic never appears collapsed.
    expect(
      screen.queryByText(/The video discusses/, { exact: false }),
    ).not.toBeInTheDocument();
  });

  it('reveals the provenance line only when expanded', async () => {
    const user = userEvent.setup();
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          description: 'Over 10 million SVG and PNG icons for download.',
        })}
      />,
    );
    // Mobile-only control (desktop uses the hover/arrow-key preview panel instead).
    await user.click(screen.getAllByRole('button', { name: 'More' })[0]);
    expect(
      screen.getAllByText(/From: The video discusses/, { exact: false }).length,
    ).toBeGreaterThan(0);
  });

  it('shows only the title while description is unresolved — topic never leaks into the row', () => {
    render(<LinksTable linksData={makeLinksData(baseLink)} />);
    expect(
      screen.getAllByText('10M Free Icons & Stock Photos').length,
    ).toBeGreaterThan(0);
    expect(
      screen.queryByText(/The video discusses/, { exact: false }),
    ).not.toBeInTheDocument();
  });
});

describe('LinkTagCluster', () => {
  it('shows the ghost + affordance on untagged rows', () => {
    render(<LinksTable linksData={makeLinksData(baseLink)} />);
    // Desktop row + mobile card each render the cluster trigger.
    expect(
      screen.getAllByRole('button', { name: 'Add link tag' }).length,
    ).toBeGreaterThan(0);
  });

  it('renders name-less dots for attached tags, names only in the tooltip', () => {
    render(
      <LinksTable
        linksData={makeLinksData({
          ...baseLink,
          tags: [
            { id: 't1', name: 'svg', color: '#f87171', meaning: 'vector art' },
            { id: 't2', name: 'ui', color: '#60a5fa', meaning: '' },
          ],
        })}
      />,
    );
    const clusters = screen.getAllByRole('button', { name: 'Edit 2 link tags' });
    expect(clusters.length).toBeGreaterThan(0);
    // The tag name never renders as row text — badge is a color dot only.
    expect(screen.queryByText('svg')).not.toBeInTheDocument();
  });
});
