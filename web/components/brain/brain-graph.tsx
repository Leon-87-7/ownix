'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ComponentType, ReactNode, Ref } from 'react';
import dynamic from 'next/dynamic';
import type { ForceGraphMethods, ForceGraphProps } from 'react-force-graph-2d';
import { useReducedMotion } from '@/lib/hooks/useReducedMotion';
import { safeUrl } from '@/lib/url-utils';

// react-force-graph touches `window` at import time — load it client-only (ADR-0028).
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false }) as ComponentType<
  ForceGraphProps<GraphNode, GraphLink> & { ref?: Ref<ForceGraphMethods<GraphNode, GraphLink>> }
>;

type GraphNode = {
  id: string;
  title: string;
  topic: string;
  url: string;
  seen_count: number;
  stars?: number | null;
  pushed_at?: string | null;
};
type GraphEdge = { source: string; target: string; score: number };
type GraphPayload = { nodes: GraphNode[]; edges: GraphEdge[] };
type SearchResult = { url: string };
type GraphLink = GraphEdge;
type RenderNode = GraphNode & { x?: number; y?: number; id?: string | number };
type RenderLink = GraphLink & { source?: string | number | RenderNode; target?: string | number | RenderNode };

// Cool topic palette — Index amber is reserved for search matches and active controls.
const TOPIC_COLORS = ['#4f9cff', '#34d399', '#a78bfa', '#f472b6', '#7dd3fc', '#facc15', '#fb7185'];
function topicColor(topic: string): string {
  let hash = 0;
  for (const ch of topic || 'untagged') hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return TOPIC_COLORS[hash % TOPIC_COLORS.length];
}

const DIM = 'rgba(140,148,160,0.28)';
const MATCH = '#d99a45';
const GRAPH_HEIGHT = 448;
const FIT_PADDING = 56;
const MOTION_MS = 450;

function topicKey(topic: string | null | undefined): string {
  return topic?.trim() || '';
}

function topicLabel(topic: string): string {
  return topic === '' ? 'Untagged' : topic;
}

const HTML_ESCAPE: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function escapeHtml(value: unknown): string {
  return String(value).replace(/[&<>"']/g, (char) => HTML_ESCAPE[char]);
}

function linkEndpointId(endpoint: unknown): string | undefined {
  if (endpoint == null) return undefined;
  return typeof endpoint === 'object' && 'id' in endpoint ? String(endpoint.id) : String(endpoint);
}

export function BrainGraph({ results, searchState }: { results: SearchResult[]; searchState: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const graphRef = useRef<ForceGraphMethods<GraphNode, GraphLink> | null>(null);
  const [width, setWidth] = useState(0);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [hiddenTopics, setHiddenTopics] = useState<Set<string>>(() => new Set());
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const reducedMotion = useReducedMotion();
  const transitionMs = reducedMotion ? 0 : MOTION_MS;

  useEffect(() => {
    let cancelled = false;
    fetch('/api/brain/graph')
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`Graph failed (${res.status})`))))
      .then((data: GraphPayload) => {
        if (!cancelled) {
          setGraph(data);
          setState('ready');
        }
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // react-force-graph mutates its data in place; hand it fresh objects and map edges -> links.
  const graphData = useMemo(
    () => ({
      nodes: graph.nodes.map((n) => ({ ...n })),
      links: graph.edges.map((e) => ({ source: e.source, target: e.target, score: e.score })),
    }),
    [graph],
  );

  const nodeTopics = useMemo(() => new Map(graph.nodes.map((node) => [node.id, topicKey(node.topic)])), [graph.nodes]);

  const topics = useMemo(
    () =>
      Array.from(new Set(graph.nodes.map((node) => topicKey(node.topic)))).sort((a, b) => topicLabel(a).localeCompare(topicLabel(b))),
    [graph.nodes],
  );

  const matchedIds = useMemo(() => new Set(results.map((r) => r.url)), [results]);
  const hasMatches = searchState === 'results' && matchedIds.size > 0;

  // Memoise the accessors handed to ForceGraph2D so their identity only changes when inputs do.
  const isNodeVisible = useCallback((node: RenderNode): boolean => !hiddenTopics.has(topicKey(node.topic)), [hiddenTopics]);
  const isLinkVisible = useCallback(
    (link: RenderLink): boolean => {
      const sourceTopic = nodeTopics.get(linkEndpointId(link.source) || '');
      const targetTopic = nodeTopics.get(linkEndpointId(link.target) || '');
      // Unknown endpoints (not in nodeTopics) stay visible rather than collapsing into Untagged.
      return (sourceTopic === undefined || !hiddenTopics.has(sourceTopic)) && (targetTopic === undefined || !hiddenTopics.has(targetTopic));
    },
    [nodeTopics, hiddenTopics],
  );
  const isVisibleMatch = useCallback(
    (node: RenderNode): boolean => isNodeVisible(node) && hasMatches && matchedIds.has(node.url),
    [isNodeVisible, hasMatches, matchedIds],
  );
  const visibleMatchCount = useMemo(
    () => graph.nodes.filter((node) => !hiddenTopics.has(topicKey(node.topic)) && matchedIds.has(node.url)).length,
    [graph.nodes, hiddenTopics, matchedIds],
  );
  const visibleTopicCount = useMemo(
    () => topics.filter((topic) => !hiddenTopics.has(topic)).length,
    [topics, hiddenTopics],
  );

  // Relationship count per node — how many edges (of any endpoint) touch it.
  // `graph.edges`' source/target are always plain node ids (the backend
  // response, untouched by ForceGraph2D's in-place object mutation of
  // `graphData.links`), so no `linkEndpointId` unwrapping is needed here.
  const relationshipCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const edge of graph.edges) {
      counts.set(edge.source, (counts.get(edge.source) ?? 0) + 1);
      counts.set(edge.target, (counts.get(edge.target) ?? 0) + 1);
    }
    return counts;
  }, [graph.edges]);

  // The keyboard/screen-reader-primary view of the same node set the canvas
  // draws (§3 accessibility handoff) — filtered by the same topic toggles,
  // and sorted match-first while a search is active so Tab reaches the
  // relevant rows first instead of an arbitrary graph-insertion order.
  const visibleNodes = useMemo(() => {
    const nodes = graph.nodes.filter(isNodeVisible);
    return [...nodes].sort((a, b) => {
      if (hasMatches) {
        const aMatch = matchedIds.has(a.url) ? 0 : 1;
        const bMatch = matchedIds.has(b.url) ? 0 : 1;
        if (aMatch !== bMatch) return aMatch - bMatch;
      }
      return a.title.localeCompare(b.title);
    });
  }, [graph.nodes, isNodeVisible, hasMatches, matchedIds]);

  // Identity tracks visibleMatchCount/transitionMs/isVisibleMatch, so the auto-focus effect re-runs
  // whenever the match set changes - even when its size stays the same.
  const zoomToVisibleMatches = useCallback(() => {
    if (!graphRef.current || visibleMatchCount === 0) return;
    graphRef.current.zoomToFit(transitionMs, FIT_PADDING, isVisibleMatch);
  }, [visibleMatchCount, transitionMs, isVisibleMatch]);

  useEffect(() => {
    if (!hasMatches || visibleMatchCount === 0) return;
    const handle = window.setTimeout(zoomToVisibleMatches, 0);
    return () => window.clearTimeout(handle);
  }, [hasMatches, visibleMatchCount, zoomToVisibleMatches]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setWidth(el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [state]);

  const zoomBy = (factor: number) => {
    const instance = graphRef.current;
    if (!instance) return;
    instance.zoom(instance.zoom() * factor, transitionMs);
  };

  const zoomToFit = () => graphRef.current?.zoomToFit(transitionMs, FIT_PADDING, isNodeVisible);
  const recenter = () => graphRef.current?.centerAt(0, 0, transitionMs);
  const toggleTopic = (topic: string) => {
    setHiddenTopics((current) => {
      const next = new Set(current);
      if (next.has(topic)) next.delete(topic);
      else next.add(topic);
      return next;
    });
  };

  const shell = 'hidden rounded-lg border border-line p-6 text-sm md:block';
  if (state === 'loading') return <div className={`${shell} bg-surface text-body`}>Loading Brain graph…</div>;
  if (state === 'error') return <div className={`${shell} bg-status-error-tint text-status-error`}>Could not load Brain graph.</div>;
  if (graph.nodes.length === 0) return <div className={`${shell} bg-surface text-body`}>No Brain nodes yet.</div>;

  return (
    <section className="hidden rounded-lg border border-line bg-canvas p-4 md:block" aria-label="Brain graph map">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Brain map</h2>
          <p className="text-xs text-body">Semantic links grouped by topic. Search matches are highlighted in Index amber.</p>
        </div>
        <span className="font-mono text-xs text-muted tabular-nums">
          {graph.nodes.length} nodes · {graph.edges.length} edges
        </span>
      </div>
      <div ref={containerRef} className="relative h-[28rem] w-full overflow-hidden rounded-md bg-surface">
        <div className="pointer-events-none absolute inset-x-3 top-3 z-10 flex items-start justify-between gap-3">
          <div className="pointer-events-auto flex overflow-hidden rounded-lg bg-canvas/90 p-1 shadow-overlay ring-1 ring-line backdrop-blur">
            <GraphControl label="Zoom in" onClick={() => zoomBy(1.35)}>+</GraphControl>
            <GraphControl label="Zoom out" onClick={() => zoomBy(1 / 1.35)}>−</GraphControl>
            <GraphControl label="Fit visible graph" onClick={zoomToFit}>Fit</GraphControl>
            <GraphControl label="Recenter graph" onClick={recenter}>Center</GraphControl>
            <GraphControl label="Focus visible search matches" onClick={zoomToVisibleMatches} disabled={visibleMatchCount === 0}>
              Match
            </GraphControl>
          </div>
          <div className="pointer-events-auto max-w-[22rem] rounded-lg bg-canvas/90 p-3 shadow-overlay ring-1 ring-line backdrop-blur">
            <div className="mb-2 flex items-center justify-between gap-3">
              <span className="text-xs font-medium text-ink">Topics</span>
              <span className="font-mono text-label text-muted tabular-nums">{visibleTopicCount}/{topics.length}</span>
            </div>
            <div role="group" aria-label="Topics" className="flex max-h-28 flex-wrap gap-1.5 overflow-y-auto pr-1">
              {topics.map((topic) => {
                const hidden = hiddenTopics.has(topic);
                return (
                  <button
                    key={topic}
                    type="button"
                    onClick={() => toggleTopic(topic)}
                    aria-pressed={!hidden}
                    className={`inline-flex min-h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium ring-1 transition-[background-color,color,opacity,transform] duration-150 active:scale-[0.96] motion-reduce:transition-none motion-reduce:active:scale-100 ${
                      hidden
                        ? 'bg-transparent text-body ring-line hover:bg-raised hover:text-ink'
                        : 'bg-raised text-ink ring-line-strong hover:bg-line'
                    }`}
                  >
                    <span className={`h-2.5 w-2.5 rounded-full ${hidden ? 'opacity-40' : ''}`} style={{ backgroundColor: topicColor(topic) }} aria-hidden="true" />
                    {topicLabel(topic)}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        {/* The canvas itself has no keyboard/non-visual equivalent of its own —
            aria-hide it and let BrainNodeList below be the accessible
            representation of this same data (§3 accessibility handoff). The
            zoom/topic controls above are real buttons and stay outside this
            wrapper; they're already keyboard/screen-reader operable. */}
        <div aria-hidden="true">
          <ForceGraph2D
            ref={graphRef}
            graphData={graphData}
            width={width || undefined}
            height={GRAPH_HEIGHT}
            backgroundColor="rgba(0,0,0,0)"
            nodeRelSize={4}
            nodeVal={(n: RenderNode) => Math.max(1, n.seen_count || 1)}
            nodeLabel={(n: RenderNode) => `${escapeHtml(n.title)}${n.stars != null ? ` · ★${escapeHtml(n.stars)}` : ''}`}
            nodeVisibility={isNodeVisible}
            nodeColor={(n: RenderNode) => (hasMatches ? (matchedIds.has(n.url) ? MATCH : DIM) : topicColor(topicKey(n.topic)))}
            linkVisibility={isLinkVisible}
            linkColor={() => 'rgba(140,148,160,0.20)'}
            linkWidth={(l: RenderLink) => Math.max(0.5, (l.score || 0) * 2)}
            warmupTicks={20}
            cooldownTicks={120}
          />
        </div>
      </div>
      <BrainNodeList
        nodes={visibleNodes}
        relationshipCounts={relationshipCounts}
        matchedIds={matchedIds}
        hasMatches={hasMatches}
      />
    </section>
  );
}

/** The primary keyboard/screen-reader representation of the Brain graph — not
 * a degraded fallback (§3 accessibility handoff). Every node the canvas draws
 * (after the same topic-visibility filter) is a real, Tab-reachable link
 * here, so a keyboard-only or screen-reader user reaches everything a mouse
 * user can pan/zoom to find, without depending on the canvas at all. */
function BrainNodeList({
  nodes,
  relationshipCounts,
  matchedIds,
  hasMatches,
}: {
  nodes: GraphNode[];
  relationshipCounts: Map<string, number>;
  matchedIds: Set<string>;
  hasMatches: boolean;
}) {
  return (
    <div className="mt-3 max-h-64 overflow-auto rounded-md border border-line">
      <table className="min-w-full divide-y divide-line text-left text-sm">
        <caption className="sr-only">
          Brain nodes, as a keyboard- and screen-reader-accessible
          alternative to the graph map above.
        </caption>
        <thead className="sticky top-0 bg-raised text-xs text-muted">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">Title</th>
            <th scope="col" className="px-3 py-2 font-medium">Topic</th>
            <th scope="col" className="px-3 py-2 font-medium">Relationships</th>
            {hasMatches && <th scope="col" className="px-3 py-2 font-medium">Match</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {nodes.map((node) => {
            const href = safeUrl(node.url);
            const matched = hasMatches && matchedIds.has(node.url);
            return (
              <tr key={node.id}>
                <td className="px-3 py-2">
                  {href ? (
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-ink underline-offset-2 hover:text-signal hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-bright"
                    >
                      {node.title}
                    </a>
                  ) : (
                    <span className="text-muted">{node.title}</span>
                  )}
                </td>
                <td className="px-3 py-2 text-body">{topicLabel(topicKey(node.topic))}</td>
                <td className="px-3 py-2 font-mono text-xs tabular-nums text-muted">
                  {relationshipCounts.get(node.id) ?? 0}
                </td>
                {hasMatches && (
                  <td className="px-3 py-2">
                    {matched && (
                      <span className="rounded border border-line px-1.5 py-0.5 text-mono-label font-medium text-signal">
                        Match
                      </span>
                    )}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function GraphControl({
  label,
  children,
  onClick,
  disabled = false,
}: {
  label: string;
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      className="min-h-10 min-w-10 rounded-md bg-transparent px-3 text-xs font-medium text-body ring-1 ring-transparent transition-[background-color,color,opacity,transform] duration-150 hover:bg-raised hover:text-ink active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40 motion-reduce:transition-none motion-reduce:active:scale-100"
    >
      {children}
    </button>
  );
}
