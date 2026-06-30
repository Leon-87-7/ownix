// @vitest-environment jsdom
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { BrainGraph } from './brain-graph';

const { graphMethods, latestGraphPropsRef } = vi.hoisted(() => ({
  graphMethods: {
    zoom: vi.fn((scale?: number) => (scale == null ? 1 : undefined)),
    zoomToFit: vi.fn(),
    centerAt: vi.fn(),
  },
  latestGraphPropsRef: { current: {} as Record<string, any> },
}));

vi.mock('next/dynamic', () => ({
  default: () =>
    React.forwardRef((props: Record<string, any>, ref) => {
      latestGraphPropsRef.current = props;
      if (ref && typeof ref === 'object') ref.current = graphMethods;
      return <div data-testid="force-graph" />;
    }),
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
});
