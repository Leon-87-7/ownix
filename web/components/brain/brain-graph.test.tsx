// @vitest-environment jsdom
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BrainGraph } from './brain-graph';
import { expectNoAxeViolations } from '@/test/axe';

const { graphMethods, latestGraphPropsRef } = vi.hoisted(() => ({
  graphMethods: {
    zoom: vi.fn((scale?: number) => (scale == null ? 1 : undefined)),
    zoomToFit: vi.fn(),
    centerAt: vi.fn(),
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  latestGraphPropsRef: { current: {} as Record<string, any> },
}));

vi.mock('next/dynamic', () => ({
  default: () => {
    const MockForceGraph = React.forwardRef(
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      (props: Record<string, any>, ref) => {
        latestGraphPropsRef.current = props;
        if (ref && typeof ref === 'object') ref.current = graphMethods;
        return <div data-testid="force-graph" />;
      },
    );
    MockForceGraph.displayName = 'MockForceGraph';
    return MockForceGraph;
  },
}));

const payload = {
  nodes: [
    { id: '1', title: 'AI Video', topic: 'AI', url: 'https://example.com/ai', seen_count: 2 },
    { id: '2', title: 'Docs Video', topic: 'Docs', url: 'https://example.com/docs', seen_count: 1 },
    { id: '3', title: 'Loose Video', topic: '', url: 'https://example.com/loose', seen_count: 1 },
  ],
  edges: [
    { source: '1', target: '2', score: 0.7 },
    { source: '2', target: '3', score: 0.4 },
  ],
};

beforeEach(() => {
  latestGraphPropsRef.current = {};
  graphMethods.zoom.mockClear();
  graphMethods.zoomToFit.mockClear();
  graphMethods.centerAt.mockClear();
  graphMethods.zoom.mockImplementation((scale?: number) => (scale == null ? 1 : undefined));
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => payload }));
  vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
});

describe('BrainGraph', () => {
  it('adds graph controls and topic filters without refiltering graph data', async () => {
    render(<BrainGraph results={[]} searchState="idle" />);

    await screen.findByTestId('force-graph');
    expect(screen.getByRole('button', { name: /zoom in/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /fit visible graph/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /recenter graph/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /ai/i })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: /untagged/i })).toBeTruthy();
    expect(latestGraphPropsRef.current.graphData.nodes).toHaveLength(3);
    expect(latestGraphPropsRef.current.nodeVisibility(payload.nodes[0])).toBe(true);
    expect(latestGraphPropsRef.current.linkVisibility(payload.edges[0])).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: /docs/i }));

    expect(screen.getByRole('button', { name: /docs/i })).toHaveAttribute('aria-pressed', 'false');
    expect(latestGraphPropsRef.current.graphData.nodes).toHaveLength(3);
    expect(latestGraphPropsRef.current.nodeVisibility(payload.nodes[1])).toBe(false);
    expect(latestGraphPropsRef.current.linkVisibility(payload.edges[0])).toBe(false);
  });

  it('renders the error state when the graph request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 500 }));
    render(<BrainGraph results={[]} searchState="idle" />);

    expect(await screen.findByText(/could not load brain graph/i)).toBeTruthy();
    expect(screen.queryByTestId('force-graph')).toBeNull();
  });

  it('renders the empty state when there are no nodes', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) }));
    render(<BrainGraph results={[]} searchState="idle" />);

    expect(await screen.findByText(/no brain nodes yet/i)).toBeTruthy();
    expect(screen.queryByTestId('force-graph')).toBeNull();
  });

  it('escapes node labels before ForceGraph renders them as HTML tooltips', async () => {
    render(<BrainGraph results={[]} searchState="idle" />);

    await screen.findByTestId('force-graph');
    const label = latestGraphPropsRef.current.nodeLabel({
      ...payload.nodes[0],
      title: '<img src=x onerror="alert(1)"> & \'quoted\'',
      stars: '<svg/onload=alert(1)>',
    });

    expect(label).toBe('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;quoted&#39; \u00b7 \u2605&lt;svg/onload=alert(1)&gt;');
  });

  it('focuses only visible search matches and honors reduced motion', async () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }));

    render(<BrainGraph results={[{ url: 'https://example.com/ai' }, { url: 'https://example.com/docs' }]} searchState="results" />);

    await waitFor(() => expect(graphMethods.zoomToFit).toHaveBeenCalled());
    const automaticFocus = graphMethods.zoomToFit.mock.calls.at(-1)!;
    expect(automaticFocus[0]).toBe(0);
    expect(automaticFocus[2](payload.nodes[0])).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: /ai/i }));
    await waitFor(() => expect(graphMethods.zoomToFit.mock.calls.length).toBeGreaterThan(1));
    const filteredFocus = graphMethods.zoomToFit.mock.calls.at(-1)!;
    expect(filteredFocus[2](payload.nodes[0])).toBe(false);
    expect(filteredFocus[2](payload.nodes[1])).toBe(true);
  });

  it('refocuses when the match set changes but its size stays the same', async () => {
    const { rerender } = render(
      <BrainGraph results={[{ url: 'https://example.com/ai' }, { url: 'https://example.com/docs' }]} searchState="results" />,
    );

    await waitFor(() => expect(graphMethods.zoomToFit).toHaveBeenCalled());
    const before = graphMethods.zoomToFit.mock.calls.length;
    expect(graphMethods.zoomToFit.mock.calls.at(-1)![2](payload.nodes[1])).toBe(true); // docs matches

    // Same count (2), different set: drop docs, add loose.
    rerender(
      <BrainGraph results={[{ url: 'https://example.com/ai' }, { url: 'https://example.com/loose' }]} searchState="results" />,
    );

    await waitFor(() => expect(graphMethods.zoomToFit.mock.calls.length).toBeGreaterThan(before));
    const refocus = graphMethods.zoomToFit.mock.calls.at(-1)!;
    expect(refocus[2](payload.nodes[2])).toBe(true); // loose now matches
    expect(refocus[2](payload.nodes[1])).toBe(false); // docs no longer matches
  });

  it('wires zoom and recenter controls to the ForceGraph ref', async () => {
    render(<BrainGraph results={[]} searchState="idle" />);

    await screen.findByTestId('force-graph');
    fireEvent.click(screen.getByRole('button', { name: /zoom in/i }));
    fireEvent.click(screen.getByRole('button', { name: /recenter graph/i }));

    expect(graphMethods.zoom).toHaveBeenCalledWith(1.35, 450);
    expect(graphMethods.centerAt).toHaveBeenCalledWith(0, 0, 450);
  });

  describe('BrainNodeList (§3 accessibility handoff)', () => {
    it('marks the canvas aria-hidden and lists every node as a real link', async () => {
      render(<BrainGraph results={[]} searchState="idle" />);

      const canvas = await screen.findByTestId('force-graph');
      expect(canvas.closest('[aria-hidden="true"]')).toBeTruthy();

      for (const node of payload.nodes) {
        const link = screen.getByRole('link', { name: node.title });
        expect(link).toHaveAttribute('href', node.url);
        expect(link).toHaveAttribute('target', '_blank');
        expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
      }
    });

    it('shows each node\'s relationship (edge) count', async () => {
      render(<BrainGraph results={[]} searchState="idle" />);
      await screen.findByTestId('force-graph');

      const row = (title: string) =>
        screen.getByRole('link', { name: title }).closest('tr')!;

      // node 1 touches edge(1,2); node 2 touches edge(1,2) and edge(2,3); node 3 touches edge(2,3).
      expect(row('AI Video').textContent).toContain('1');
      expect(row('Docs Video').textContent).toContain('2');
      expect(row('Loose Video').textContent).toContain('1');
    });

    it('hides a node from the list when its topic is toggled off, in sync with the canvas', async () => {
      render(<BrainGraph results={[]} searchState="idle" />);
      await screen.findByTestId('force-graph');

      expect(screen.getByRole('link', { name: 'Docs Video' })).toBeTruthy();
      fireEvent.click(screen.getByRole('button', { name: /docs/i }));
      expect(screen.queryByRole('link', { name: 'Docs Video' })).toBeNull();
    });

    it('marks matched nodes and sorts them first while a search is active', async () => {
      render(
        <BrainGraph
          results={[{ url: 'https://example.com/docs' }]}
          searchState="results"
        />,
      );
      await screen.findByTestId('force-graph');

      const matchedRow = screen.getByRole('link', { name: 'Docs Video' }).closest('tr')!;
      expect(matchedRow.textContent).toContain('Match');
      const unmatchedRow = screen.getByRole('link', { name: 'AI Video' }).closest('tr')!;
      expect(unmatchedRow.textContent).not.toContain('Match');

      const rows = screen.getAllByRole('row');
      const titleCells = rows.map((r) => r.textContent);
      expect(titleCells.findIndex((t) => t?.includes('Docs Video'))).toBeLessThan(
        titleCells.findIndex((t) => t?.includes('AI Video')),
      );
    });

    it('has no axe violations, with or without active search matches', async () => {
      const { container, rerender } = render(<BrainGraph results={[]} searchState="idle" />);
      await screen.findByTestId('force-graph');
      await expectNoAxeViolations(container);

      rerender(
        <BrainGraph results={[{ url: 'https://example.com/docs' }]} searchState="results" />,
      );
      await waitFor(() => expect(screen.getByRole('link', { name: 'Docs Video' })).toBeTruthy());
      await expectNoAxeViolations(container);
    });
  });
});
