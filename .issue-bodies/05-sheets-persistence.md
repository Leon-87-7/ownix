## What to build

Add **Sheets persistence** for the repo pipeline. New `Repo Analysis` tab in the consolidated `GOOGLE_SHEETS_ID` (5th tab, joining `YouTube Transcript Index`, `Short Video Analysis`, `Article Analysis`, `mini PRD`). Append a row on first run via `sheets.append_repo_row`; update in place on `/freestyle` re-run via `sheets.update_repo_row` keyed by `jobs.sheets_row_id`.

Behavior:

- New tab `Repo Analysis` in the spreadsheet identified by `GOOGLE_SHEETS_ID` (the operator manually creates the physical tab + header row; this issue is the code side).
- 20 columns in this order (spec **§Repo Analysis tab columns**):

  ```
  job_id | url | owner | repo | title | tagline | tech_stack
  | stars | forks | language | last_pushed | archived
  | project_ideas | when_to_use | avoid_when
  | concepts_taught | prerequisites | curriculum_hooks
  | submitted_at | status
  ```

- Array-shaped fields serialize as newline-joined strings (matching `Article Analysis` precedent for `action_points` / `tools`):
  - `tech_stack`, `project_ideas`, `concepts_taught`, `prerequisites` → `"\n".join(items)`
  - `curriculum_hooks` → one item per line as `"{concept} — {file_pointer}: {why}"`, omitting the ` — {file_pointer}` segment when null.
- Boolean `archived` serializes as `"TRUE"` / `"FALSE"` (matching Sheets convention).
- `sheets.append_repo_row(job, analysis, bundle)` calls existing `_append_sync(tab_name="Repo Analysis", values=[...])` from ADR-0013. Captures the appended row id (Sheets returns `updates.updatedRange`) and writes it to `jobs.sheets_row_id` for later update.
- `sheets.update_repo_row(job, analysis, bundle)` performs an in-place overwrite via `spreadsheets.values.update` at the cached `sheets_row_id` range. Used by the freestyle re-run path (#8).
- `processors.repo.run` calls `append_repo_row` (or `update_repo_row` when `job.sheets_row_id` is non-null) **fire-and-forget** via `asyncio.create_task(...)` — never blocks the user-facing response (invariant #3 from CONTEXT.md).
- Failure of the Sheets call logs a warning but does not move the job to `error`. The Telegram document + summary already shipped from #69 and #68; the audit trail is best-effort.

Reference spec: **§Design Decisions** (#10), **§Repo Analysis tab columns**, **§Schema additions**, ADR-0013.

## Acceptance criteria

- [ ] `sheets.append_repo_row(job, analysis, bundle)` appends a row to the `Repo Analysis` tab with all 20 columns in the spec'd order.
- [ ] Array fields serialize newline-joined; `curriculum_hooks` serializes per the `concept — file_pointer: why` rule (with file_pointer omitted when null).
- [ ] `jobs.sheets_row_id` is populated after a successful append (captured from `values.append` response's `updates.updatedRange`).
- [ ] `sheets.update_repo_row(job, analysis, bundle)` performs `values.update` at the cached range; row count stays constant after a re-run (verify in tests with a mocked Sheets client).
- [ ] `processors.repo.run` invokes `append_repo_row` exactly once per fresh job and `update_repo_row` exactly once per freestyle re-run (driven by presence of `jobs.sheets_row_id`).
- [ ] The Sheets call is wrapped in `asyncio.create_task` — the function returns before Sheets completes (verify with a deliberately slow mock).
- [ ] A Sheets failure (e.g. 403, transient 5xx) logs a warning but leaves `jobs.status='done'` and does not affect Telegram delivery.
- [ ] Tests: row construction shape; serialization rules for each array field; fire-and-forget contract; failure-isolation contract.
- [ ] CONTEXT.md `Consolidated spreadsheet` entry already mentions the fifth tab (updated during grilling) — verify the wording matches what shipped.
- [ ] PR demo: paste a repo URL, see a row appear in the `Repo Analysis` tab; tap Freestyle, see the same row update in place (when #8 lands) — for this slice the freestyle path can be exercised by manual test queue insertion.

## Blocked by

- #68 — needs the `repo_analysis` JSON to populate the row.
