## What to build

Wire the existing `/freestyle <url>` slash command + `✍️ Freestyle` inline button (from #68) end-to-end for the repo pipeline. A freestyle re-run reuses the cached `github_repo_bundle:` (no second GitHub fetch), substitutes the user's prompt into `_build_repo_prompt`, regenerates the analysis, ships a fresh document + summary message, and updates the existing `Repo Analysis` Sheets row in place via `update_repo_row` (from #70).

Behavior:

- `/freestyle <repo-url>` (existing slash command, no changes to its handler) arms `chat_state(awaiting_freestyle, job_id)` for the matching job. The freestyle handler already accepts any `detect_pipeline`-valid URL, so `repo` URLs work transparently.
- The Freestyle button on the summary message (added in #68) wires to the same `awaiting_freestyle` state machine — already supported by the existing callback table.
- User types the prompt within the 10-minute window → `webhook` writes `jobs.freestyle_prompt` and re-enqueues `{"task":"repo","job_id":<same-id>}`.
- `processors.repo.run` detects `job.freestyle_prompt` and:
  - Reads `github_repo_bundle:` from Redis (cache hit; no GitHub fetch).
  - Passes `freestyle_prompt=job.freestyle_prompt` to `_build_repo_prompt`.
  - Calls Gemini, gets a fresh `repo_analysis` JSON.
  - Renders a fresh markdown document, sends via `send_document` (filename unchanged).
  - Sends a fresh summary message with the new analysis + Freestyle button.
  - Calls `sheets.update_repo_row` (NOT `append_repo_row`) — keyed by `jobs.sheets_row_id` from the original run.
  - Fires brain ingest again — the URL is the same, so `brain.ingest_links` upserts (or no-ops, depending on existing semantics; verify behavior).
- The same `job_id` is preserved across re-runs (consistent with article's #18). One repo URL → one Sheets row, regardless of how many freestyle re-runs land on it.

Reference spec: **§Design Decisions** (#14, #18), **§Architecture → Data flow** (freestyle re-run block).

## Acceptance criteria

- [ ] `/freestyle <repo-url>` recognized by `detect_pipeline` as a repo URL and routes through the existing slash handler (no handler-code changes required — verify with an integration test).
- [ ] The Freestyle button on the summary message triggers `awaiting_freestyle` for the correct `job_id`.
- [ ] After the user types a prompt, `jobs.freestyle_prompt` is set, `chat_state` is cleared, and `{"task":"repo","job_id":<same-id>}` is enqueued.
- [ ] `processors.repo.run` cache-hits `github_repo_bundle:` on a re-run (assert zero GitHub HTTP calls in a test).
- [ ] `_build_repo_prompt` is called with `freestyle_prompt=job.freestyle_prompt` and the resulting prompt contains the user's text verbatim.
- [ ] Fresh document + summary message land in chat after the re-run completes.
- [ ] `sheets.update_repo_row` is invoked (NOT `append_repo_row`) on the re-run; the Sheets tab's row count stays constant.
- [ ] `job_id` is unchanged across the original run and any number of freestyle re-runs.
- [ ] If the user pastes `/freestyle <repo-url>` for a URL that has no existing `jobs` row, the system creates a fresh job and runs through `repo.run` normally (the freestyle_prompt is set during the first run, not as a re-run) — mirror the existing freestyle-on-fresh-URL pattern from article and video pipelines.
- [ ] Tests: freestyle re-run path (full mock); cache hit on re-run; update vs append routing; job_id stability.
- [ ] PR demo: paste a repo URL, wait for the analysis, tap `✍️ Freestyle`, type a custom prompt (e.g. `"explain this for a Rust developer"`), receive a fresh re-analysis with the Rust-developer framing; verify the Sheets row is updated in place rather than duplicated.

## Blocked by

- #68 — needs the Gemini analysis surface and the `_build_repo_prompt(freestyle_prompt=...)` parameter wired.
- #70 — needs `sheets.update_repo_row` available so the re-run updates instead of appends.
