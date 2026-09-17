# Codex prompt — implement the admin/viewer visibility plan (2026-09-17)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

There is no GitHub issue batch behind this prompt — the plan below is the
full, already-detailed source. Its own per-task Steps (write failing test →
verify it fails → implement → verify it passes) are the definition of done
for each slice; treat them the way you'd treat an issue's acceptance
criteria.

## Required context — read these first, in this order

1. `docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md` — the full
   implementation plan. It is authoritative over anything summarized below;
   its 9 tasks already contain exact `path:line` references, real code, and
   real tests. Read it in full before touching anything.
2. Root `CLAUDE.md` — repo layout, test/lint commands.
3. `web/CLAUDE.md` — frontend component layout conventions (kebab-case,
   colocated `.test.tsx`, no barrel files) for the tasks touching
   `web/components/`.
4. The concrete files each task changes (the plan names exact line ranges
   for each): `src/config.py`, `src/auth/middleware.py`, `src/api/auth.py`,
   `src/api/jobs.py`, `src/services/gemini.py`, `src/services/ops_bot.py`
   (read-only — reuse its existing functions, don't modify it),
   `web/components/shell/invite-gate.tsx`, `web/components/shell/sidebar.tsx`,
   `web/app/(dashboard)/layout.tsx`,
   `web/app/(dashboard)/newsletter-digest/page.tsx`,
   `web/app/(dashboard)/prompts/page.tsx`.

## Key decisions already made (do not relitigate)

- **No new `role` column, no migration.** The codebase already has a
  single-operator admin concept: `settings.OPERATOR_CHAT_ID`, already
  special-cased in `database.get_user_status`/`set_user_status`
  (`src/db/users.py`). Add `Settings.is_operator(chat_id)` and use it
  everywhere "is this an admin" needs answering. Do not invent a parallel
  role/permission system.
- **One synthetic account, two doors.** The "viewer" backdoor is a single
  real `users` row at `settings.VIEWER_LOGIN_USER_ID` (`-900_000_002`),
  reachable two ways that must resolve to the *same* row: its own
  email+password login (mirroring the existing `reviewer_login()` in
  `src/api/auth.py` almost verbatim — same shape, same
  `hmac.compare_digest`, same `rate_limit.enforce`), and a same-tab toggle
  that substitutes an operator's *effective* acting id to that row via a
  short-lived `ownix_view_as` cookie read in `SessionMiddleware`. Because
  both paths land on the same row, it starts empty and accumulates real
  submitted jobs as it's used — do not create two separate accounts.
- **Newsletter Digest is the only hidden feature.** Gate it with a 404, not
  a 403, at `/api/newsletter*` — a hidden route shouldn't confirm its own
  existence to a member probing the URL. Docs (`/doc-parser`,
  `/api/parsed`) and Recipes (`/prompts`, `/api/templates`) must **not** be
  gated — Docs is already a core builder feature, and Recipes gets its
  actual bug fixed instead of being hidden.
- **Recipes' bug is unrelated to any role/visibility work.**
  `_resolve_job_template` in `src/api/jobs.py` only accepts a built-in
  template name or the literal `"freestyle"` — it never looks up a saved
  user template. Fix: when the name isn't a built-in, look it up via
  `database.get_user_template_by_name(chat_id, template)` and, if found,
  resolve it to `("freestyle", recipe["extra_instructions"])` — this
  reuses the freestyle path both `_build_prompt` and `_build_audio_prompt`
  (`src/processors/enrichment.py`) already handle correctly; no changes
  needed in `enrichment.py` itself.
- **The Gemini alert reuses existing infrastructure, adds none.** Wrap
  `_call_with_fallback` in `src/services/gemini.py` with an in-memory
  rolling failure window, and on threshold fire through
  `src/services/ops_bot.py`'s already-shipped `admin_chat_ids()` +
  `send_ops_message()` (the same channel invite-approval notifications
  already use). Do not add Sentry, Datadog, or any new dependency.
- **Cookie/session conventions are fixed, mirror them exactly.** Every
  `response.set_cookie(...)` call in this batch uses
  `httponly=True, secure=settings.SESSION_COOKIE_SECURE, samesite="lax",
  path="/"` — copy the existing calls in `src/api/auth.py`
  (`reviewer_login`, `telegram_login`), don't invent different cookie
  flags.
- **Respect the `database` facade.** `src/database.py` re-exports
  `src/db/*.py` — always call `database.get_user_template_by_name(...)`
  etc., never import `src/db/users.py` or `src/db/templates.py` directly
  from API/service code. `get_user_template_by_name` is already
  re-exported; nothing to add there.

## Work order

Tasks 1→4 are strictly sequential (each builds on the last — Task 3 edits
the same `SessionMiddleware.dispatch` block Task 5's gate lives inside).
Tasks 5→6 depend on Task 3 already having landed. Tasks 7→8 (Recipes) and
Task 9 (Gemini alert) are fully independent of everything else and of each
other — do them in any order, including in parallel with the rest, but keep
each task's own commit-sized diff self-contained (this prompt produces one
uncommitted working tree, not per-task commits — see Deliverable).

### Task 1 — `Settings.is_operator()` + viewer-login settings

Plan section: "Task 1" in the required-context doc. Add the method next to
`Settings.export_blocked` in `src/config.py`, and the four new
`VIEWER_LOGIN_*` settings next to the existing `REVIEWER_LOGIN_*` block.
Write `tests/test_config.py` (create it if it doesn't exist) with the four
test cases the plan specifies.

### Task 2 — Viewer login endpoint

Plan section: "Task 2". Add `ViewerLoginPayload` + `viewer_login()` to
`src/api/auth.py`, placed directly after `reviewer_login()` — same
structure, same `_resume_deletion_if_stuck` reuse, same cookie-setting
call. Add `"/api/auth/viewer-login"` to `_OPEN_API_PATHS` in
`src/auth/middleware.py`. Tests go in `tests/test_auth.py`, alongside the
existing `test_reviewer_login_*` tests in the same class.

### Task 3 — View-as toggle (middleware substitution + endpoints)

Plan section: "Task 3". This is the load-bearing task — read it twice.
Define `VIEW_AS_COOKIE = "ownix_view_as"` in `src/auth/middleware.py`,
attach `real_id` to `request.state.user` unconditionally, substitute `id`
to `settings.VIEWER_LOGIN_USER_ID` only when the real id is the operator
**and** the cookie is present. The plan's replacement code block for the
tail of `SessionMiddleware.dispatch` also includes the Newsletter Digest
404 gate (`path.startswith("/api/newsletter")`) — that's deliberate, land
it here in the same edit rather than as a separate change, per the plan's
own note. Add `POST`/`DELETE /api/auth/view-as` to `src/api/auth.py`,
gated on `settings.is_operator(real_id)` read from
`request.state.user["real_id"]` (not `["id"]` — a currently-toggled admin
must still be able to call `DELETE` to exit).

### Task 4 — `/api/auth/me` fields + frontend toggle

Plan section: "Task 4". Extend `me()`'s response in `src/api/auth.py` with
`is_admin`/`can_view_as`/`viewing_as`. Extend `InviteUser` in
`web/components/shell/invite-gate.tsx` with the same three optional
fields. Create `web/components/shell/view-as-switch.tsx` — model its
placement and gating pattern on the existing
`web/components/ui/dev-persona-switch.tsx` (same "floating control
rendered outside `InviteGate` in the dashboard layout" shape), but gate on
the real session's `is_admin`/`viewing_as`, not a `NODE_ENV`/mock-build
flag. Render it in `web/app/(dashboard)/layout.tsx` next to
`<DevPersonaSwitch />`. Colocated `.test.tsx` per the plan's Step 6.

### Task 5 — Backend gate test for Newsletter Digest

Plan section: "Task 5". The gate itself already landed in Task 3 — this
task is test-only. Check whether `tests/test_api_newsletter_digest.py`
already exists; if so add the two tests there against its existing
fixture, otherwise add them to `tests/test_auth.py`'s `auth_client` class
(stub route included in the plan).

### Task 6 — Frontend nav filter + page guard for Newsletter Digest

Plan section: "Task 6". Add `ADMIN_ONLY_HREFS`/`visibleNav()` to
`web/components/shell/sidebar.tsx`, filter both render sites (collapsed
rail and expanded drawer) through it. Add the client-side redirect guard
to `web/app/(dashboard)/newsletter-digest/page.tsx` — read that file's
current imports first and reuse whichever of `useSessionUser`/`useRouter`/
`useEffect` it's missing, don't duplicate an import it already has.
Extend `web/components/shell/sidebar.test.tsx` reusing its existing
`useSessionUser` mock pattern — don't introduce a second, differently
shaped mock in the same file.

### Task 7 — Recipes: `_resolve_job_template` resolves saved recipes

Plan section: "Task 7". Make `_resolve_job_template` `async`, add the
`chat_id` parameter, add the recipe-lookup branch. Update **both** call
sites in `src/api/jobs.py` (`_create_pipeline_job` around line 263 and
`enrich_job` around line 804 — confirmed current as of this prompt) to
`await` it and pass `chat_id`. Before finishing this task, grep
`_resolve_job_template` across `src/` to confirm there is no third caller
this prompt missed. Tests: check whether `tests/test_api_jobs.py` exists
under that name (`find tests -iname "*jobs*"`); if the jobs API tests live
under a different filename, add there instead and note the actual
filename in your summary.

### Task 8 — "Apply to a link" UI on the Recipes page

Plan section: "Task 8". Depends on Task 7 (the backend must resolve a
recipe name before this UI's POST does anything useful). Read the current
template-list render loop in `web/app/(dashboard)/prompts/page.tsx` first
to find where user (non-builtin) templates are mapped, then add the
`ApplyRecipeForm` component and mount it per row. Posts directly to the
existing `/api/jobs` endpoint — no new backend route.

### Task 9 — Gemini failure-rate alert via the ops bot

Plan section: "Task 9". Fully independent of every other task — safe to
do first, last, or in parallel. Add the rolling-window state and
`_maybe_alert_gemini_failures()` to `src/services/gemini.py`, hook it into
`_call_with_fallback`'s failure path, import `admin_chat_ids`/
`send_ops_message` **lazily inside the function** (not at module top) —
this matches the plan's stated import-order caution, not because of an
actual circular import (there isn't one; `ops_bot.py` doesn't import
`gemini.py`), but keep it lazy as written. Run
`python -m pytest tests/test_gemini_client.py tests/test_gemini_photo.py -v`
after, not just the new tests — confirm nothing else in that file broke.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Stay inside the files named in Required Context and each task's section
  above. Don't touch unrelated routes in a file you're already editing for
  one task (e.g. editing `src/api/auth.py` for Tasks 2–4 must not touch
  the GitHub/Google OAuth routes living in the same file).
- Do not add a database migration or a `role`/permission column — rejected
  above, `Settings.is_operator()` is the only mechanism.
- Do not add a new monitoring dependency for Task 9 — `ops_bot.py`'s
  existing functions only.
- Follow each task's TDD order exactly as the plan writes it: write the
  failing test, run it and confirm the failure mode matches what the plan
  says to expect, then implement, then confirm green. Don't skip the
  "verify it fails" step.
- Backend: `python -m pytest tests -q` (or scoped with `-k`), never through
  the `rtk` hook (`.claude/rules/rtk-tests.md`). Lint: `ruff check src/`
  (line-length 100, py311).
- Frontend (`web/`): `npm run test:run`, `npm run lint`.

## Deliverable

Uncommitted working-tree changes implementing all 9 tasks from
`docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md`, each task's
own tests passing, plus a short summary per task of what was done and
anything that blocked or diverged from the plan (a test file that didn't
exist under the expected name, a line number that had already moved, a
mock pattern in an existing test file that didn't match what the plan
assumed) — name the actual file/line you used instead, don't silently
paper over the difference.
