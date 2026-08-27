# Codex prompt — implement issues #561–#563 (job/link tag unification)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/plans/2026-08-27-job-link-tag-unification.md` — the full plan and every
   decision behind this batch. Authoritative, **except** for one corrected
   finding: §0's cardinality table says `repo` ingest is "gated on
   `settings.GOOGLE_DRIVE_FOLDER_BRAIN`" the same way `article` is. That is
   wrong for `repo` — see "Key decisions" below for the corrected version.
2. `CLAUDE.md` (repo root) — layout, and the test/lint commands in "Commands".
   Run `python -m pytest` via a **PowerShell** shell, never piped through a
   Bash `rtk` hook if one is configured in this environment — it can silently
   hang pytest without surfacing a failure.
3. `src/api/jobs.py` — `list_jobs` (~line 328), `get_job` (~line 636),
   `get_job_tags`/`attach_tag`/`detach_tag` (~lines 441–480). This is where
   the derived `link_id` and the sweep operation are wired in.
4. `src/database.py` — the six tag-CRUD helpers you'll reuse: `list_job_tags`,
   `attach_job_tag`, `detach_job_tag` (~lines 2614–2675) and `list_link_tags`,
   `attach_link_tag`, `detach_link_tag` (~lines 2538–2569).
5. `src/brain.py` — `normalize_url` (~line 293) and `_ingest_one_link`
   (~line 431, its `INSERT ... ON CONFLICT(chat_id, url)` at ~line 484 is why
   a link row is unique per `(chat_id, url)`).
6. `src/processors/link.py`, `src/processors/article.py` (lines 294–299),
   `src/processors/repo.py` (lines 555–570, and `_brain_ingest_safe` at
   line 423) — the three processors whose jobs this batch merges.
7. `web/lib/hooks/useJobTags.ts`, `web/lib/hooks/useLinkTags.ts`,
   `web/components/feed/job-card-tags.tsx`,
   `web/app/(dashboard)/jobs/[id]/page.tsx` (the `useJobTags` call at
   ~line 1090 and the `TagMenu` render at ~line 1193) — the frontend call
   sites you're switching.
8. GitHub issues #561–#563 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per slice.

## Key decisions already made (do not relitigate)

- **Frontend-only redirect.** `/api/jobs/{id}/tags` (`get_job_tags`/
  `attach_tag`/`detach_tag` in `src/api/jobs.py`) is **not modified** and
  keeps meaning exactly one thing — a job's own `job_tags` rows — for every
  content type. Do not add `content_type` branching inside those handlers.
  The redirect happens entirely on the frontend: for `content_type IN
  ('link', 'article', 'repo')`, `JobCardTags` and the job-detail page's
  `TagMenu` call site switch to `useLinkTags(link_id)` once a `link_id` is
  available; every other content type is untouched.
- **Join key: `chat_id` + `normalize_url(job.url)` against `links.url`** —
  mirror the exact lookup `link.py` already does at its own verification
  step (lines 43–49). **Do not use `links.source_job`** for this join —
  `database.count_job_links` uses `source_job = ?`, but that column is
  first-creator provenance only (CONTEXT.md rule 15: "provenance, not
  ownership") and is never updated on a re-sighting. It will return nothing
  for the cross-pipeline case #562/#563 explicitly require (a URL that a
  *different*, earlier job already turned into a link) — that case must
  resolve by URL identity, not by which job happens to own the `source_job`
  column.
- **Corrected finding — `repo`'s ingest is not `GOOGLE_DRIVE_FOLDER_BRAIN`-gated.**
  `article.py:294-299` wraps its entire `brain.ingest_links` call in
  `if settings.GOOGLE_DRIVE_FOLDER_BRAIN:` — if that setting is unset, an
  article job never even attempts to create a link row. `repo.py:563-570`
  has no such gate: `spawn_background(_brain_ingest_safe(...))` always
  fires, and `_brain_ingest_safe` (line 423) swallows any exception
  internally and just logs a warning. So for `repo`, "the link doesn't exist
  yet" is purely a fire-and-forget timing race (or a swallowed failure), not
  a config gate. Implement the not-yet-linked fallback generically — "does
  `link_id` resolve right now?" — never keyed off `GOOGLE_DRIVE_FOLDER_BRAIN`
  specifically for `repo`.
- **The sweep-and-switch rule, run whenever a merged job's tag control
  loads:** if `link_id` resolves AND the job still has rows in `job_tags`
  (via `database.list_job_tags(job_id)`), union those tags onto the link
  (`database.attach_link_tag(link_id, tag_id)` per tag — already idempotent,
  `INSERT OR IGNORE`), then delete the swept `job_tags` rows
  (`database.detach_job_tag(job_id, tag_id)` per tag, or an equivalent bulk
  delete). Never remove a tag already on the link. After the sweep (or if
  there was nothing to sweep), the job's tag control reads/writes through
  the link's tags exclusively.
- **No disabled state, no timeout constant, no polling.** While `link_id`
  doesn't resolve (article/repo only — `link` jobs are always
  verified-present, per `link.py`), the tag control behaves exactly like an
  ordinary, fully-editable job-tags control — the same experience
  `short`/`long`/`photo`/`document` already have.
- **No schema migration, no `PRAGMA user_version` bump.** The sweep is a
  runtime read-time operation using existing tables (`job_tags`,
  `link_tags`) and existing helper functions — do not add new tables or
  columns.
- **Batch-safe `link_id` resolution in `list_jobs`.** Mirror the existing
  `short_ids` / `database.get_thumbnail_job_ids` follow-up-query pattern
  already in `list_jobs` (`src/api/jobs.py`, right after the main SELECT,
  ~lines 361–367): resolve `link_id` for the subset of returned rows whose
  `content_type IN ('link','article','repo')` in one batched query, not a
  per-row join inside the main SELECT and not N+1 queries.
- **Single-job `link_id` in `get_job`.** Mirror the existing `link_count`
  pattern (`src/api/jobs.py:642-644`) — computed after `detail_fields_for`
  filtering and added to the response outside the content-type field
  allowlist, since `link_id` isn't a raw job column.
- **Carrier-job boundary (non-negotiable, applies to all three issues):** a
  `short`/`long`/`photo`/`document` job's tags never flow to any link it
  surfaced, and no UI change of any kind happens for those content types —
  no tooltip, no label, no badge. This was a deliberate decision (documented
  in the plan §1), not an oversight to "fix" while you're in this code.

## Work order

Implement in issue order — each slice builds on the previous, and each must
leave the app working (`python -m pytest tests -q` and `ruff check src/` from
the repo root; `npm run test:run`, `npm run lint`, and `npm run build` from
`web/`).

### #561 — merge job tags into link tags for content_type=link

Add the derived `link_id` (per "Key decisions" above) to both `list_jobs` and
`get_job` in `src/api/jobs.py`, scoped to `content_type IN ('link', 'article',
'repo')` (build the full set now even though only `link` is wired on the
frontend in this slice — #562/#563 reuse it as-is). Implement the
sweep-and-switch helper (likely in `src/database.py` alongside the tag CRUD
functions it composes, or in `src/api/jobs.py` next to `get_job_tags`) and
call it from wherever the frontend fetches a merged job's tags. Switch
`web/components/feed/job-card-tags.tsx` and the `useJobTags`/`TagMenu` call
site in `web/app/(dashboard)/jobs/[id]/page.tsx` (lines ~1090 and ~1193) to
use `useLinkTags(link_id)` when `content_type === 'link'`.

Fix direction: `link`-type jobs are always link_id-resolvable by the time
they reach `done` (`link.py`'s own verification), so this slice needs no
fallback logic — that's #562's job. Keep the sweep helper generic (it takes a
`job_id` + `link_id`, not a content-type check) so #562/#563 can call it
unchanged.

Regression: `short`/`long`/`photo`/`document` jobs must not receive a
`link_id` field at all (not `null` — omit it), and their `/api/jobs/{id}/tags`
behavior must be byte-for-byte unchanged. Add a test proving a carrier job's
`job_tags` are never touched by the sweep helper even if that job happens to
share a `link_id`-resolvable URL by coincidence.

Test coverage (colocated, this repo's convention): a `tests/` module for the
new `link_id` resolution and sweep helper (backend), and
`job-card-tags.test.tsx` / the job-detail page's existing test file
(frontend) covering: pre-existing `job_tags` get swept on first load after a
`link_id` resolves; a `link`-type job with no prior `job_tags` shows the
link's tags directly; short/long/photo/document are unaffected.

### #562 — extend merge to article jobs with not-yet-linked fallback

Add `article` to the frontend redirect's content-type set. Implement the
not-yet-linked fallback: when `link_id` is absent for an `article` job, the
tag control uses `useJobTags`/`job_tags` exactly like `short`/`long` do today
(no special-casing, no disabled state). Once `link_id` later resolves (next
time the tag control loads), #561's sweep helper fires automatically — no new
mechanism, just reusing #561's helper.

Fix direction: this reuses #561's `link_id` resolution (already scoped to
include `article`) — check whether the returned `link_id` is present before
deciding which hook to call, don't add an article-specific polling/retry loop.

Regression: re-run #561's carrier-job-boundary test; add the cross-pipeline
case explicitly — a link that already exists (created by an unrelated
job/pipeline) before this article job runs must resolve `link_id` immediately
and show that link's existing tags, with nothing to sweep.

Test coverage: extend the backend link_id/sweep tests to cover `article`'s
not-yet-linked case (mock/seed a job with no matching `links` row, assert the
job-tags path is used; then seed the matching link and assert the next call
sweeps and switches). Frontend test covering the fallback-to-normal-editor
rendering path.

### #563 — extend merge to repo jobs

Same as #562, for `content_type == 'repo'`. This is almost entirely
configuration + tests — the fallback/sweep mechanism from #561/#562 is
reused unchanged. Do not build a repo-specific gating check based on
`GOOGLE_DRIVE_FOLDER_BRAIN` (see the corrected finding above) — the same
"does `link_id` resolve" check #562 uses is sufficient and correct for
`repo` too.

Test coverage: mirror #562's test additions for `repo`, including its own
cross-pipeline case.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Do not touch anything outside `src/api/jobs.py`, `src/database.py`,
  `src/brain.py` (read-only reference — you shouldn't need to change it),
  the three processor files (read-only reference), and the named frontend
  files. Do not refactor unrelated code in any file you open for this.
- `/api/jobs/{id}/tags` request/response contract is frozen — no new query
  params, no new response fields on that endpoint.
- Test commands: `python -m pytest tests -q` and `ruff check src/` from the
  repo root; `npm run test:run`, `npm run lint`, `npm run build` from `web/`.
  Run pytest via PowerShell, not through a Bash-triggered `rtk` hook if this
  environment has one configured — it can hang silently instead of failing.

## Deliverable

Uncommitted working-tree changes implementing #561–#563 fully (all three are
AFK, fully specified — no HITL scaffolding needed), each issue's acceptance
criteria covered by a passing regression test, plus a short summary of what
was done per issue and anything that blocked you.
