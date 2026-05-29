## What to build

Add the **repo pipeline** routing skeleton end-to-end so a GitHub repo URL pasted in chat creates a `content_type='repo'` job, dispatches to a new `processors/repo.py` module, and returns a stub card (no Gemini analysis yet). This is the tracer-bullet that proves the worker dispatch + routing + Telegram delivery path before any heavy work lands.

Behavior:

- `validators.detect_pipeline` returns `"repo"` for `github.com/<owner>/<repo>[/...]` URLs.
- Subpaths (`/blob/...`, `/tree/...`, `/issues/...`, `/wiki/...`, `/pulls/...`) normalize to `github.com/<owner>/<repo>` for the job's stored URL and dedup key.
- Reserved-path blocklist rejects `/features`, `/pricing`, `/marketplace`, `/sponsors`, `/topics`, `/explore`, `/settings`, `/notifications`, `/codespaces`, `/login`, `/signup`, `/apps`, `/orgs`, `/about`, `/security`, `/trending`, `/readme` — first segment of the path checked case-insensitively.
- Gists (`gist.github.com`) reject. Enterprise hosts (`github.<company>.com`) reject. Org-only URLs (`github.com/<owner>` with no second segment) reject.
- Worker dispatch table gains `"repo"` → `repo.run`.
- `processors/repo.py` exists with `run(job)` that fetches metadata via the existing `services/github.enrich_repo`, then sends a stub Telegram message:

  ```
  📦 {owner}/{repo}
  ⭐ {stars:,} | 🔀 {forks:,} | 💻 {language} | 📅 {N days ago}

  🚧 Full analysis coming soon — this is a placeholder while the repo pipeline rolls out.

  🔗 {repo_url}
  ```

- Job is marked `status='done'` after the stub message ships. No Sheets row, no Drive, no brain ingest yet (those land in later slices).
- The existing webhook "URL not supported" rejection message gets a repo-aware hint when the URL is `github.com` but failed routing: `If you meant a repository, the URL should look like https://github.com/<owner>/<repo>.`

Reference spec: [`docs/features/postgrill/repo-url-feature.md`](docs/features/postgrill/repo-url-feature.md) sections **§Design Decisions** (#1, #2, #6, #25, #26), **§Architecture → Reserved-path blocklist**, **§Build Order Phase 1, 5, 6, 7**.

## Acceptance criteria

- [ ] `validators.detect_pipeline("https://github.com/anthropics/claude-code")` returns `"repo"`.
- [ ] `validators.detect_pipeline("https://github.com/anthropics/claude-code/blob/main/README.md")` returns `"repo"`.
- [ ] `validators.detect_pipeline("https://github.com/anthropics")` returns `"rejected"`.
- [ ] `validators.detect_pipeline("https://github.com/pricing")` returns `"rejected"`.
- [ ] `validators.detect_pipeline("https://gist.github.com/anyone/abc123")` returns `"rejected"`.
- [ ] Subpath URLs normalize to `github.com/<owner>/<repo>` form when written to `jobs.url` (new `normalize_repo_url` helper or inline in `create_job`).
- [ ] Worker `_DISPATCH` table includes `"repo": repo.run` and dispatches correctly when a `{"task":"repo","job_id":...}` envelope is pushed.
- [ ] `processors/repo.py` exists with a `run(job)` coroutine; it calls `services.github.enrich_repo`, formats the stub message, sends via `telegram.sender.send_message`, and marks the job `status='done'`.
- [ ] Rejected `github.com` URLs (orgs, gists, reserved paths) produce a rejection message that ends with the repo-aware hint.
- [ ] Unit tests cover the routing matrix (each of the rows above) and the stub-message formatter.
- [ ] Integration test (or manual demo step in the PR description) confirms a real Telegram message lands after enqueuing a `{"task":"repo"}` envelope against a fixture job row.
- [ ] CONTEXT.md glossary additions (`Repo pipeline`, `Repo URL`, `GitHub reserved-path blocklist`) already merged via the grilling session do not need re-editing — verify the entries match what shipped.

## Blocked by

None — can start immediately.
