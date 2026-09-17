# Admin/Viewer Visibility Runbook

Operational guide for the feature merged in PR #639 (`main` at `dcb2489`,
2026-09-17): the operator's admin identity, the viewer backdoor (standalone
login + in-dashboard toggle), the Newsletter Digest admin gate, and the
Gemini failure-rate alert. Full design/decisions:
`docs/superpowers/plans/2026-09-17-admin-viewer-visibility.md`. There is no
new `role`/permission column anywhere in this system — every "admin" check
below is `Settings.is_operator()`, which is just `OPERATOR_CHAT_ID` compared
against the acting identity.

## 1. The operator identity

`OPERATOR_CHAT_ID` (an existing env var, not new to this PR) is now load-bearing
for more than it used to be. Before this PR it only affected
`database.get_user_status`/`set_user_status` (auto-approve) and
`Settings.export_blocked` (whose Drive/Sheets export goes where). As of this
PR it also gates:

- Whether `/api/auth/me` reports `is_admin: true` (drives the frontend nav
  filter — see §4).
- Whether the admin-only view-as toggle (§2) is reachable at all.
- Whether `/api/newsletter*` is reachable (§4).

**If `OPERATOR_CHAT_ID` is unset, every one of those fails closed** — nobody
is `is_operator()`-true, so nobody sees the admin-only surfaces, including
whoever would otherwise be the operator. This is a deliberate reversal from
an earlier version of this PR that failed *open* in that case (an approved
member could reach Newsletter Digest with no operator configured at all) —
a Codex adversarial review caught it before merge; see the plan doc's
Task 5/adversarial-review notes. **Set `OPERATOR_CHAT_ID` before relying on
any admin-only surface in a new deployment** — an unconfigured environment
isn't "everything open," it's "the admin surfaces don't exist yet."

## 2. The viewer backdoor

One synthetic `users` row, `VIEWER_LOGIN_USER_ID` (default `-900_000_002` in
`src/config.py`; negative and far from any real Telegram chat id on
purpose — real ids are always positive). Two ways to become it, both landing
on the same row so it never drifts and accumulates real submitted jobs as
it's used:

### Env vars (`src/config.py`)

| Var | Purpose |
|---|---|
| `VIEWER_LOGIN_ENABLED` | Master switch. `False` by default — nothing below works until this is `True`. |
| `VIEWER_LOGIN_EMAIL` | Must be set (non-empty) for either access path to work — the toggle 404s without it, matching the standalone login's own requirement. |
| `VIEWER_LOGIN_PASSWORD` | Only used by the standalone login form (`POST /api/auth/viewer-login`). Rotate it the same way `REVIEWER_LOGIN_PASSWORD` gets rotated — this is the same class of temporary-access credential. |
| `VIEWER_LOGIN_USER_ID` | The synthetic chat id. Change it only if `-900_000_002` collides with something (it shouldn't — see above). |

### Path A — standalone login

`POST /api/auth/viewer-login` with `{email, password}` matching
`VIEWER_LOGIN_EMAIL`/`VIEWER_LOGIN_PASSWORD`. Mints a real `vig_session`
cookie for the viewer account — open it in a second browser profile/incognito
window to watch it side by side with your own admin session.

### Path B — in-dashboard toggle

Only reachable by the real operator (`Settings.is_operator(real_id)` on the
*real*, pre-substitution session — see `src/auth/middleware.py`'s
`real_id`/`user["id"]` split). `POST /api/auth/view-as` sets an
`ownix_view_as` cookie; every subsequent request on that browser then acts as
the viewer account (`request.state.user["id"]` becomes
`VIEWER_LOGIN_USER_ID`, with the real operator id preserved as
`request.state.user["real_id"]` for the toggle's own auth checks).
`DELETE /api/auth/view-as` clears it. The floating "View as member" /
"Exit viewer mode" control (`web/components/shell/view-as-switch.tsx`) is the
UI for this — same placement pattern as the existing mock-mode
`DevPersonaSwitch`, but gated on the real session, so it also works in
production for the real operator.

### Turning it off

Flipping `VIEWER_LOGIN_ENABLED` back to `False` takes effect **immediately**,
not just for new logins/toggles — this took two review passes to get right:

- A stale `source: "viewer_login"` session (from Path A) is rejected on its
  next request (`SessionMiddleware`'s disabled-session check, matching the
  existing `REVIEWER_LOGIN_ENABLED` treatment).
- An operator who is *currently* toggled in (Path B, cookie still set) stops
  being substituted on their very next request — the middleware's
  substitution condition checks `VIEWER_LOGIN_ENABLED` directly, so a leftover
  `ownix_view_as` cookie can't keep acting as a live backdoor after the flag
  flips off. (This was a real gap an adversarial review caught: the
  disabled-session check runs *before* the toggle substitution and only ever
  sees the real operator's own session, so it could never have caught a
  stale cookie on its own.)

## 3. Newsletter Digest admin gate

`/api/newsletter*` (both the API and the `/newsletter-digest` nav item) is
the one feature this PR hides from non-admins — see §1 for why "no operator
configured" also means "hidden," not "open." The gate returns a plain `404`,
not `403`, so a member probing the URL directly can't even tell the route
exists.

Everything else this PR touches (Docs/`doc-parser`, Recipes/`prompts`) stays
open to every approved user — those were explicitly kept out of scope; see
the plan doc's Task 5/6 notes for why Newsletter Digest specifically was the
one picked.

## 4. Gemini failure-rate alert

`src/services/gemini.py` now tracks Gemini call failures in a rolling
5-minute window (`_gemini_failures`, `_GEMINI_FAILURE_WINDOW_SECONDS`,
`_GEMINI_FAILURE_THRESHOLD = 5`). At 5+ failures in that window, it sends one
message through the **existing** ops-admin Telegram channel
(`src/services/ops_bot.py`'s `admin_chat_ids()`/`send_ops_message()` — the
same channel that already delivers invite-approval cards), then goes quiet
for `_GEMINI_ALERT_COOLDOWN_SECONDS` (60 minutes) before it can fire again.

What you'll see: `⚠️ Gemini unavailable N times in the last 5 minutes. Latest
error: <message>` in the ops bot chat. No new bot, no new channel to
configure — if you already get invite-approval cards, you'll get this too.

**This state is in-memory, per-process, and resets on deploy/restart.** It's
a best-effort operational nudge, not a source of truth — don't build
alerting-on-alerting around it, and don't be surprised if a redeploy during a
real outage resets the counter. If `admin_chat_ids()` is empty (no
`OPS_ADMIN_CHAT_IDS` configured), the alert is silently skipped and logged as
`gemini.failure_alert_no_admins` — check that env var is actually set if
you're expecting these and never see one.

## 5. Recipes: "freestyle" is a reserved name

Unrelated to the admin/viewer work above, but shipped in the same PR:
`_resolve_job_template` (`src/api/jobs.py`) now resolves a saved Recipe by
name instead of only accepting built-ins, closing a previously-dead feature
(no apply path existed anywhere before this). One consequence:
`create_template`/`_require_user_template` (`src/api/templates.py`) now
reject `"freestyle"` as a Recipe name outright (`409`/`403`), since
`_resolve_job_template` already treats that literal string as the built-in
freestyle mode and would never reach a same-named saved Recipe. If a Recipe
named `freestyle` already existed in a database from before this PR, it's
still usable via the old paths that read it directly — it just can't be
created fresh or fetched by that name through `_resolve_job_template` going
forward.

## Gotchas

- **An unconfigured `OPERATOR_CHAT_ID` doesn't mean "no restrictions" —
  it means "no admin exists yet."** See §1. This is the opposite of how
  `Settings.export_blocked` treats the same unset value (it fails *open*
  there) — the two functions deliberately disagree on purpose, because one
  is a data-export default and the other is a visibility gate for a feature
  this PR exists to hide. Don't "fix" the newsletter gate to match
  `export_blocked`'s precedent — that was tried and reverted (see the plan
  doc's Task 5 history) after an adversarial review flagged it as a real
  fail-open risk.
- **The view-as toggle only works from the operator's own real session.**
  `start_view_as`/`stop_view_as` check `request.state.user["real_id"]`, not
  `["id"]` — deliberately, so a currently-toggled-in session can still call
  `DELETE /api/auth/view-as` to exit. If you're testing this and the toggle
  endpoint 403s unexpectedly, check which identity you're actually
  authenticated as, not just whether *a* session cookie is present.
- **The viewer account is real and durable, not a mock.** Both access paths
  `upsert_user`/`set_user_status("approved")` the same row. It shows up in
  admin tooling (`/users` in the ops bot, the dashboard's own user-facing
  surfaces if it ever submits a job) like any other approved account. If you
  want its accumulated test data gone, delete it the same way any other
  account gets deleted — there's no separate cleanup path for it.
