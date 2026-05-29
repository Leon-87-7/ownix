## What to build

Add **Second Brain ingest** for the repo pipeline. The repo URL itself (and only the repo URL — README body hyperlinks are deliberately ignored) gets embedded into the `links` table and uploaded as an Obsidian-shaped markdown to Google Drive, fire-and-forget after the user-facing response ships.

Behavior:

- `processors.repo.run` calls `brain.ingest_links([repo_url], topic=analysis["tagline"], source_job_id=job.id)` after the Telegram document + summary message have shipped. Wrapped in `asyncio.create_task(...)` per invariant #3.
- The single URL ingested is the **normalized** repo URL (`github.com/<owner>/<repo>`, no subpath, no query string, no fragment).
- README body hyperlinks are **NOT** ingested (mirror article's decision #19; repo body links are noise — badges, doc sites, related projects). Document this in code with a comment pointing to ADR / spec rationale.
- `/find <query>` (existing semantic search) should surface the repo automatically once the brain ingest completes; verify with a manual `/find <tagline-keyword>` after a job lands.
- The existing `enrich_github_links` path inside `/find` already enriches `github.com` results with metadata. After this slice, repos that were analyzed via the repo pipeline appear in `/find` results with both the existing metadata enrichment AND the cached `topic=tagline` from the brain row. No change to `/find` rendering in this slice — that's noted as a future enhancement in the spec.

Reference spec: **§Design Decisions** (#19), **§Architecture → Data flow** (brain ingest line).

## Acceptance criteria

- [ ] `processors.repo.run` calls `brain.ingest_links([repo_url], topic=tagline, source_job_id=job.id)` after Telegram delivery.
- [ ] The call is wrapped in `asyncio.create_task(...)` — `run` returns before brain ingest completes (verify with a slow mock).
- [ ] The URL passed to `ingest_links` is the normalized repo URL, not the user's original paste (test with a `/blob/main/README.md` paste — the brain receives the root URL).
- [ ] README body hyperlinks are NOT extracted or ingested (test: ingest the analysis for a repo whose README contains 20+ external hyperlinks; only one row appears in `links` for that job).
- [ ] A brain-ingest failure logs a warning but leaves `jobs.status='done'` unchanged.
- [ ] Manual demo step: paste a real repo URL, wait for analysis, then run `/find <tagline-keyword>` — the repo appears in results within a minute (subject to embedding latency).
- [ ] Tests: one URL ingested; topic equals tagline; source_job_id equals job.id; fire-and-forget contract.
- [ ] No regression in `/find` rendering or existing brain ingest paths.

## Blocked by

- #68 — needs the `repo_analysis` JSON for the `tagline` topic.
