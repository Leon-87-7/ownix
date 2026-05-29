## What to build

Handle three real-world failure / degradation modes for the repo pipeline:

1. **Archived repos** — run analysis with a warning prepended.
2. **No README** — degrade the prompt gracefully and warn.
3. **GitHub API failures** — distinct user-visible error per failure mode (404 / 403+rate-limit / 5xx + network).

Behavior:

### Archived

- `bundle["metadata"]["archived"] == True` triggers a warning line prepended to both the summary message and the markdown document:
  - Summary: `⚠️ Archived — no longer maintained` line above the header card.
  - Document: `## ⚠️ Archived — no longer maintained` H2 below the title.
- `archived=True` is written to the `Repo Analysis` Sheets row (column 12).
- Gemini still runs — analysis quality is preserved, the warning is purely informational.

### No README

- `services.github.fetch_readme` returns `None` (404 from `/repos/{o}/{r}/readme`).
- `bundle["no_readme"] = True` is set; `bundle["readme"] = ""`.
- `_build_repo_prompt` (from #68) receives `flags={"no_readme": True}` and adjusts to instruct Gemini to lean on tree + manifests for the analysis.
- Summary message and document include the `ℹ️ No README detected — analysis is shallower than usual` line/heading.
- Sheets row still appended; brain ingest still fires. The job is a success, just shallower.

### GitHub API failures

- The metadata call is the first GitHub call and gates the rest. If it fails:
  - **404** (`Repo not found or private — check the URL.`)
  - **403** with rate-limit headers (`X-RateLimit-Remaining: 0`): `GitHub API limit hit, try again in an hour.`
  - **403** without rate-limit headers, or **401**: `GitHub authentication failed — check GITHUB_TOKEN.` (log-only severity; this is operator misconfiguration, not user error — but user still needs feedback).
  - **5xx** or `httpx.NetworkError` / timeout: `GitHub unavailable, retry.`
- Failure path: job → `status='error'`, no `template_analysis`, no Sheets row, no brain ingest, no Telegram document. Single error message sent to chat with the case-appropriate copy.
- README, tree, manifest fetch failures **inside** a partial-success bundle (rare but possible) do NOT abort the pipeline. Missing README triggers the no-README path above. Missing tree → empty list. Missing manifest → skip silently.
- The `gemini.GeminiUnavailableError` (from ADR-0011) is a separate failure mode — already handled by `_call_with_fallback`; surface as `Gemini unavailable, try /force later.` (mirror existing enrichment pattern).

Reference spec: **§Design Decisions** (#21, #22, #23), **§Architecture → Data flow** (error path).

## Acceptance criteria

### Archived
- [ ] An archived-flag bundle produces a summary message starting with `⚠️ Archived — no longer maintained`.
- [ ] The markdown document includes the H2 `## ⚠️ Archived — no longer maintained`.
- [ ] The `archived` column in the Sheets row is `TRUE` for archived repos and `FALSE` otherwise.
- [ ] Test: synthetic bundle with `metadata.archived=True` → both warning surfaces appear; without it → neither appears.

### No README
- [ ] `services.github.fetch_readme` 404 returns `None` without raising.
- [ ] `fetch_repo_bundle` sets `no_readme=True` and `readme=""` on `fetch_readme` returning `None`.
- [ ] `_build_repo_prompt(bundle, flags={"no_readme": True})` produces a different prompt (asserts a specific instructional sentence is present).
- [ ] Summary message and document show the `ℹ️ No README detected …` line/heading.
- [ ] Pipeline still completes successfully, Sheets row appended, brain ingest fires.
- [ ] Test: bundle with empty README → full success path with shallow-analysis warning.

### GitHub API failures
- [ ] 404 on metadata → user receives `Repo not found or private — check the URL.`; `jobs.status='error'`; no Sheets row; no document.
- [ ] 403 with `X-RateLimit-Remaining: 0` → user receives `GitHub API limit hit, try again in an hour.`
- [ ] 5xx / network / timeout → user receives `GitHub unavailable, retry.`
- [ ] 401 / 403 without rate-limit headers → user receives `GitHub authentication failed — check GITHUB_TOKEN.` AND a warning logs to structlog.
- [ ] README / tree / manifest fetch failures inside an otherwise-successful bundle do NOT abort the pipeline. (Test with mocked transport returning 404 for the README but 200 for everything else → no-README path engages.)
- [ ] `GeminiUnavailableError` surfaces as `Gemini unavailable, try /force later.`
- [ ] Tests: one per failure mode against a mocked HTTP transport.
- [ ] Job rows for failed paths have `status='error'` and no `template_analysis`.

## Blocked by

- #68 — needs the prompt / Gemini call surface to integrate the `no_readme` flag and the metadata call to gate failures off of.
