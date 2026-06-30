---
adr: "0027"
title: Brain node lifecycle — normalized-URL dedup and metadata-only repo refresh
status: accepted
date: 2026-06-21
---

## Context

The [[Second Brain]] keys each node by URL, but `brain.ingest_links` deduped on the *exact* URL string, so tracking-param/trailing-slash twins (`?v=X&t=10` vs `?v=X`) slipped past and cluttered the [[Brain graph]] as duplicate nodes. Separately, the only nodes whose underlying subject changes over time are GitHub repos (stars, last-push), yet a brain repo node stores none of that — it holds only `url`, a Gemini-guessed `title`, `topic`, and an embedding. The rich repo data lives on the `jobs` row, Drive `.md`, Sheets, and the live GitHub bundle, never on the node.

## Decision

**Dedup on a normalized URL.** Strip query, fragment, and trailing slash before the existing `WHERE url = ?` lookup in `brain.ingest_links`. A re-sighting bumps `seen_count`; it never creates a second node. Re-occurrence is **not** time-windowed — there is no "spawn a fresh node after N days." A 14-day clock was explicitly rejected for node identity (see Consequences).

**Repo nodes refresh metadata only.** Add `stars` and `pushed_at` columns to `links`. A scheduled job re-fetches GitHub metadata (reusing `fetch_repo_bundle` + `GITHUB_TOKEN`) for `github.com` nodes older than 14 days that are **not archived**. No Gemini re-analysis — the tagline/title/embedding are left untouched.

## Considered Options

- **Time-windowed node splitting** (same URL >14 days apart → a new node): rejected. It breaks the one-node-per-URL invariant the Drive sync depends on (`{slugify(title)}.md` would collide for two nodes sharing a URL/title).
- **Full repo re-analysis every 14 days** (re-fetch bundle + re-run Gemini): rejected as default. Real Gemini spend per repo on a timer, to refresh a title that is a generic guess. Reserved for a future ADR if the *semantic* node must track repo evolution.

## Consequences

- One-node-per-normalized-URL becomes a load-bearing invariant (CONTEXT.md Key Invariant #13) — the Drive slug uniqueness rests on it.
- `links` gains `stars` / `pushed_at`; the [[Brain graph]] node payload can surface "★1.2k · pushed 3d ago" for repo nodes without a live GitHub call at render time.
- The refresh job is a separate backend concern from graph rendering and ships independently; archived repos are skipped to avoid pointless API spend.
