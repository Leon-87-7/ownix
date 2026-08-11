# Codex prompt — implement issues #505–#508 (checklists command delivery)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

> **Base branch: `worktree-checklists-command`, not `main`.** Plan Tasks 1-5
> (the DB migration, config settings, `src/processors/checklists.py`, and
> `checklists_command`/`SHARED_COMMANDS`) are already committed on that
> branch — see `.claude/worktrees/checklists-command` — and have not been
> merged to `main`. Land this batch on top of `worktree-checklists-command`,
> not on top of `main`, or every "already built" reference in this prompt
> will be missing from your working tree.

## Required context — read these first, in this order

1. `docs/superpowers/plans/2026-08-11-checklists-command.md` — the full implementation plan. Tasks 1-5 (DB migration, config settings, `src/processors/checklists.py`, `checklists_command` in `src/intake/commands.py`) are already merged; this batch covers what the plan calls Tasks 6, 7, 8, 9, 10, 11, 12, and the Task 13 verification folded into #507's acceptance criteria. Its Global Constraints section is binding for all four issues.
2. `CLAUDE.md` (repo root) — project layout, backend/frontend test commands. Backend tests must never run through the `rtk` hook — see `.claude/rules/rtk-tests.md`.
3. `web/CLAUDE.md` — component layout convention (`web/components/<area>/<kebab-name>.tsx`, colocated `.test.tsx`, no barrel files).
4. The four GitHub issues (`gh issue view <n> --repo Leon-87-7/ownix` for 505, 506, 507, 508) — each carries its own acceptance criteria; treat those as the definition of done per slice.

## Key decisions already made (do not relitigate)

- Telegram command word and every internal name is `checklists`, never `audit` — the repo already has an unrelated `audit_log` table/concept; do not introduce any naming collision with it.
- The shared generation core already exists and is **NOT** part of this batch: `run_checklists(job) -> tuple[dict, str]` in `src/processors/checklists.py:88`, and the channel-agnostic `checklists_command(chat_id, parts) -> IntakeResponse` in `src/intake/commands.py:255` (registered in `SHARED_COMMANDS` at `src/intake/commands.py:301`). Do not modify either — build on top of them.
- No lock column, no reaper, no retry-button/keyboard machinery for this feature — a failed generation is just retried by re-running the command/button.
- Persistence is DB-only: `jobs.checklists_md` / `jobs.checklists_generated_at` (already migrated). No Drive upload, no Sheets row, no Brain ingest.
- `CopyButton` currently lives page-local at `web/app/(dashboard)/jobs/[id]/page.tsx:178` (`function CopyButton({ value, ariaLabel, label }: ...)`, imports `Tooltip` from `@/components/ui/tooltip` at line 33). #505 must extract it verbatim, not rewrite it.

## Work order

Implement #505 first — #507 and #508 both need the shared `CopyButton`. #506 has no dependency and can be done in any order relative to the others.

### #505 — Extract shared CopyButton component

Move the `CopyButton` function currently at `web/app/(dashboard)/jobs/[id]/page.tsx:178-217` verbatim into a new `web/components/ui/copy-button.tsx`. Update the page to import it (`import { CopyButton } from '@/components/ui/copy-button';`) instead of defining it locally. Move the existing "does not warn about setState after unmount" regression test out of `web/app/(dashboard)/jobs/[id]/page.test.tsx`'s `describe('CopyButton', ...)` block into a new `web/components/ui/copy-button.test.tsx` that renders the component directly — plus a basic "copies value and shows Copied!" test. Leave a simple "Copy all" smoke test behind in the page's own test file.

Full acceptance criteria: see issue #505.

### #506 — Telegram /checklists command delivery

In `src/telegram/webhook.py`, add `_cmd_checklists(ctx: SlashCtx) -> None` right after `_cmd_spec` (currently at line 667), mirroring the existing `_cmd_find`/`_cmd_force` pattern already in this file: check `len(ctx.parts) < 2` locally and send a usage message, otherwise `await intake_commands.checklists_command(ctx.chat_id, ctx.parts)` and render the result — `send_message` for `kind in ("error", "command_result")`, `send_document` (filename `checklist_<suffix>.md`, caption "✅ Checklist ready") for `kind == "checklists_result"`. Register `"/checklists": _cmd_checklists` in `_SLASH_TABLE` (currently starting at line 1078, right after the `"/spec": _cmd_spec,` entry), and add a `/checklists` line to `_HELP_TEXT` (currently starting at line 1042) matching the existing entries' backtick/em-dash format.

New tests in `tests/test_webhook.py`, mirroring the existing `test_cmd_find_*` tests, monkeypatching `src.telegram.webhook.send_message` / `send_document`.

Full acceptance criteria: see issue #506.

### #507 — Dashboard job detail: generate & display checklists

A full vertical slice — backend endpoint through frontend UI:

- **Backend**: add `checklists_md`, `checklists_generated_at` to `_DETAIL_FIELDS_COMMON` in `src/api/jobs.py` (currently at line 498). Add `POST /api/jobs/{job_id}/checklists` — `get_owned_job`, reject `content_type` outside `{"short", "long"}` and `status` outside `{"transcript_done", "done"}` or empty `transcript` with 422, call `run_checklists(job)` from `src/processors/checklists.py`, persist via `database.update_job_status(job_id, job["status"], checklists_md=md, checklists_generated_at=<iso timestamp>)`, return `{checklists_md, checklists_generated_at}`. New `tests/test_jobs_api_checklists.py` following the authenticated-`TestClient` pattern in `tests/test_api_intake.py` (build a fresh `FastAPI()` app, add `SessionMiddleware`, include `jobs_router`, mint a session cookie) — `tests/test_jobs_api.py` itself has no client fixture, don't add one there.
- **Frontend types/helpers**: add the two fields to `JobDetail` in `web/lib/hooks/useJobDetail.ts`; add `downloadMarkdownFile(filename, content)` to `web/lib/job-detail-utils.ts` (Blob + anchor click + `URL.revokeObjectURL`, no server round trip).
- **Hook**: `web/lib/hooks/useChecklists.ts` — `useChecklists(jobId) -> { generating, error, run }`, `run()` posts to the new endpoint via `apiPost` from `web/lib/fetch-utils.ts` and returns the result or `null` on failure.
- **UI**: a `ChecklistsSection` component in `web/app/(dashboard)/jobs/[id]/page.tsx` — visible only when `content_type` is short/long and `status` is transcript_done/done; "Run Checklists" button (relabels to "Regenerate" once a checklist exists); renders the markdown; a `CopyButton` (from #505) and a "Download .md" button once content exists; shows the last-generated timestamp.

Full acceptance criteria, including the plan's Task 13 full-suite verification requirement: see issue #507.

### #508 — Intake response card: copy button for checklists results

In `web/components/intake/intake-response-card.tsx`, add `checklists_result: 'Checklist'` to the `KIND_LABEL` map, and render a `CopyButton` (from #505; `value={response.text}`) directly under the response-text paragraph, only when `response.kind === 'checklists_result'`. No backend change needed — `/intake` already dispatches `/checklists <suffix>` through the existing `SHARED_COMMANDS` registry.

Full acceptance criteria: see issue #508.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch `src/processors/checklists.py`, `src/intake/commands.py`, `src/database.py`, or `src/config.py` — the generation core and its persistence are already built and out of scope for this batch.
- Don't refactor unrelated code in a file you open for one of these changes (e.g. don't touch other fields in `_DETAIL_FIELDS_COMMON`, don't touch other `_SLASH_TABLE`/`_HELP_TEXT` entries beyond adding the one new line).
- Backend tests: `python -m pytest tests -q` — never through the `rtk` hook (`.claude/rules/rtk-tests.md`). Frontend tests: `npm test -- --run` from `web/`. Lint: `ruff check src/` and `npm run lint` from `web/`.
- Existing valid behavior on the job detail page, `/help`, and the intake response card must keep working exactly as before for every response kind other than `checklists_result`.

## Deliverable

Uncommitted working-tree changes implementing #505–#508 in full, with tests per each issue's acceptance criteria, plus a short summary of what was done per issue and anything that blocked.
