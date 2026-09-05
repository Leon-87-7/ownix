# Codex prompt — implement issue #605 (email digest pipeline, batch 3: job-recovery exclusion + dedicated retry)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

This is **batch 3 of 4** implementing the email-digest feature (#600–#606).
Batches 1–2 (#600–#604: schema, subscription API, webhook, processor,
promotion, frontend detail page) have already landed in this working tree.
This batch is a single, small, self-contained fix: `src/services/
job_recovery.py`'s generic retry logic cannot distinguish an `email_digest`
receipt job from a plain `link` or `bookmarks` job (all three now share
`content_type='link'`), so retrying it generically would incorrectly
re-enqueue it as a fetchable `link` job against a non-fetchable
`email_digest:<hash>` URL.

## Required context — read these first, in this order

1. `src/services/job_recovery.py` — read the whole file. This is the file
   you are fixing.
2. `PLAN.md` (repo root) — the "Failed-digest retry" entry in the Risks /
   open questions section states the full problem and the intended fix.
3. `PLAN-REVIEW-LOG.md` (repo root) — Round 4 finding #2 (the gap
   discovered), Round 5 finding #1 (the fix must cover every consumer of the
   shared helper, not just one function).
4. `CLAUDE.md` (repo root) — `python -m pytest tests -q` via PowerShell
   only, never through the `rtk` Bash hook.
5. Whatever route module/API path batch 2 (#603) put the newsletter-digest
   promotion routes in — grep for `newsletter_subscriptions`/
   `digest_candidates`/`email_digest` under `src/api/` to find it; the
   dedicated retry action in this batch belongs alongside those routes.
6. GitHub issue #605 (`gh issue view 605 --repo Leon-87-7/ownix`) — its
   acceptance criteria are the definition of done.

## Key decisions already made (do not relitigate)

- **The exclusion is one predicate in one shared place**:
  `_scope_where()` in `src/services/job_recovery.py:26-32` is already the
  single helper behind `recovery_summary()` (line 35), `retry_pending()`
  (line 61), and `_claim_error_rows()` (line 195) → `retry_error()` (line
  220). Add `url NOT LIKE 'email_digest:%'` to the `conditions` list built
  there — one edit covers all three call sites. Do not duplicate the
  predicate per function, and do not add separate `WHERE` clauses to each
  caller individually.
- **Do not touch `database.fetch_and_mark_stale_jobs()`** (the separate
  stale-processing reaper called from `retry_error()`) — resetting a stuck
  `processing` row to `error` is safe regardless of task and is out of
  scope for this fix. Only the *retry* path (which guesses the wrong task
  from `content_type`) is the actual bug.
- **The dedicated retry action re-enqueues the same `job_id`**
  (`{"task": "email_digest", "job_id": ...}`), it is not `retry_error()`'s
  create-a-new-row shape (`src/services/job_recovery.py:259-268`) — that
  shape is what makes `retry_error()`'s content_type-keyed task lookup
  necessary in the first place, and re-creating a row for an
  `email_digest:<hash>` job would just create a second synthetic receipt
  job pointing at the same (already-consumed) payload. Reset the job's
  status appropriately before re-enqueueing, matching how the existing
  same-job retry branches in `retry_error()` (the `article` and
  `long`-with-transcript branches, `src/services/job_recovery.py:239-250`)
  reset status before calling `queue.enqueue`.
- **`bookmarks` jobs have the identical mis-retry exposure today and it is
  explicitly out of scope for this issue** — do not fix it as a drive-by. A
  one-line comment noting it's a known, separate pre-existing gap is
  welcome; a silent fix to the `bookmarks` path is not (unrequested,
  unreviewed behavior change to an unrelated pipeline).

## Work order

### #605 — fix(job-recovery): exclude email_digest receipt jobs; add dedicated retry

1. Add the `url NOT LIKE 'email_digest:%'` predicate to `_scope_where()`
   (`src/services/job_recovery.py:26-32`).
2. Add one dedicated retry API route, scoped specifically to
   `email_digest`-task error jobs, that:
   - Loads the job scoped by `(id, chat_id)` (or through the owning
     subscription, whichever the actual #603 route module's ownership
     pattern uses — check the real code, don't guess).
   - Verifies the job is actually an `email_digest`-task error job (its
     `url` starts with `email_digest:` and `status == 'error'`) — reject/404
     on anything else, including a `bookmarks` receipt job with the same
     `content_type`.
   - Re-enqueues `{"task": "email_digest", "job_id": job_id}` against the
     **same** `job_id`, resetting status first.
3. Add the one-line comment about the `bookmarks` pre-existing gap near
   `_scope_where()` or the retry route, whichever reads more naturally.
4. Tests: an errored `email_digest` job survives generic `retry_error()`,
   `retry_pending()` unchanged, and is absent from `recovery_summary()`
   counts; the dedicated retry action successfully re-enqueues the same
   `job_id`; the dedicated retry action rejects a non-`email_digest` job
   (including a `bookmarks` job with `content_type='link'`) and a
   cross-tenant job.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch files outside `src/services/job_recovery.py`, the new retry
  route (wherever the existing newsletter-digest routes live), and their
  tests. Do not refactor unrelated parts of `job_recovery.py`.
- Do not fix the `bookmarks` mis-retry exposure — flag it, don't fix it.
- Do not build #606 (ops Worker) — a separate, later batch.
- Test commands: `python -m pytest tests -q` (PowerShell, never the `rtk`
  Bash hook). `ruff check src/`.

## Deliverable

Uncommitted working-tree changes implementing #605 fully: the shared
exclusion predicate and the dedicated same-job retry action. Regression
tests per the issue's acceptance criteria. A short summary of what was done
and the exact route path chosen for the dedicated retry action.
