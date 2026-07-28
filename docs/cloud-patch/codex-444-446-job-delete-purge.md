# Codex prompt — implement issues #444–#446 (job hard delete + cloud purge)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0042-job-hard-delete-async-purge.md` — the accepted decision.
   It fixes the delete semantics (hard delete, no soft-delete/trash tier), the
   split between the synchronous DB half and the asynchronous cloud purge, and
   the five rejected alternatives. **Authoritative over any paraphrase below if
   the two disagree.**
2. `CONTEXT.md` — glossary entries **Job delete** and **Job purge** (next to
   **Clear failed**, which is the thing this is *not*), plus **Key Invariants**
   12, 15 and 16. Use this vocabulary verbatim in code comments and log events.
3. `CLAUDE.md` (repo root) — layout, component-folder rules, test/lint commands.
   Run pytest via the PowerShell path, never through the `rtk` hook
   (`.claude/rules/rtk-tests.md`).
4. `DESIGN.md` — normative token frontmatter. Note the action color is **Index
   Amber `#d99a45`**, not the `#f6921e` quoted in older briefs; `status-error`
   is `#f87171` on tint `#371717` (line 28). The `components:` block
   (lines ~111–135) is where a new `button-danger` token belongs, and §Buttons
   (lines ~354–360) is where its prose goes.
5. `docs/TASK.md` task 33 — the resolved brief, including the delete-zone
   layout and the correction block listing what the original grounding got
   wrong.
6. The specific files each issue touches — line numbers below were verified
   2026-07-27 but may drift; find the symbol by name if so.
7. GitHub issues #444, #445, #446
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each carries its own
   acceptance criteria; treat those as the definition of done per slice.

## Key decisions already made (do not relitigate)

- **Hard delete.** No soft-delete column, no trash tier, no undo, no retention
  window. The row is gone.
- **The Brain de-index is manual.** `links.source_job` (`src/database.py:179`)
  is `TEXT NOT NULL` with **no foreign key** — it is not one of the five tables
  that cascade off `jobs`. `DELETE FROM links WHERE source_job = ?` is a
  separate, required statement. Do **not** "fix" this by adding an FK
  migration; that is a schema change nobody asked for.
- **Job thumbnails are not cloud artifacts.** `job_thumbnails.bytes` is a
  SQLite BLOB (`src/database.py:99-106`). The cascade disposes of them. The
  `gcs_key` column belongs to `document_outputs` (`src/database.py:278-290`).
  Do not add thumbnail cleanup to the purge.
- **A styled confirm dialog, not `window.confirm`.** This is deliberate and it
  splits the repo's existing pattern. The four existing `window.confirm` call
  sites — `spaces/[id]/page.tsx:31`, `sidebar.tsx:252`, `submit-job.tsx:347`
  and `:709` — are **not** to be migrated. Do not touch them.
- **Filled red exists only inside the dialog.** The page-level trigger is a
  ghost plate with red *text*; the dialog's confirm button is the only solid
  `#f87171` surface in the product. Do not promote the trigger to a filled
  button, and do not use Index Amber for either.
- **Delete is allowed from any status**, including `pending`, `processing` and
  `enriching`. Do not add a 409 guard for non-terminal jobs.
- **The purge is best-effort.** A cloud failure must never fail the user's
  click. The endpoint returns 204 without awaiting any Google API call.
- **Task 19 is out of scope.** No Telegram message deletion, no swipe gesture,
  no feed-card delete, no "don't show again". Task 19 builds on what this batch
  produces.

## Work order

Do them in order. #444 introduces the endpoint that #445 and #446 both extend;
#445 and #446 are independent of each other once #444 exists.

### #444 — permanent delete on the job details page

**Backend.** `src/api/jobs.py` — the router is
`jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])` (line 22). There is
already a DELETE in this file to mirror exactly — `detach_tag`
(lines 423-435):

```python
@jobs_router.delete("/{job_id}/tags/{tag_id}", status_code=204)
async def detach_tag(job_id: str, tag_id: str, request: Request) -> Response:
    ...
    await get_owned_job(job_id, request)
    ...
    return Response(status_code=204)
```

Mirror that shape — `status_code=204`, `get_owned_job` for ownership,
`return Response(status_code=204)`. Don't invent a new response convention.

`get_owned_job` (`src/api/deps.py:7-15`) raises **404** for an unknown id and
**403** for a job owned by another chat. Both must leave the row intact.

Add the DB-layer helper next to `delete_space` (`src/database.py:2182-2190`),
which is the precedent for this shape (`_execute_rowcount`, returns bool). It
must run **both** statements:

- `DELETE FROM jobs WHERE id = ?` — `job_thumbnails`, `job_annotations`,
  `job_tags`, `space_urls` and `document_outputs` cascade.
- `DELETE FROM links WHERE source_job = ?` — the Brain de-index.

FK enforcement is per-connection (`PRAGMA foreign_keys=ON` in `connection()`,
invariant 13) — the cascade silently does nothing without it, so run both
statements inside one `connection()` context.

**Frontend.** `web/app/(dashboard)/jobs/[id]/page.tsx`. `JobActionsBar` is
defined at line 497 and rendered at line 676; the page component's `return`
closes with `</PageShell>` around line 708. The delete zone goes **after** the
notes editor block, immediately before `</PageShell>` — *not* inside
`JobActionsBar`.

The page component (around line 577) reads `restricted` from
`useRestrictedMode()`. It does **not** currently hold a router — the
`useRouter()` at line 363 belongs to the `JobHeader` child. Add one at page
level.

Delete-zone layout — one row, under a `border-line` top rule:

```
[ Delete job ] │ Permanently removes this job, its notes, tags and Brain
                 link, and its files in Drive, Sheets and storage. This
                 can't be undone.
```

- Trigger: ghost border + `text-status-error`. Copy the class shape from
  `web/app/(dashboard)/spaces/[id]/page.tsx:78` — mirror that pattern, don't
  invent a new button treatment. `flex-shrink: 0` so the warning wraps instead
  of squeezing the button.
- Divider: 1px, `border-line`, `align-self: stretch`.
- Below ~620px the row stacks to a column and the divider is hidden.

New component `web/components/ui/confirm-dialog.tsx` (kebab-case, no barrel
file, colocated test — see CLAUDE.md's component-layout rules). Build it on the
existing primitive `web/components/ui/dialog.tsx`, which exports `Dialog`,
`DialogTrigger`, `DialogContent` (with a `hideClose` prop), `DialogTitle` and
`DialogDescription`. `DialogContent` already handles the visual-viewport
recentering and the close affordance — do not reimplement any of that.

Behavior: opens focused on **Cancel** (the safe choice, not the red button),
closes on Escape, keeps Tab focus inside itself. Confirm button is a solid
`#f87171` fill with near-black `#1b1309` text.

Failure: close the dialog and render a small `text-status-error` line under the
trigger — mirror the `deleteFailed` state in
`web/app/(dashboard)/spaces/[id]/page.tsx:28-45`. No toast; the repo has no
toast system and this is not the place to add one.

Success: `if (window.history.length > 1) router.back(); else router.push('/feed')`.

Hide the whole delete zone in restricted mode, the same way the notes editor is
gated at `page.tsx:693`.

**Design system.** Add a `button-danger` token to DESIGN.md's `components:`
block alongside `button-signal` / `button-ghost`, plus a line in §Buttons. This
is the one place a new token is authorized; do not add any other.

**Regression clause:** every existing route in `src/api/jobs.py` must keep
working — in particular `detach_tag`, which shares the `/{job_id}/...` path
space. Confirm the new `DELETE /{job_id}` does not shadow
`DELETE /{job_id}/tags/{tag_id}` (FastAPI matches the more specific path first,
but the ordering of the decorators in the file still matters for readability —
put the new route near `get_job` at line 584).

**Tests:** `tests/test_jobs_api.py` for the endpoint (success, 404 unknown id,
403 other chat's job, `links` rows removed, deletion from `pending`). Colocated
Vitest beside the component — `web/components/ui/confirm-dialog.test.tsx` — and
extend `web/app/(dashboard)/jobs/[id]/page.test.tsx` for the flow, including the
failure line and the restricted-mode absence.

### #445 — drop task envelopes whose job row is gone

`src/worker.py`. `_TASK_HANDLERS` (lines 203-213) holds **nine** discriminators:
`enrichment`, `video`, `article`, `repo`, `document`, `link`, `prd_auto`,
`prd_auto_resend`, `prd_intent`. Note `link` — CLAUDE.md's prose list omits it;
the code is authoritative.

The guard goes in `_dispatch` (line 216), before the handler lookup:

```python
_ROWLESS_TASKS = {"job_purge"}  # operate on a job that is already deleted

async def _dispatch(task: dict) -> None:
    if task["task"] not in _ROWLESS_TASKS:
        job = await database.get_job(task["job_id"])
        if job is None:
            log.info("job_gone_skipped", job_id=task["job_id"], task=task["task"])
            return
    ...
```

**`_ROWLESS_TASKS` is load-bearing.** #446 introduces a `job_purge` envelope
whose job row is deleted *by design*. A blanket "row missing → skip" guard would
silently swallow every purge. Add the exemption set in this slice even though
`job_purge` does not exist yet.

Why this matters: deleting a `pending` job leaves its envelope in the Redis
`video_jobs` list (`src/queue.py:28`). Without the guard the worker pops it and
runs the whole pipeline for a job that no longer exists — and because the video
pipeline is not idempotent (invariant 12 / ADR-0010) that uploads fresh Drive
documents and appends a new Sheets row. The `UPDATE` writes that follow are
silent no-ops against the missing row, so nothing surfaces the problem.

**Out of scope:** interrupting a job already mid-pipeline. There is no live
cancellation — `status='cancelled'` is only ever set on `error` rows by
`src/services/job_recovery.py:156` and `:209`, and the worker catches only
process-level `asyncio.CancelledError` (line 286). Do not add per-processor
existence checks; that window is knowingly accepted in ADR-0042.

**Regression clause:** all nine existing discriminators must still dispatch
normally when the row is present, and `unknown_task` logging (line 219) must be
unchanged.

**Tests:** extend the worker tests — an envelope for a deleted job is skipped
without invoking any processor; a `job_purge` envelope is *not* skipped.

### #446 — job_purge: Drive, GCS and Sheets artifacts

**Enqueue side**, in the same endpoint from #444: read the artifact references
**before** deleting the row, then enqueue. `queue.enqueue`
(`src/queue.py:48-54`) validates that the envelope has both `task` and `job_id`
keys and raises `ValueError` otherwise — so `job_id` stays in the envelope even
though the row is gone by the time the worker reads it.

The envelope must also carry **`chat_id`**: every Google call in this repo is
per-user (`build_google_service(..., chat_id=...)`,
`user_folder_id(chat_id)` in `src/services/drive.py`). Without it the worker
cannot authenticate against the right account.

Reference set to capture:

- Drive: `drive_file_id`, `prd_auto_drive_file_id`, `prd_intent_drive_file_id`
  from the `jobs` row.
- GCS: every `gcs_key` from the job's `document_outputs` rows
  (`src/database.py:278-290`) — read them before the cascade removes them.
- Sheets: the job's `url`.

The endpoint still returns 204 without awaiting any Google API call.

**Worker side.** Register `job_purge` in `_TASK_HANDLERS` and add
`src/processors/purge.py` following the shape of the existing processors.

Three new service functions, each in its own existing module — mirror that
module's existing style (they all wrap sync Google clients via
`asyncio.to_thread` and route errors through `handle_google_refresh_error` /
`log` helpers; follow that, don't invent a new error path):

- `src/services/drive.py` — a delete/trash function. The module currently has
  only upload/create/update variants.
- `src/services/storage.py` — a `delete(key)`. The module currently has
  `upload`, `download`, `exists` and `object_key` (lines 25-52).
- `src/services/sheets.py` — a row delete. The module currently has only
  append-row and update-row. **The `jobs` table stores no sheet row index**, so
  the row must be located by searching the sheet for the job's URL. A miss is
  logged and skipped — do not retry it forever, and do not add a row-index
  column to `jobs` to make this easier (that is a schema change out of scope).

A failure against any one service must not prevent the other two from running.
Log each failure with the job id and the service; leave the DB clean either way.

**Regression clause:** existing Drive uploads, GCS writes and Sheets appends
must keep working unchanged — these modules are on the hot path for every
pipeline.

**Tests:** cover the handler with each service stubbed, including the
partial-failure path and the Sheets row-not-found path, plus a test that the
endpoint enqueues an envelope carrying `chat_id` and the captured refs.

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Working tree only.
- **Scope fence.** Touch only: `src/api/jobs.py`, `src/api/deps.py` (read-only —
  no changes expected), `src/database.py`, `src/worker.py`, `src/queue.py`
  (read-only), `src/processors/purge.py` (new), `src/services/drive.py`,
  `src/services/storage.py`, `src/services/sheets.py`,
  `web/app/(dashboard)/jobs/[id]/page.tsx`,
  `web/components/ui/confirm-dialog.tsx` (new), `DESIGN.md`, and the test files
  named above. Do not refactor unrelated code in a file you opened for one fix.
- **Do not migrate the four existing `window.confirm` call sites.** The split is
  deliberate (ADR-0042, "Considered options").
- **No schema migrations.** No FK on `links.source_job`, no sheet-row-index
  column. Both were considered and rejected.
- **No new dependencies.** No toast library, no confirm library — the repo has
  Radix Dialog already.
- Tests and lint, never through the `rtk` hook
  (`.claude/rules/rtk-tests.md` — run pytest via PowerShell):
  - `python -m pytest tests/test_jobs_api.py -q` (and the worker test file)
  - `ruff check src/`
  - from `web/`: `npm run test:run`, `npm run lint`, `npm run build`

## Deliverable

Uncommitted working-tree changes implementing #444, #445 and #446, with
regression tests matching each issue's own acceptance criteria, plus a short
summary of what was done per slice and anything that blocked — in particular,
if the Sheets API surface makes a search-by-URL row delete impractical, say so
and leave that one function stubbed rather than inventing a row-index schema
change.
