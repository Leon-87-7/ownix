# Codex prompt — implement issues #449–#452 (pending is a preview, not a wall)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0031-invite-gate-and-onboarding.md` — the invite gate: `users.status`
   (`pending`/`approved`/`blocked`), email capture, and the Telegram-only
   approval flow. Approval stays Telegram-only; nothing in this batch changes that.
2. `docs/adr/0035-restricted-mode-preview.md` — Restricted mode: the
   `ownix_preview` cookie, the read-only preview corpus, and the facade pages.
   #450 reuses this machinery wholesale rather than building a second preview path.
3. `CONTEXT.md` (repo root) — domain glossary and the job-status FSM. #449 adds a
   new state to that FSM and must update the entry.
4. `CLAUDE.md` (repo root) — repo layout, component-folder rules, and the exact
   test/lint commands.
5. `DESIGN.md` (repo root) — normative tokens; needed for #450's banner only.
6. The files being changed: `src/database.py`, `src/telegram/webhook.py`,
   `src/services/jobs.py`, `src/services/ops_bot.py`, `src/api/auth.py`,
   `web/components/shell/invite-gate.tsx`.
7. GitHub issues #449–#452 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the definition of done
   per slice.

Source brief: `docs/archive/TASK-archive.md`, task 29.

## Key decisions already made (do not relitigate)

- **`held` is a job status, not a boolean column.** It sits *before* `pending` in
  the job FSM and is only reachable pre-approval. This was weighed against an
  `ALTER TABLE jobs ADD COLUMN held INTEGER` (cheaper migration) and rejected —
  job state stays in one column.
- **Approval remains Telegram-only.** No web-side approve, no admin UI.
- **Web-side submission for pending users is out of scope.** The preview feed is
  read-only; Telegram is the ingest surface for a pending user.
- **`INVITE_AUTO_APPROVE` is out of scope.** It is a separate open idea (#352).
- **Only pending users *with an email on file* get their links held.** A pending
  user with no email still gets the `awaiting_email` prompt — there is nothing to
  hold yet.
- #449 → #451 → #452 is a chain. **#450 is independent** and can be done in any
  order relative to the others.

## Work order

Implement in issue order. Backend slices must leave `python -m pytest tests -q`
green; #450 must leave `npm run test:run`, `npm run lint` and `npm run build`
green from `web/`.

### #449 — hold a pending user's links as un-enqueued `held` jobs

**Current state.** `_invite_gate_allows` (`src/telegram/webhook.py:1358`) is the
gate. A pending user with an email on file falls through to the final two lines
(`webhook.py:1404-1405`): send `_INVITE_WAITING_MESSAGE_TEMPLATE`, `return False`.
The URL is never persisted — that is the bug.

**The `status` CHECK exists in two places and both must change:**

- `src/database.py:88` — inside `SCHEMA_SQL`, the path taken by a **fresh** DB:
  `CHECK(status IN ('pending','processing','transcript_done','enriching','done','error','cancelled')),`
- `src/database.py:975` — the same CHECK inside `_V23_CREATE`, which
  `_V33_CREATE` (`database.py:1134`) derives from and which is the **current**
  jobs schema for an existing DB.

**Fix — migration.** SQLite cannot `ALTER` a CHECK, so rebuild the table. The
repo already has this exact pattern twice; **mirror `_migrate_v32_v33`
(`database.py:1140-1156`) precisely, do not invent a new approach**:

- The current head migration is v33 → v34 (`purge_tasks`, `database.py:1159`), so
  yours is **v34 → v35**, appended at the end of the `_MIGRATIONS` list.
- Derive the schema the same way v33 did: `_V35_CREATE = _V33_CREATE.replace("jobs_v33", "jobs_v35").replace(<old status CHECK>, <status CHECK + 'held'>)`
  and `_V35_COLS = _V33_COLS`.
- Keep the FK dance verbatim: `await conn.commit()` → `PRAGMA foreign_keys=OFF` →
  `_rebuild_jobs_table(conn, _V35_CREATE, "jobs_v35", _V35_COLS)` → commit, then
  `finally: rollback()` + `PRAGMA foreign_keys=ON`. The comment at
  `database.py:1142-1145` explains why — with FK enforcement on, `DROP TABLE jobs`
  cascade-wipes `document_outputs` / `job_thumbnails`. Do not skip it.

**Fix — creation path.** `database.create_job` (`database.py:1450`) hardcodes
`'pending'` in its INSERT (`database.py:1465`). Add a `status: str = "pending"`
keyword so the hold path inserts `'held'` directly; every existing caller keeps
its current behavior untouched. Update the docstring at `database.py:1459`, which
currently states the status as a fact.

**Fix — the gate.** In `_invite_gate_allows`, before the final waiting-message
return, add the hold branch for a pending user with an email: classify the URL
with `detect_pipeline` (`src/utils/validators.py`) first, reject unsupported URLs
with the existing message (the wording used at `webhook.py:1428-1431`), and for a
supported URL create a `held` job and reply "Saved — it processes the moment
you're in."

**Do not route this through `create_and_enqueue_job`** (`src/services/jobs.py:22`) —
it always enqueues (`jobs.py:63`). Call `database.create_job` directly.

**Already correct — do not change, but pin it.** All three `job_recovery` scans
are `WHERE ... status = 'pending'` (`src/services/job_recovery.py:73, 83, 97`), so
held jobs are invisible to recovery by construction. Add a test asserting a `held`
job is not selected, requeued, or counted, so a later refactor cannot silently
resurrect parked jobs.

**Regression clause:** every existing ingest path (Telegram approved users,
`POST /api/jobs`, repo follow-up, `/addlink`) must still create `pending` jobs and
enqueue them exactly as before. Existing rows must survive the migration with
their statuses intact.

**Tests:** `tests/test_database.py` (migration tests live there — it is the only
file touching `user_version`), `tests/test_webhook.py` (the gate branch),
`tests/test_job_recovery.py` (the pinning test). Update `CONTEXT.md`'s job-status
FSM entry to document `held`.

### #451 — flush held jobs to the queue on invite approval

**Current state.** Two approve paths, both flipping `users.status` to `approved`:

- `src/telegram/webhook.py:1684` — the ops invite callback
  (`ops_invite_approve` / `ops_invite_block`, dispatched at `webhook.py:1761`),
  single user.
- `src/services/ops_bot.py:236` — `_approve_pending_ids`, the batch path used by
  `approve_pending_batch` (`ops_bot.py:275`) and `approve_pending_domain`
  (`ops_bot.py:289`). It loops ids, flips each `pending` → `approved`, then DMs
  each approved user "You're in, send a link." (`ops_bot.py:269`).

Neither knows about jobs. After #449, a user's held jobs would sit parked forever.

**Fix.** Write **one** helper in `src/services/jobs.py`, next to
`task_for_content_type` (`jobs.py:13`) and `create_and_enqueue_job` (`jobs.py:22`),
that takes a `chat_id`, selects that user's `held` jobs, flips each to `pending`,
and enqueues it. Call that single helper from both sites — **do not inline the
SQL twice.**

- Enqueue with the existing envelope shape:
  `{"task": task_for_content_type(content_type, default=content_type), "job_id": job_id}`.
  `task_for_content_type` already collapses short/long → `video`.
- Flip status to `pending` **before** enqueueing, so a worker that picks the job
  up instantly never sees a `held` row.
- Prefer the recoverable failure mode: a job left `held` because Redis was down is
  picked up by a later flush; a job flipped to `pending` but never enqueued is
  invisible until `job_recovery`'s staleness window. Log loudly either way.
- Mirror the batch's existing resilience convention (`ops_bot.py:268-271`): one
  user's failure is caught, logged with `log.exception`, and does not abort the
  rest of the batch.

**Regression clause:** the existing "You're in, send a link." DM must still fire,
unchanged, on both paths. Approving a user with zero held jobs is a clean no-op.
A flush must never touch another user's jobs.

**Tests:** `tests/test_webhook.py` (callback path) and a test covering
`_approve_pending_ids` (`tests/test_ops_bot_validation.py` is the existing
ops-bot test file). Assert held → pending, the queue push, and the no-held no-op.

### #452 — invite waiting copy says links sent now are saved

**Current state.** All three invite strings are one-liners at the top of
`src/telegram/webhook.py`:

```
100  _INVITE_EMAIL_PROMPT_TEMPLATE = "VIG is invite-only — what's your email so {admin} can approve you?"
101  _INVITE_WAITING_MESSAGE_TEMPLATE = "Still waiting on {admin}."
103  _INVITE_BLOCKED_MESSAGE = "Access blocked."
```

`_INVITE_WAITING_MESSAGE_TEMPLATE` is sent from two sites in `_invite_gate_allows`
(`webhook.py:1388` right after the email is captured, and `webhook.py:1404` on any
later message), both via `.format(admin=_admin_label())`.

**Fix.** Rewrite the waiting message so it names what happens next: they are in
the queue, and links they send meanwhile are saved and process on approval. Keep
the `{admin}` placeholder working at both call sites. Give the email prompt and
blocked message the same treatment — each names a next step, or plainly states
there is not one.

**Brand fix, in scope for the strings you are already touching:** the email prompt
says "VIG"; the product is **Ownix** everywhere in the web UI. Fix that word in
these strings. Do not widen this into a repo-wide rename — that is a separate,
un-issued task.

**This copy is only true once #449 has landed.** If you are implementing this
slice without #449 in the tree, say so in your summary rather than shipping a
message that lies.

**Regression clause:** copy only — no new call sites, no logic changes.

**Tests:** update whatever in `tests/test_webhook.py` asserts on the old strings.

### #450 — pending sessions get the preview dashboard + queue banner

**Current state — the cookie is the blocker.** `_login_telegram_user`
(`src/api/auth.py:72`) calls
`response.delete_cookie("ownix_preview", path="/", secure=...)` on **every**
Telegram login, approved or not. `isRestrictedRequest`
(`web/lib/restricted/server.ts:31`) short-circuits on `if (!hasPreviewCookie) return false`,
so a logged-in pending user is never restricted and the dashboard layout's
preview wiring never engages. `InviteGate` (`web/components/shell/invite-gate.tsx:171`)
then renders `<GateScreen status="pending" />` (`invite-gate.tsx:276`, component at
`invite-gate.tsx:43`) — the dead wall.

**Fix — backend.** Keep (or re-mint) `ownix_preview` at login when the user is
**not** approved; keep deleting it for approved users so an approved session is
never trapped in the preview corpus. The cookie's canonical value is `1` and the
route that normally sets it is `web/app/restricted/route.ts` — match its
name/value/path exactly.

The rest of `isRestrictedRequest` already handles this correctly: with a cookie
**and** a session it calls `fetchAuthStatus`, and pending/blocked resolve to
`'unapproved'` → restricted. **Do not change that function.**

**Fix — frontend.** In `InviteGate`, the `status === 'pending'` branch renders
`children` plus a queue-status banner instead of `<GateScreen status="pending" />`.
`blocked` keeps `<GateScreen status="blocked" />`. The `needsEmail` `EmailModal`
branch (`invite-gate.tsx:279`) is unchanged — a pending user with no email still
gets the modal first. Note the existing `restricted` prop and its early return
(`invite-gate.tsx:173, 221`): the layout already passes a restricted flag, so
compose with it rather than duplicating it.

Banner copy (settled, use verbatim):

> You're in the queue — approval usually within a few hours; you'll get a Telegram
> hello. Meanwhile: install the app, send the bot your first link.

`DESIGN.md` is normative: plate ladder, WCAG-AA contrast, `prefers-reduced-motion`
honored. **Do not use signal orange for the banner** — signal always means "act
here", and this is status, not an action.

**Two existing tests assert the behavior this slice inverts — update them, do not
delete them:**

- `tests/test_preview_api.py:575` — `test_pending_login_deletes_preview_cookie`
  asserts a pending login *deletes* the cookie. Invert it; leave
  `test_approved_login_deletes_preview_cookie` (`:566`) passing as-is.
- `web/components/shell/invite-gate.test.tsx:117` — "shows the pending screen
  instead of dashboard content for pending users". Rewrite for the new behavior.

**Regression clause:** an approved user's cookie is still deleted at login and
they see real data — no preview-corpus regression. A blocked user still sees the
blocked wall. Every write action inside the preview stays blocked by the existing
restricted-mode chrome.

**Tests:** the two above, plus RTL coverage of the pending / blocked / approved
branches in the existing colocated `invite-gate.test.tsx`.
`web/lib/restricted/server.test.ts` must still pass untouched.

## Hard constraints

- **No commits, no pushes, no PRs, no branch creation.** Working tree only.
- Scope fence: touch only the files named above. Do not refactor unrelated code in
  a file you opened for one fix. Do not rename `VIG` → `Ownix` outside the three
  invite strings in #452.
- Do not add a dependency for any of this.
- Do not weaken or delete an existing test to make a new behavior pass — the two
  tests named in #450 are to be **rewritten** for the new expectation.
- Migrations are append-only. Never renumber, edit, or reorder an existing entry
  in `_MIGRATIONS`.
- Commands (from `CLAUDE.md`), **never through the `rtk` hook** — see
  `.claude/rules/rtk-tests.md`:
  - `python -m pytest tests -q` (or per-file: `python -m pytest tests/test_webhook.py -q`)
  - `ruff check src/`
  - from `web/`: `npm run test:run`, `npm run lint`, `npm run build`

## Deliverable

Uncommitted working-tree changes implementing #449, #451, #452 and #450, with
regression tests matching each issue's own acceptance criteria, plus a short
per-issue summary of what was done and anything that blocked you — especially any
place where the migration rebuild or the cookie change forced a decision this
document did not pin down.
