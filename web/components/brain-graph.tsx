'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import dynamic from 'next/dynamic';

// react-force-graph touches `window` at import time — load it client-only (ADR-0028).
const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), { ssr: false });

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

// Cool topic palette — signal orange (#f6921e) is reserved for search matches.
const TOPIC_COLORS = ['#4f9cff', '#34d399', '#a78bfa', '#f472b6', '#7dd3fc', '#facc15', '#fb7185'];
function topicColor(topic: string): string {
  let hash = 0;
  for (const ch of topic || 'untagged') hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return TOPIC_COLORS[hash % TOPIC_COLORS.length];
}

const DIM = 'rgba(140,148,160,0.28)';
const MATCH = '#f6921e';

export function BrainGraph({ results, searchState }: { results: SearchResult[]; searchState: string }) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [width, setWidth] = useState(0);
  const [graph, setGraph] = useState<GraphPayload>({ nodes: [], edges: [] });
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

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

  const matchedIds = useMemo(() => new Set(results.map((r) => r.url)), [results]);
  const hasMatches = searchState === 'results' && matchedIds.size > 0;

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const measure = () => setWidth(el.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, [state]);

  const shell = 'hidden rounded-lg border border-line p-6 text-sm md:block';
  if (state === 'loading') return <div className={`${shell} bg-surface text-body`}>Loading Brain graph…</div>;
  if (state === 'error') return <div className={`${shell} bg-status-error-tint text-status-error`}>Could not load Brain graph.</div>;
  if (graph.nodes.length === 0) return <div className={`${shell} bg-surface text-body`}>No Brain nodes yet.</div>;

  return (
    <section className="hidden rounded-lg border border-line bg-canvas p-4 md:block" aria-label="Brain graph map">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-ink">Brain map</h2>
          <p className="text-xs text-body">Semantic links grouped by topic. Search matches are highlighted in signal orange.</p>
        </div>
        <span className="font-mono text-xs text-muted">
          {graph.nodes.length} nodes · {graph.edges.length} edges
        </span>
      </div>
      <div ref={containerRef} className="h-[28rem] w-full overflow-hidden rounded-md bg-surface">
        <ForceGraph2D
          graphData={graphData}
          width={width || undefined}
          height={448}
          backgroundColor="rgba(0,0,0,0)"
          nodeRelSize={4}
          nodeVal={(n) => Math.max(1, n.seen_count || 1)}
          nodeLabel={(n) => `${n.title}${n.stars != null ? ` · ★${n.stars}` : ''}`}
          nodeColor={(n) => (hasMatches ? (matchedIds.has(n.id as string) ? MATCH : DIM) : topicColor(n.topic))}
          linkColor={() => 'rgba(140,148,160,0.20)'}
          linkWidth={(l) => Math.max(0.5, (l.score || 0) * 2)}
          warmupTicks={20}
          cooldownTicks={120}
        />
      </div>
    </section>
  );
}
