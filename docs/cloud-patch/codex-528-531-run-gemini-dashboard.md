# Codex prompt — implement issues #528–#531 (dashboard "Run Gemini" recipe picker)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0050-dashboard-run-gemini-mirrors-queue-not-sync-call.md` — the
   accepted decision: why this is queued (mirrors Telegram) rather than called
   synchronously (like Checklists), the atomic-claim shape, and the
   `freestyle_prompt` handling. Authoritative over any older wording elsewhere.
2. `docs/TASK.md`, task 35 ("Long-pipeline transcript segment + dashboard
   \"Run Gemini\" recipe picker") — the full grilled brief (Backend/UI
   sections) this batch was sliced from.
3. `CONTEXT.md`'s **Template picker keyboard** glossary entry — the Telegram
   flow this dashboard feature mirrors (five built-ins + Freestyle, no custom
   templates).
4. `CLAUDE.md` (repo root) — layout, and the exact test/lint commands.
5. `DESIGN.md` and `PRODUCT.md` (repo root) — visual system, motion/reduced-motion
   rules, and the "one rationed signal orange" bar this UI must respect.
6. The concrete files you'll touch (see each issue section below for the
   specific anchors — line numbers were re-verified against the current tree
   when this prompt was written, but re-check them yourself before editing).
7. GitHub issues #528–#531 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per issue.

## Key decisions already made (do not relitigate)

- The "Run Gemini" trigger is a **one-time gate**, not a repeatable
  "regenerate" control like Checklists: visible only when
  `content_type === 'long' && status === 'transcript_done'`. It disappears the
  moment a claim succeeds (optimistic `status: 'enriching'`) and never
  reappears once the job has been enriched.
- The recipe picker offers **exactly** the five built-in templates
  (`summary`, `method`, `technical`, `review`, `narrative`) plus Freestyle —
  the same set Telegram's `_cb_gemini_yes` keyboard offers
  (`src/telegram/webhook.py:219-260`). It does **not** read the full
  `/api/templates` list or offer user-defined ("Your recipes") templates —
  those aren't wired into `enrichment.py`'s template lookup at all yet; that's
  a separate, unbuilt capability, out of scope here.
- The backend claim is **atomic**, mirroring this repo's existing
  conditional-UPDATE convention (`backfill_og_image_url`, `src/database.py`
  around line 1808 — `UPDATE ... WHERE id = ? AND status = 'x' ...` via
  `_execute_rowcount`, `src/database.py:1489`, treating `rowcount > 0` as
  success). Don't invent a different locking mechanism (no `SELECT ... FOR
  UPDATE`, no app-level mutex).
- `enrichment.py` (the processor itself) is **not modified** by this batch.
  The new endpoint only adds a second caller of the existing
  `{"task": "enrichment", "job_id": ...}` queue envelope — the exact one
  `_cb_template_pick` (`src/telegram/webhook.py:263-288`) already enqueues.
  A dashboard-triggered enrichment will still message the job's Telegram chat
  — that's expected (ADR-0050), not a bug to "fix."
- Desktop and mobile render the picker differently (accordion vs. slide-in
  panel — split across #530/#531) but call the **same** submit handler and
  hit the **same** endpoint. Don't fork the submission logic per breakpoint.

## Work order

#528 and #529 are independent — implement in either order, or in parallel if
you're working sequentially just do #528 first since it's the smallest. #530
requires #529's endpoint to exist. #531 requires #530's picker to exist. Each
slice must leave the app working: `python -m pytest tests -q`, `ruff check
src/`, and (for the web slices) `npm run test:run`, `npm run lint`, `npm run
build` from `web/`.

### #528 — long-pipeline job pages show their transcript

Current: `web/lib/job-detail-utils.ts:14` defines `ENRICHMENT_FIELDS` (the
field list rendered for `long`/`article`/`repo` jobs — selected at
`web/app/(dashboard)/jobs/[id]/page.tsx:170` via `job.content_type === 'short'
? SHORT_FIELDS : ENRICHMENT_FIELDS`). `SHORT_FIELDS` (`job-detail-utils.ts:25`)
already includes `{ key: 'transcript', label: 'Transcript', render: 'text' }`
at line 27; `ENRICHMENT_FIELDS` has no equivalent entry.

Fix: add the same `transcript` field object to `ENRICHMENT_FIELDS`, positioned
**first** in the array (before `ai_topic`) — mirrors short's "primary content
first" ordering. No backend or type change: `JobDetail.transcript`
(`web/lib/hooks/useJobDetail.ts`) is already populated on the job-detail
response; `long_video.py` already writes `jobs.transcript`.

Regression: article and repo jobs must not gain an empty "Transcript" card.
This is already covered by the existing `presentFields` filter in
`page.tsx` (drops null/undefined/empty-string values) since neither
`src/processors/article.py` nor `src/services/github.py` ever write
`jobs.transcript` — confirm this stays true rather than assuming it.

Test: extend whichever colocated test currently covers
`web/app/(dashboard)/jobs/[id]/page.tsx` (there is a `.test.tsx` beside it) to
assert a `long` job with a non-empty `transcript` renders a Transcript field
card, and that an `article`/`repo` job fixture without one does not.

### #529 — backend: `POST /api/jobs/{job_id}/enrich`

Current: `src/api/jobs.py` — `create_job` (around line 213) already validates
templates via `_resolve_job_template` (around line 173); there is no
`POST /{job_id}/enrich` route today. `src/api/deps.py:7` defines
`get_owned_job`, the ownership-check convention every other per-job endpoint
uses. `src/telegram/webhook.py:263-288` (`_cb_template_pick`) is the reference
shape: writes `jobs.template`, then
`queue.enqueue({"task": "enrichment", "job_id": actual_job_id})`
(`webhook.py:281`).

Fix direction: add `POST /api/jobs/{job_id}/enrich` to `src/api/jobs.py`.

- Ownership via `get_owned_job`.
- Reject with 422 unless the job's `content_type == 'long'` and
  `status == 'transcript_done'`.
- Validate the request body `{template, freestyle_prompt}` by reusing
  `_resolve_job_template` — do not re-implement its validation.
- Claim atomically: a single conditional `UPDATE jobs SET status='enriching',
  template=?, freestyle_prompt=? WHERE id=? AND status='transcript_done'`,
  executed through `_execute_rowcount` (`src/database.py:1489`) the same way
  `backfill_og_image_url` does. `freestyle_prompt` is the submitted value when
  `template == 'freestyle'`, else explicitly `NULL` (clears any stale value
  from a prior attempt — don't leave it untouched). A `rowcount == 0` result
  means the claim lost the race (already `enriching`, or moved on) — return
  409 and do **not** enqueue.
- On a successful claim, enqueue `{"task": "enrichment", "job_id": job_id}` —
  the exact envelope `_cb_template_pick` uses. If enqueueing raises, best-effort
  `UPDATE` the row back to `status='transcript_done'` so the job isn't
  stranded in `enriching` with nothing actually queued, then surface a 5xx.

Regression: `src/processors/enrichment.py` must not change — this issue only
adds a second caller of the existing task envelope. Telegram's
`_cb_gemini_yes` → `_cb_template_pick` flow must keep working exactly as it
does today (same DB writes, same enqueue call).

Test: new `tests/test_jobs_api_enrich.py`, mirroring the fixture/setup pattern
in `tests/test_jobs_api_checklists.py` (temp DB, monkeypatched `DB_PATH`,
`TestClient`). Cover: ownership rejection (a different chat's job), wrong
`content_type` rejection, wrong `status` rejection, invalid-template
rejection, successful claim + correct enqueue payload, a second concurrent/
stale claim attempt returning 409 and not enqueueing again, `freestyle_prompt`
persisted on a freestyle pick and cleared (`NULL`) on a named-template pick,
and rollback to `transcript_done` when the enqueue call is mocked to raise.

### #530 — dashboard: Run Gemini button + inline recipe picker + poll-to-completion

Current: `web/app/(dashboard)/jobs/[id]/page.tsx` — `JobActionsBar` renders at
line 764, `{!restricted && <ChecklistsSection job={job} />}` immediately after
at line 769; `ChecklistsSection` itself (defined at line 546) shows the
existing error-surfacing convention to mirror
(`error && <p role="alert" className="text-status-error">{error}</p>`, around
line 598). `web/lib/fetch-utils.ts`'s `useFetchDetail` (around line 129)
returns `{ data, setData, fetchState }` — no `reload`/refetch capability
exists yet. `web/lib/polling.ts:9` exports `startPolling(fetchFn, isIdleFn,
intervalMs)`; `web/lib/hooks/useInFlightPolling.ts` is the existing consumer
(Feed's card-level polling), with `IN_FLIGHT_STATUSES` including
`'enriching'`. `web/components/feed/submit-job.tsx` has the existing
`freestylePrompt` state + textarea pattern (search `freestylePrompt` in that
file) to reuse for the picker's Freestyle option.

Fix direction:

- Add a `reload()` capability to `useJobDetail/useFetchDetail` (small, general
  addition — expose a callback that re-runs the existing fetch effect body; do
  not build a second, parallel fetch hook).
- Render a "Run Gemini" trigger between `JobActionsBar` and
  `ChecklistsSection`, gated on `!restricted && content_type === 'long' &&
  status === 'transcript_done'` — same restricted-mode gating
  `ChecklistsSection` already uses. Plain-text label ("Run Gemini"), no
  emoji — match `ChecklistsSection`'s own button copy conventions, not
  Telegram's.
- Activating it reveals an **inline** accordion panel in the page's normal
  flow (not a modal/dialog — `web/components/ui/dialog.tsx` is a pop/fade
  transition, not a slide, and is deliberately not used here), listing the
  five named templates as one-tap buttons plus a Freestyle option that
  reveals a textarea + separate submit button before it can be submitted
  (reuse the `freestylePrompt` pattern from `submit-job.tsx`). Respect
  `prefers-reduced-motion` on the reveal transition.
- Submitting calls `POST /api/jobs/{job_id}/enrich` (#529). On success,
  optimistically call the job-detail hook's `setData` to set
  `status: 'enriching'` on the held job object — this immediately hides the
  trigger/panel (their gate is `status === 'transcript_done'`) and prevents a
  second submission in the same page view without a separate disabled flag.
  On a non-2xx response (including 409), show an inline error using the same
  `role="alert"` pattern `ChecklistsSection` uses — do not fail silently.
- While `status === 'enriching'`, poll via `startPolling` (reuse it directly,
  same 10-second interval `useInFlightPolling` uses) calling the new
  `reload()`, with the idle condition being "job status is no longer
  `enriching`." Once a poll observes `status` has moved to `done` or `error`,
  polling stops and the page's existing render (via `presentFields`, from
  #528's field list) picks up the new data automatically — no separate
  "result" UI to build.
- This issue ships the picker identically on mobile and desktop (accordion
  everywhere); #531 upgrades the desktop container only.

Regression: existing Checklists and delete-button behavior on this page must
be unaffected. `useJobDetail`'s existing auto-refetch-on-`jobId`-change
behavior must keep working after adding `reload()`.

Test: colocated `.test.tsx` for the page (or a new one if the existing file is
already large — match whatever convention the current test file uses).
Cover: trigger visibility gating (all four conditions), named-template
one-tap submit, Freestyle requiring text before submit, optimistic hide on
success, inline error on a mocked 409/500 response, and that polling starts
only while `status === 'enriching'` and stops once it isn't (use fake timers
or the existing pattern this repo's polling tests already use for
`useInFlightPolling`, if one exists — check first).

### #531 — desktop: recipe picker becomes an edge slide-in panel with descriptions

Current: `web/components/shell/sidebar.tsx:435` has the repo's only existing
slide-in pattern (`open ? 'translate-x-0' : '-translate-x-full'`).
`web/lib/hooks/useTemplateList.ts` already fetches `/api/templates` and
exposes `{ templates, loading, fetchError, ... }`, where each `Template` has
`is_builtin: boolean` and `description: string`.

Fix direction: on desktop breakpoints, activating "Run Gemini" opens the
picker in a panel sliding in from a screen edge, mirroring `sidebar.tsx`'s
`translate-x` pattern instead of #530's inline accordion. Reuse
`useTemplateList`, filtered to `t.is_builtin === true`, to show each named
template's `description` next to its label. Mobile is untouched — it keeps
the accordion from #530. Submission, one-tap-vs-Freestyle-text behavior, the
optimistic hide, error surfacing, and polling are all unchanged from #530 —
this issue only swaps the desktop container and adds descriptions, no new
state or network calls beyond the existing `useTemplateList` fetch.

Regression: mobile rendering path from #530 must be byte-for-byte behavior
unchanged (only the desktop breakpoint's container differs).

Test: extend #530's test coverage with desktop-viewport assertions that the
slide-in container renders (not the accordion) and that each built-in
template's description is visible; assert the narrow-viewport path still
renders the accordion.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch files outside `src/api/jobs.py`, `src/database.py` (only the new
  claim query), `web/lib/job-detail-utils.ts`, `web/lib/fetch-utils.ts`,
  `web/lib/hooks/useJobDetail.ts`, `web/app/(dashboard)/jobs/[id]/page.tsx`,
  and their colocated tests — plus any genuinely new files this batch
  introduces (e.g. `tests/test_jobs_api_enrich.py`). Do not touch
  `src/processors/enrichment.py`, `src/telegram/webhook.py`, or anything
  under `docs/`.
- Don't refactor unrelated code in a file you open for one fix.
- Run `python -m pytest tests -q` and `ruff check src/` for the backend slice
  (#529), and `npm run test:run`, `npm run lint`, `npm run build` from `web/`
  for the frontend slices (#528, #530, #531) — per `CLAUDE.md` — never through
  the `rtk` hook.

## Deliverable

Uncommitted working-tree changes implementing #528–#531 fully (or as far as
the dependency chain allows if you run out of budget — #528 and #529 must not
be left half-done since #530/#531 depend on #529), with regression test
coverage per each issue's acceptance criteria, plus a short summary of what
was done per issue and anything that blocked you.
