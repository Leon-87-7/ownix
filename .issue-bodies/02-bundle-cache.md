## What to build

Replace the stub processor from #66 with a real **bundle fetch** of GitHub content — README, recursive file tree, and detected package manifests — combined with the existing metadata call. The bundle lands in a new Redis cache key with a 7-day TTL, README content is preprocessed (badges + inline HTML stripped, truncated to 50 KB silently), and `/force <repo-url>` is extended to invalidate both the new bundle cache and the existing 24h `github_meta:` key.

Behavior:

- `src/services/github.py` grows four sibling functions next to `enrich_repo`:
  - `fetch_readme(owner, repo, token) -> str | None` — calls `GET /repos/{owner}/{repo}/readme`, base64-decodes the content. Returns `None` on 404.
  - `fetch_tree(owner, repo, branch, token) -> list[str]` — calls `GET /repos/{owner}/{repo}/git/trees/{branch}?recursive=1`. Returns list of path strings.
  - `fetch_manifest(owner, repo, path, token) -> str | None` — calls `GET /repos/{owner}/{repo}/contents/{path}`, base64-decodes.
  - `fetch_repo_bundle(owner, repo, token) -> dict` — orchestrates: metadata first (provides `default_branch`), then `asyncio.gather` README + tree + each manifest detected in the tree. Returns the bundle JSON shape in spec **§Bundle JSON shape**.
- README preprocessing helper `preprocess_readme(raw: str) -> str` (spec **§README preprocessing pseudocode**): strip badge-only lines (`^\s*[\[!].*\]\(.*\)\s*$`), drop inline HTML blocks (`<details>`, `<picture>`, `<img>`, `<table>`, `<sub>`, `<sup>`, `<kbd>`, `<p>` and the matching self-closing tags), truncate at 50,000 chars silently.
- Manifest scanner: any of `pyproject.toml`, `setup.py`, `setup.cfg`, `requirements.txt`, `package.json`, `pnpm-lock.yaml`, `go.mod`, `Cargo.toml`, `Gemfile`, `composer.json`, `build.gradle`, `build.gradle.kts`, `pom.xml`, `Dockerfile` at depth ≤ 2 in the tree gets fetched.
- Redis cache: key `github_repo_bundle:{owner}/{repo}`, value is the full bundle JSON, TTL `86400 * 7` (7 days). Read before any GitHub call; write after a successful cold-cache assembly. Errors during cache read/write log and continue (mirror `enrich_repo` pattern).
- `processors/repo.py.run` now calls `fetch_repo_bundle`, then upgrades the stub Telegram message to include bundle stats:

  ```
  📦 {owner}/{repo}
  ⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {N days ago}

  📄 README: {bytes_after_preprocess} bytes ({original_kb} KB raw)
  🗂  Tree: {N} files
  📦 Manifests: {comma-joined list, or "none"}

  🚧 Gemini analysis lands in the next slice (#TODO-3).

  🔗 {repo_url}
  ```

- `/force <repo-url>` in `webhook.py`: after the existing `jobs`-row reset path, also `DEL github_repo_bundle:{owner}/{repo}` AND `DEL github_meta:{owner}/{repo}`. Single command, both caches cleared.
- Job is still marked `status='done'` after the upgraded stub. No Sheets / Drive / brain / Gemini yet.

Reference spec: **§Design Decisions** (#7, #8, #9, #12, #13), **§Architecture → Bundle JSON shape**, **§Architecture → Manifest detection**, **§README preprocessing pseudocode**, **§Build Order Phase 3**, [ADR-0014](docs/adr/0014-github-rest-not-jina-for-repos.md).

## Acceptance criteria

- [ ] `services.github.fetch_readme` returns the README content for a public repo, `None` on 404 (test fixture: a repo known to have a README + a repo deliberately constructed with `.gitignore` only).
- [ ] `services.github.fetch_tree` returns a flat list of paths from a recursive tree call (test against `anthropics/claude-code` or a fixture).
- [ ] `services.github.fetch_manifest` returns base64-decoded content for a known path; `None` on 404.
- [ ] `services.github.fetch_repo_bundle` returns the spec'd dict shape with all keys populated (and empty fallbacks where appropriate) for a public repo.
- [ ] `services.github.preprocess_readme` strips badge-only lines, drops the listed inline HTML tags, and truncates at exactly 50,000 chars. Unit tests cover each rule independently.
- [ ] Redis key `github_repo_bundle:{owner}/{repo}` is written on cold-cache fetch with TTL 7 days (verify via `TTL` command or test double).
- [ ] Cache hit path: a second invocation of `fetch_repo_bundle` for the same owner/repo returns the cached blob without any GitHub HTTP call (test with a mocked transport that asserts zero requests on hit).
- [ ] `processors.repo.run` produces the upgraded stub message containing the four bundle-stat lines.
- [ ] `/force <repo-url>` deletes both Redis cache keys (verify with `EXISTS` before/after) and still performs the existing jobs-row reset.
- [ ] Manifest detection picks up at least three of: `pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml` from a fixture tree.
- [ ] Integration test or PR manual-demo step: paste a real repo URL, see the upgraded stub message; paste again, observe cache-hit logs; run `/force <url>`, paste again, observe cold-cache fetch logs.

## Blocked by

- #66 — needs the routing + processor skeleton in place.
