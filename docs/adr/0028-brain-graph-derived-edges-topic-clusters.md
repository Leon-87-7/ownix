---
adr: "0028"
title: Brain graph — derived edges, topic clusters, 2D desktop / ego-network mobile
status: accepted
date: 2026-06-21
---

## Context

The Brain page is a semantic search list; we want to visualize the [[Second Brain]] as a graph of nodes and clusters, with search highlighting matching nodes. But the data model has **no edges table and no clusters** — "related" links are computed on the fly (top-k cosine) only to write Obsidian `.md`, then discarded. Embeddings are 768-dim. A naive design would add an edges table, a clustering pass (k-means / community detection), and a dimensionality-reduction step (UMAP/t-SNE) to place nodes — three new subsystems for a small in-memory corpus.

## Decision

- **Edges are derived, not stored.** `GET /api/brain/graph` returns `{ nodes, edges }` where edges are top-k cosine neighbors (≥ `BRAIN_MIN_SCORE`), reusing `brain._compute_related` across the whole corpus. No edges table.
- **Clusters are topics, not an algorithm.** A node's `topic` *is* its cluster, expressed as node color. Same-topic nodes pull together under the force layout. No clustering algorithm, no dimensionality reduction — the force simulation positions nodes from the edges.
- **2D on desktop, ego-network on mobile.** Desktop renders `react-force-graph` `ForceGraph2D` (color by topic, size by `seen_count`); mobile renders a tap-to-expand ego-network (one node + its neighbors) from the same payload. 3D was rejected: it reads worse (occlusion, unfindable highlights, orbit-vs-scroll conflict on touch) and is one import away if ever wanted.
- **Search highlight needs no API change.** Graph nodes carry the unique `url`, so the frontend matches existing `/api/brain/search` results by `url`, builds a `Set` of matched ids, and repaints them (`nodeColor` / `nodeCanvasObjectMode`) + `zoomToFit`.

## Consequences

- `react-force-graph` is added to `web/` (cached in opensrc at `github.com/vasturiano/react-force-graph/1.48.2`); the React bindings are thin — canvas/layout internals live in the separate `vasturiano/force-graph` repo.
- The graph reflects whatever `topic` values ingestion produced; if topics stop being meaningful groupings, real community detection becomes a future ADR — until then it is deliberately absent.
- No backfill or schema change is needed for rendering; the endpoint reads existing `links` + embeddings.
