# Codex prompt — implement issues #618–#624 (non-Telegram identity: GitHub/Google/email sign-in, cross-provider merge, and a DM-only Discord channel)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/adr/0061-non-telegram-identity-and-discord-dm-channel.md` — the
   authoritative decision record for this whole batch. Its **Decision** and
   **Considered and rejected** sections override any looser paraphrase below
   if they disagree. Two hard scope fences from it: this is a **narrow
   slice** of `docs/plans/2026-08-03-ownix-intake-channels-extension-share.md`'s
   Phase 9 — do **not** add `users.id`, do **not** migrate any `chat_id`
   ownership off `jobs`/`tags`/`spaces`/etc. (that's Phase 9b, deferred). Do
   **not** build Discord guild/server support or request the privileged
   `MESSAGE_CONTENT` intent — Discord is DM-only in this batch.
2. `docs/adr/0030-export-gate-and-oauth-credential-model.md` (its
   2026-09-10 addendum especially) — the existing Google OAuth connection
   (`src/api/google_oauth.py`, `/api/google/*`) authorizes Drive/Sheets
   **export** for a Tenant that already exists. #619's Google **login** is a
   **fully separate OAuth client, scopes, and callback route** — never
   touch `/api/google/*`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`, or the export
   flow's state table.
3. `docs/adr/0031-invite-gate-and-onboarding.md` (its 2026-09-10 addendum) —
   the invite gate (`pending` until Operator approval) applies identically
   regardless of signup channel. Its "no SMTP infra" rejection premise is
   stale — `src/services/email.py` already sends transactional mail.
4. `CLAUDE.md` (repo root) — module layout and exact test/lint commands.
   Never run pytest through the `rtk` hook (`.claude/rules/rtk-tests.md`).
5. The concrete seams each issue builds on (current as of this writing —
   find by name if line numbers have drifted):
   - `src/database.py:228-239` — the `users` table (`tg_id INTEGER PRIMARY
     KEY`, `status` CHECK'd `pending|approved|blocked|deleting`). `:2593`
     `upsert_user(*, tg_id, first_name, username=None, last_name=None,
     photo_url=None)`; `:2620` `get_user_status(tg_id) -> UserStatus`;
     `:2630` `get_user(tg_id) -> dict | None`; `:2643` `set_user_status`;
     `:2672` `set_user_email(tg_id, email)`. All keyed on the plain integer
     `tg_id` — nothing here changes shape, it just starts receiving
     synthetic negative ids too (see decision below).
   - `src/database.py` end-of-file migration convention — 45 `_MIGRATIONS.append(...)`
     calls, always appended at the literal end of the file (see the
     "2026-09-08 incident note" comment there), each guarded with a
     `PRAGMA table_info` / `sqlite_master` existence check because migration
     tests replay the full chain from old synthetic fixtures. Mirror this
     exactly for the new `identity_links` table and the `users.email`
     partial unique index — do not touch any existing numbered migration.
   - `src/auth/session.py:156-177` — `_mint_token(prefix, value, ttl)` /
     `_redeem_token(prefix, token)`: single-use, atomic-GETDEL, TTL'd opaque
     tokens (Redis in prod, in-memory dict for local dev via `_use_memory()`).
     `mint_handoff`/`redeem_handoff` (`:180-195`) and
     `mint_dashboard_handoff`/`redeem_dashboard_handoff` (`:198-213`) are
     thin wrappers over these two. **Every new token this batch needs (OAuth
     `state`, the magic-link token, the Discord pairing code) is another
     thin wrapper over the same two functions with a new prefix — do not
     invent a second token store.**
   - `src/auth/extension_tokens.py` (whole file) — `mint_pairing_code`/
     `redeem_pairing_code` (`:45-58`) is the **exact** pattern #623's Discord
     pairing code mirrors: a one-line wrapper calling
     `session_store._mint_token`/`_redeem_token` with a new prefix. Copy this
     shape, not the token/hash-storage machinery further down that file
     (that part is specific to the extension's long-lived bearer token,
     which Discord pairing does not need — pairing is single-use only).
   - `src/api/google_oauth.py` (whole file) — the exact `connect` → redirect
     to provider → `callback` → `httpx.AsyncClient().post(token_url, data={...})`
     → use the token shape for #618/#619's GitHub/Google **login** routes.
     Do not reuse its `store_google_token`/`google_oauth_states` — those are
     export-specific. Use `session_store._mint_token`/`_redeem_token` for
     the login flows' `state` param instead (no new SQL table needed for
     that).
   - `src/api/auth.py` (whole file) — `_login_telegram_user` (`:65-117`) is
     the canonical "mint a session for a {tg,synthetic} id" shape: calls
     `database.upsert_user`, resumes a stuck deletion
     (`_resume_deletion_if_stuck`), builds `session_user` with the existing
     field names (`id`, `first_name`, `username`, `photo_url`, optional
     `source`), calls `session_store.mint(session_user)`, sets the
     `ownix_preview` cookie based on `get_user_status`. **Every new login
     path in this batch (#618, #619, #620) produces a `session_user` dict in
     exactly this shape** — map each provider's own fields into
     `first_name`/`username`/`photo_url` (do not add provider-specific
     session fields).
   - `src/auth/middleware.py` (whole file) — `_OPEN_API_PATHS` (`:20-32`) is
     where a route that must work **before any session exists** gets listed
     (e.g. `/api/auth/telegram`). The new GitHub/Google-login/email-magic-link
     `connect`+`callback`/`request`+`redeem` routes go here — they are
     establishing the *first* session, unlike `/api/google/connect` (export)
     which requires `request.state.user` already. The Discord
     pairing-code-mint endpoint (#623) is **not** added here — it requires an
     existing, approved session, same as any ordinary `/api/*` route.
   - `src/utils/validators.py:19` — `normalize_email(email) -> str | None`.
     Use this everywhere an email is compared or stored in this batch — the
     existing `PUT /api/auth/email` route (`src/api/auth.py:435-462`) already
     does, mirror it.
   - `src/services/email.py` (whole file) — `send_welcome_email(user)` is
     the existing transactional-send shape (SMTP config check, MX-lookup
     domain validation via `_domain_accepts_mail_sync`, `EmailMessage`). #620's
     magic-link email is a new function in this same file following the same
     shape (subject/from/to/plaintext body), not a new email-sending module.
   - `src/intake/models.py` (whole file) — `IntakeActor`/`IntakeMessage`/
     `IntakeResponse`, `SCHEMA_VERSION`. `src/intake/router.py:35`
     `async def handle(msg: IntakeMessage) -> IntakeResponse`.
   - `src/channels/telegram/adapter.py` (whole file) — the exact adapter
     shape #624's Discord adapter mirrors: `update_to_intake_message(update)
     -> IntakeMessage | None` and `async def render_response(chat_id,
     response) -> None`. Note its docstring: this Telegram adapter is a
     conversion helper **not yet wired into the live webhook dispatch loop**
     — that's a separate, still-open concern for Telegram and out of scope
     here. Discord has no existing dispatch loop to leave alone, so #624's
     Discord adapter **must** be the live dispatch path for paired DMs (call
     `router.handle()` directly from the Gateway message handler).
   - `src/worker.py:412-458` — `loop()` is the one long-running coroutine in
     this codebase (`while True: dequeue → dispatch`), started via
     `asyncio.run(loop())` in `main()`. #622's Discord Gateway connection
     becomes a **second** coroutine run concurrently via
     `asyncio.gather(loop(), discord_gateway.run(), ...)` inside `main()` —
     do not fold Gateway logic into the queue-consumption `while True` itself.
   - `src/config.py:31,47-50,78-82,123-129` — existing `Settings` fields
     (`GITHUB_TOKEN` is an unrelated repo-enrichment PAT — do not touch or
     confuse it with the new GitHub OAuth login client; `GOOGLE_OAUTH_*` is
     the export client — do not touch). Add: `GITHUB_OAUTH_CLIENT_ID`,
     `GITHUB_OAUTH_CLIENT_SECRET`, `GITHUB_OAUTH_REDIRECT_URI`,
     `GOOGLE_LOGIN_CLIENT_ID`, `GOOGLE_LOGIN_CLIENT_SECRET`,
     `GOOGLE_LOGIN_REDIRECT_URI`, `DISCORD_APPLICATION_ID`,
     `DISCORD_BOT_TOKEN` — these exact names, they match
     `scripts/setup-nontelegram-oauth.sh` (already in the repo) which is how
     a human provisions the real credentials.
   - `src/main.py:203-215` — `app.include_router(...)` block; register any
     new router here in the same style.
6. GitHub issues #618–#624 (`gh issue view <n> --repo Leon-87-7/ownix`) —
   each carries its own agent-brief comment with acceptance criteria; treat
   those as the per-issue definition of done.

## Key decisions already made (do not relitigate)

- **One shared identity-linking table, additive only.** New table
  `identity_links(provider TEXT, subject TEXT, owner_id INTEGER, verified
  INTEGER, created_at, PRIMARY KEY(provider, subject))`. `provider` is one
  of `"github"`, `"google"`, `"email"`, `"telegram"` — Discord is
  deliberately **not** a value here at pairing time in the sense of
  originating a session; see #623's own row shape below. This table is
  purely additive — no existing table changes ownership.
- **Synthetic owner id, not a new PK.** A non-Telegram signup mints a
  synthetic id via `-secrets.randbelow(2**31)` (or equivalent — any
  negative integer clearly outside Telegram's positive `tg_id` space) and
  passes it as `tg_id` into the **existing** `upsert_user`/`get_user_status`/
  etc. unchanged. `users.tg_id` now means "owner id," not literally a
  Telegram id — this is a deliberate, documented misnomer (ADR-0061), not a
  bug to "fix" by renaming the column in this batch.
- **One shared helper owns "resolve or create an owner for this login."**
  Add `src/auth/identity.py` with
  `async def resolve_owner(provider: str, subject: str, *, email: str | None, email_verified: bool) -> int`.
  #618 (GitHub, first provider) implements it to: look up
  `identity_links` for `(provider, subject)` — if found, return its
  `owner_id`; otherwise mint a synthetic owner id, `upsert_user(tg_id=owner_id, ...)`,
  insert into `identity_links`, return it. **#619 and #620 call this same
  function unchanged** — do not duplicate its body per provider. #621 is
  the slice that edits *only* this function's internals to add the
  verified-email-match branch (see below) — every provider benefits the
  moment #621 lands, with no per-provider code changes.
- **Login OAuth is not export OAuth.** #619's Google login uses
  `GOOGLE_LOGIN_CLIENT_ID/SECRET/REDIRECT_URI` and scope
  `openid email profile` only, on new routes under `/api/auth/google/*`.
  Never import from or write to anything under `src/api/google_oauth.py`,
  `google_oauth_tokens`, or `google_oauth_states`.
- **Session field shape is fixed.** Every new login mints
  `{"id": owner_id, "first_name": ..., "username": ..., "photo_url": ...,
  "source": "<provider>"}` — map GitHub's `login`→`username`,
  `avatar_url`→`photo_url`, `name`→`first_name`; Google's `given_name`→
  `first_name`, `picture`→`photo_url`, `email`→ also passed separately to
  `resolve_owner`. No new session fields.
- **Invite gate is provider-agnostic.** After `resolve_owner` returns (new
  or existing), call the existing `database.get_user_status`/`set_user_email`
  exactly as `_login_telegram_user` does. A first-time signup with a
  provider-verified email calls `set_user_email` immediately (skipping the
  one-time in-app ask Telegram-only users still see) — mirror
  `PUT /api/auth/email`'s `notify_operator_invite` call
  (`src/api/auth.py:435-462`) so the Operator still gets pinged.
- **Merge rule (#621): verified only, no exceptions.** In `resolve_owner`,
  before minting a new owner id for an unseen `(provider, subject)`: if
  `email` is not None and `email_verified` is True, look up an existing
  `users` row by that normalized email; if found, insert the new
  `identity_links` row pointing at *that* row's `tg_id` and return it — do
  **not** call `upsert_user` again, do **not** touch `status`. If
  `email_verified` is False (or email is None), always mint a new owner id
  — never merge on an unverified claim. Guard the concurrent case with a
  **partial unique index** `CREATE UNIQUE INDEX IF NOT EXISTS
  idx_users_email_nocase ON users(email COLLATE NOCASE) WHERE email IS NOT NULL`
  (SQLite partial index; mirror the guarded-migration pattern at the end of
  `src/database.py`) and catch the resulting `IntegrityError` in
  `resolve_owner` as "someone else just won the race — look the row up
  again and attach to it" rather than a bare failure.
- **Discord is pairing-only, never a login.** #622's Gateway connection
  produces zero identity_links rows by itself. #623 is the **only** writer
  of `identity_links` rows with `provider="discord"` — it always requires
  an existing `owner_id` (from the caller's current session) and a
  short-TTL pairing code redeemed via `session_store._mint_token`/
  `_redeem_token` (new prefix, e.g. `discord_pairing:`), exactly mirroring
  `src/auth/extension_tokens.py:45-58`'s `mint_pairing_code`/
  `redeem_pairing_code`. A DM from an unrecognized Discord user id must
  never call `resolve_owner` or `upsert_user`.
- **Discord Gateway lives inside the worker process, DM intents only.**
  `src/worker.py`'s `main()` runs the Gateway client concurrently with the
  existing `loop()`, not instead of it. Request only the intents needed for
  DMs (no `GUILD_MESSAGES`, no privileged `MESSAGE_CONTENT` for guilds).
  **Adding a Discord Gateway client library (e.g. `discord.py`) as a new
  runtime dependency in `requirements.txt` is expected and approved** —
  hand-rolling the Gateway wire protocol (heartbeats, resume, opcodes) over
  raw websockets would be reinventing what the library already solves;
  `httpx` alone is not a substitute for a Gateway connection.
- **Paired Discord DMs are the live dispatch path.** Unlike the existing
  (not-yet-wired-in) Telegram adapter, #624's Discord adapter is called
  directly from the Gateway's on-message handler for every DM from a
  snowflake that `identity_links` resolves to an `owner_id` — build
  `IntakeActor(user_id=owner_id, channel_id=f"discord:{snowflake}",
  channel_type="discord", legacy_chat_id=owner_id)` and call
  `router.handle()`.

## Nature of this batch & suggested sequencing

Cohesive feature, seven vertical slices, two independent tracks that both
depend on #618's foundation:

- **Spine:** #618 (identity table + `resolve_owner` + GitHub login + invite-gate
  parity). Everything else depends on this landing first.
- **Identity track:** #618 → {#619, #620} → #621.
- **Discord track:** #618 → #622 (independent of #619/#620) → #623 → #624.

If the single working-tree diff grows too large to review in one pass, hand
back the spine plus one complete track and clearly list which slices
remain — do not leave `resolve_owner` half-migrated (e.g. #621's merge
branch added but the unique index missing, or vice versa). State exactly
where you stopped.

## Work order

### #618 — GitHub OAuth sign-in (identity foundation)

- Migration (append at the true end of `src/database.py`, guarded per
  existing convention): create `identity_links` table.
- `src/auth/identity.py`: `resolve_owner(...)` per the decision above — this
  slice implements the naive form (no merge branch yet; that's #621).
- New routes on the existing `auth_router` (`src/api/auth.py`):
  `GET /api/auth/github/connect` (redirect to
  `https://github.com/login/oauth/authorize` with `state` minted via
  `session_store._mint_token("github_oauth_state:", ..., ttl=600)`,
  scope `read:user user:email`) and
  `GET /api/auth/github/callback` (redeem state, exchange `code` via
  `httpx.AsyncClient().post("https://github.com/login/oauth/access_token", ...)`,
  fetch `https://api.github.com/user` and `https://api.github.com/user/emails`
  to find the verified primary email, call `resolve_owner("github", str(github_user_id),
  email=..., email_verified=...)`, then mint the session exactly like
  `_login_telegram_user` does, then redirect to `/feed`).
- Add both routes to `_OPEN_API_PATHS` in `src/auth/middleware.py`.
- Add `GITHUB_OAUTH_CLIENT_ID`/`GITHUB_OAUTH_CLIENT_SECRET`/
  `GITHUB_OAUTH_REDIRECT_URI` to `src/config.py` and `.env.example` (near
  the existing `GOOGLE_OAUTH_*` block, clearly commented as the **login**
  client, distinct from `GITHUB_TOKEN`).
- Tests: `tests/test_auth.py` (or a new `tests/test_auth_identity.py`) —
  new GitHub signup lands `pending` with `users.email` auto-filled from the
  verified GitHub email and the Operator-notify path firing (mock
  `notify_operator_invite`); a second login from the same GitHub id resolves
  to the same `owner_id` (no duplicate row); existing Telegram login tests
  in `tests/test_auth.py` keep passing unchanged.

### #619 — Google OAuth sign-in, login-only (blocked by #618)

- Same shape as #618 but for Google: `GET /api/auth/google/connect` /
  `GET /api/auth/google/callback`, scope `openid email profile` only,
  token exchange against `https://oauth2.googleapis.com/token` and userinfo
  against `https://openidconnect.googleapis.com/v1/userinfo`. Uses
  `GOOGLE_LOGIN_CLIENT_ID`/`SECRET`/`REDIRECT_URI` — **never**
  `GOOGLE_OAUTH_*`. Calls the same `resolve_owner("google", google_sub, ...)`.
- Add both routes to `_OPEN_API_PATHS`.
- Add the three `GOOGLE_LOGIN_*` settings + `.env.example` entries, clearly
  commented as distinct from the export client above them.
- Tests: mirror #618's — new Google signup, repeat-login idempotency, and
  an explicit assertion that no code path in this slice imports or calls
  anything from `src/api/google_oauth.py` or touches `google_oauth_tokens`.

### #620 — Email magic-link sign-in (blocked by #618)

- `POST /api/auth/email/request` (open path, body `{email}`): normalize via
  `normalize_email`, mint a token via `session_store._mint_token("email_magic_link:",
  normalized_email, ttl=900)`, send it via a new `send_magic_link_email(email,
  link)` function in `src/services/email.py` (same shape as
  `send_welcome_email`). Respond identically whether or not the email
  already has an account (no existence oracle).
- `GET /api/auth/email/callback?token=...` (open path): redeem via
  `session_store._redeem_token`, on success call
  `resolve_owner("email", normalized_email, email=normalized_email,
  email_verified=True)` (verified by construction — see decision above),
  mint the session, redirect to `/feed`. An already-redeemed or expired
  token returns a clear 4xx, not a silent redirect.
- Add both routes to `_OPEN_API_PATHS`.
- Tests: request-then-redeem happy path, double-redeem rejected, expired
  token rejected, no account-existence leak on `/request`.

### #621 — Cross-provider account auto-merge on verified email (blocked by #618, #619, #620)

- Edit only `resolve_owner`'s internals (see decision above): add the
  verified-email lookup-and-attach branch, and the partial unique index +
  `IntegrityError` race handling. No route changes.
- Tests: (a) two different providers, same verified email → same
  `owner_id`, one `users` row, two `identity_links` rows; (b) same email but
  the second provider marks it unverified → two separate `owner_id`s; (c) a
  merge never calls `set_user_status`/triggers `notify_operator_invite`
  again; (d) simulated concurrent `resolve_owner` calls for the same new
  verified email resolve to exactly one `owner_id` (use `asyncio.gather` on
  two calls in the test, matching this repo's existing async test style).

### #622 — Discord Gateway connection skeleton, DM-only (blocked by #618 only for config wiring, otherwise independent)

- New `src/channels/discord/gateway.py`: a Gateway client (via the new
  library dependency) authenticated with `DISCORD_BOT_TOKEN`, intents
  limited to direct messages only. `async def run() -> None` connects and
  reconnects on drop (rely on the library's built-in reconnect/resume, do
  not hand-rock a reconnect loop on top of it).
- On receiving a DM: look up the sender's Discord user id in
  `identity_links` (`provider="discord"`). If unresolved, reply with fixed
  instructions on how to pair (points at the dashboard's pairing-code UI
  from #623 — that UI doesn't need to exist yet for this slice; a static
  string is fine, #623 makes it accurate). No job, no account, no
  `identity_links` row is created from this path.
- Wire into `src/worker.py`'s `main()` per the decision above
  (`asyncio.gather`).
- Tests: a unit test around the message handler (mock the Gateway
  client/library) covering "unresolved sender gets pairing instructions,
  nothing is created" and "the connection setup requests no guild intents."
  Full Gateway-connection integration is not realistically testable
  offline — note in your summary if you had to stub the library's client
  object to make this testable at all.

### #623 — Discord pairing (blocked by #618, #622)

- `POST /api/auth/discord/pair` (ordinary authenticated + approved route,
  **not** in `_OPEN_API_PATHS`): mint a pairing code via
  `session_store._mint_token("discord_pairing:", str(request.state.user["id"]),
  ttl=300)` — mirror `extension_tokens.mint_pairing_code` exactly. Return
  the code and instructions to DM it to the bot.
- In #622's DM handler: if the message body is (or starts with) a valid
  pairing code, redeem it via `session_store._redeem_token`; on success,
  insert `identity_links(provider="discord", subject=<sender's Discord user
  id>, owner_id=<redeemed owner id>, verified=1)` and reply confirming
  success. An invalid/expired code gets a clear rejection reply, nothing is
  created.
- Tests: mint → redeem-via-DM happy path creates exactly one
  `identity_links` row; expired/invalid/already-used code creates nothing
  and replies with rejection; a DM from an already-paired snowflake that
  isn't a pairing code falls through to #624's normal handling, not the
  pairing path.

### #624 — Paired Discord DM routes through the shared intake router (blocked by #623)

- In #622's DM handler, once a sender resolves to an `owner_id` via
  `identity_links` (and the message isn't a pairing code — #623 takes
  priority), build the `IntakeActor`/`IntakeMessage` per the decision above
  and call `router.handle()`; render `IntakeResponse.text` back as a DM
  reply (mirror `src/channels/telegram/adapter.py`'s `render_response`
  shape, adapted to whatever the Discord library's send-DM call is).
- No business logic forked for Discord — this slice is transport
  conversion only, same as the Telegram adapter.
- Tests: a paired DM containing a URL produces the same `IntakeResponse`
  shape `router.handle()` already returns for other channels (mock
  `router.handle`, assert the `IntakeMessage` built from a fake Discord DM
  event has the right `actor`/`text` fields); existing rate-limit/quota
  behavior inside the router applies unchanged (no channel-specific bypass
  is added).

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **Do not** add `users.id`, `user_identities` (the plan's original name —
  this batch's table is `identity_links`, additive only), or any `user_id`
  column on `jobs`/`tags`/`spaces`/etc. (Phase 9b, deferred).
- **Do not** touch `src/api/google_oauth.py`, `GOOGLE_OAUTH_CLIENT_ID/SECRET`,
  `google_oauth_tokens`, or `google_oauth_states`.
- **Do not** request Discord guild message intents or the privileged
  `MESSAGE_CONTENT` intent; DM-only.
- **Do not** touch `GITHUB_TOKEN` (the unrelated repo-enrichment PAT) or
  anything in `src/services/github.py`.
- Every new migration is appended at the literal end of `src/database.py`,
  guarded per the existing convention — never edit a prior numbered
  migration.
- Don't refactor unrelated code in a file opened for one slice.
- Backend: `python -m pytest tests -q` and `ruff check src/` (never via the
  `rtk` hook — `.claude/rules/rtk-tests.md`).

## Deliverable

Uncommitted working-tree changes implementing #618–#624 in dependency order
(or the spine plus whichever track(s) you completed, with the remainder
clearly listed), regression tests per each issue's acceptance criteria, and
a short per-issue summary of what was done plus anything that blocked you —
e.g. which Discord Gateway library you chose and why, how you stubbed it for
the #622/#624 tests, and any place the real OAuth credentials (not yet
provisioned — see issues #618/#619/#622's "Why this needs a human" notes)
meant a code path could only be tested with mocked HTTP responses.

## Result summary (post-review, 2026-09-10)

Delivered via Codex Cloud (`task_e_6aa2a619e954832c86925584a4c571a2`) then
hardened after a manual diff review + `/cloud-patch-review` pass. All seven
issues landed in one diff rather than staged per the Work order — `resolve_owner`
shipped with #621's merge branch already built in, which is functionally
equivalent to the staged sequencing and didn't need correcting.

- **#618 GitHub OAuth** — done. `src/api/auth.py` `github_connect`/`github_callback`,
  `src/auth/identity.py`'s `resolve_owner`, `identity_links` table (both in
  `SCHEMA_SQL` and the guarded end-of-file migration). Gap found in review:
  no test exercised the actual HTTP callback or the Operator-notify path —
  added `test_github_callback_new_signup_lands_pending_and_notifies` in
  `tests/test_auth_identity.py`.
- **#619 Google login-only** — done, correctly isolated from the export
  OAuth client (`GOOGLE_LOGIN_*`, never `GOOGLE_OAUTH_*`). Gap: no dedicated
  idempotency/isolation test — added
  `test_google_login_is_idempotent_and_isolated_from_export`, which also
  asserts `google_oauth_tokens`/`google_oauth_states` stay empty.
- **#620 Email magic-link** — done, reusing `mint_email_magic_link`/
  `redeem_email_magic_link` over the existing `_mint_token`/`_redeem_token`
  primitive. Gap: no HTTP-level tests at all existed — added happy-path
  (request → redeem → double-redeem rejected), unknown-token rejection, and
  a no-existence-leak test. Also found and fixed a real gap the handoff doc
  should have specified: `POST /api/auth/email/request` had no rate
  limiting, letting anyone spam an arbitrary mailbox with sign-in links.
  Added `rate_limit.enforce(f"magic_link_request:{email}", max_requests=5)`
  mirroring the existing `reviewer_login` pattern, plus a test.
- **#621 Cross-provider merge** — done; verified-email match and the
  race-safe unique-index + `IntegrityError` recovery both present and
  tested. Gap: nothing tested that a merge skips re-notifying the Operator —
  added `test_merge_across_providers_never_renotifies_operator` (GitHub then
  Google, same verified email, `notify_operator_invite` asserted awaited
  exactly once across both).
- **#622 Discord Gateway skeleton** — done. Chose `discord.py>=2.6,<3` (the
  standard client for this shape of Gateway connection) held open inside
  `worker.py`'s `main()` via `asyncio.gather`. DM-only intents confirmed by
  test and by inspection (`discord.Intents.none()` + `dm_messages=True`
  only). Stubbed via `SimpleNamespace` fakes for the message/author/channel
  objects rather than the real `discord.Client` in tests — no real Gateway
  connection is exercised, only the message-handling logic.
- **#623 Discord pairing** — done; pairing-mint route correctly requires an
  existing approved session (absent from `_OPEN_API_PATHS`), redemption is
  single-use, and a bare DM can never create a Tenant.
- **#624 Discord → shared intake router** — done; delegates straight to
  `router.handle()`, no forked business logic.

**Separate from the above, caught by an automated security review while
this batch was being fixed up, not by the original handoff doc:** GitHub
and Google login's OAuth `state` wasn't bound to the initiating browser
(login-CSRF) — an attacker could start their own flow and trick a victim
into completing the callback on the attacker's identity. Fixed with a
short-lived `HttpOnly`/`Secure`/`SameSite=Lax` cookie carrying `state`,
compared via `hmac.compare_digest` on callback, with tests for both
providers (`test_github_callback_rejects_state_without_matching_cookie`,
`test_google_callback_rejects_state_without_matching_cookie`).

**Resolved (2026-09-10):** checked production `users` for existing
case-insensitive duplicate emails before this migration ever runs against
real data — none found. `_migrate_identity_links` (`src/database.py`) now
also preflights this itself: it raises a clear `RuntimeError` naming any
duplicates before attempting `CREATE UNIQUE INDEX`, rather than letting a
bare `sqlite3.IntegrityError` abort startup uninformatively on some future
deploy.

**Also fixed after a `/codex:review` pass on PR #625, before rabbitloop:**
- `resolve_owner`'s synthetic owner-id range now starts at `-(2**53)`,
  disjoint from any real Telegram-issued id (Telegram bounds those to 52
  significant bits) — the prior arbitrary-negative-32-bit range could have
  collided with a future negative group/supergroup Telegram chat id.
- A same-`(provider, subject)` concurrent race (e.g. a webhook/retry firing
  the same login twice) could mint a `users` row that never got linked and
  was never cleaned up. `resolve_owner` now deletes that orphan when
  `identity_links`' `INSERT OR IGNORE` race is lost.
- `_external_login`'s email-backfill (`src/api/auth.py`) now catches the
  `sqlite3.IntegrityError` a same-email collision there would raise, instead
  of 500ing a legitimate login.
- `_run_services` (`src/worker.py`) now isolates the Discord Gateway
  connection behind a retry loop — previously any exception from
  `discord_gateway.run()` would propagate through `asyncio.gather` and
  cancel `loop()`, taking down real job processing over an optional channel.

Full verification (real full suite, not a targeted subset):
`ruff check src/` clean; `python -m pytest tests -q` — see the PR's own
CI run for the authoritative pass count as of the latest push.
