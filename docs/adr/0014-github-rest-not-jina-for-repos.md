---
adr: "0014"
title: Fetch repo content via GitHub REST API, not Jina Reader
status: accepted
date: 2026-05-29
---

## Context

The [article pipeline](../features/postgrill/article-url-feature.md) uses
[Jina Reader](https://r.jina.ai/) to fetch arbitrary URLs as clean markdown.
When designing the [repo pipeline](../features/postgrill/repo-url-feature.md)
the natural question was: should we use the same Jina passthrough for repo
content (README, file tree, manifests), or fetch via GitHub's REST API?

The two options differ on more than just transport:

| | GitHub REST API | Jina at `r.jina.ai/github.com/<o>/<r>` |
|---|---|---|
| Source | Raw `.md` file content (base64) | Rendered GitHub page → HTML → markdown extraction |
| Already markdown? | Yes — it IS the markdown source | No — round-tripped through HTML |
| Size on huge READMEs | ≈ file size | Similar or **larger** (adds GitHub page chrome — repo header, About box, file tree sidebar, topic chips) |
| File tree access | Native (`/git/trees?recursive=1`) | Not exposed — would require multiple Jina fetches per subfolder |
| Manifest file access | Native (`/contents/{path}`) | Would require per-file Jina fetches via `raw.githubusercontent.com`, no batching |
| Auth | `GITHUB_TOKEN` (already configured for the photo-pipeline repo enrichment) | `JINA_API_KEY` (optional, shared with article pipeline) |
| Rate limit | 5,000 req/hour authenticated | Free tier quota — shared with article workload |
| Reliability | GitHub status page; well-known SLAs | Jina is a small service with no SLA (already a known risk in article pipeline) |

The Jina route was tempting on the surface ("same transport as article →
fewer moving parts") but a closer look at what we actually need from a
repo — README + recursive tree + N manifest files — makes the GitHub REST
API a clean fit and Jina an awkward indirection.

## Decision

The repo pipeline fetches all GitHub content directly via the **GitHub REST
API** using the existing `GITHUB_TOKEN`. Jina Reader is not used for any
repo-pipeline path.

Specifically:

- **Metadata** — `GET /repos/{owner}/{repo}` (reuses the existing
  `enrich_repo` function in `src/services/github.py`)
- **README** — `GET /repos/{owner}/{repo}/readme` (auto-resolves
  `README.md` / `README.rst` / `readme.txt` / etc., returns base64-decoded
  content)
- **File tree** — `GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1`
- **Manifest files** — `GET /repos/{owner}/{repo}/contents/{path}` per
  detected manifest

All four fetches run concurrently via `asyncio.gather` after the metadata
call (which provides the `default_branch` needed for the tree call). The
combined bundle is cached in Redis under `github_repo_bundle:{owner}/{repo}`
with TTL 7 days.

## Consequences

- **Pro:** Per-call sizes are smaller — no GitHub page chrome bloating the
  README.
- **Pro:** Native file tree and per-file fetches; Jina has no equivalent.
- **Pro:** Rate budget (5,000/hour) is generous for vig's single-user
  scale; the existing photo-pipeline repo enrichment already shares this
  budget without strain.
- **Pro:** Failure modes map cleanly to user-visible messages (404 / 403 /
  5xx → distinct error copy).
- **Con:** Article and repo pipelines now use different content-fetch
  services. Two external dependencies instead of one. Acceptable — the
  domains they serve are structurally different (arbitrary web pages vs.
  one well-known platform).
- **Con:** The repo pipeline is GitHub-specific by construction. A future
  GitLab or Bitbucket pipeline would need its own service module, not a
  Jina passthrough.

## Considered Alternatives

- **Jina passthrough for everything** — Rejected for the size/chrome and
  no-tree reasons above.
- **Hybrid: Jina for README, GitHub REST for tree + manifests** —
  Worst of both worlds (two services, two failure modes, no upside).
- **`raw.githubusercontent.com` direct file fetches without Jina** —
  Possible for README + manifests but loses the API's `default_branch`
  resolution, README-name auto-detection, and base64 envelope.
  Unauthenticated rate limits are also tighter (60/hour).
