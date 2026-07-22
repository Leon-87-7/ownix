# Codex prompt — implement issues #399, #402–#410 (security/validation hardening)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. GitHub issues #399, #402, #403, #404, #405, #406, #407, #408, #409, #410
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each carries its own
   acceptance criteria; treat those as the definition of done per issue.
2. `CLAUDE.md` (repo root) — project layout, test/lint commands.
3. The specific files each issue below points at — line numbers are given as
   of this writing but may have drifted a line or two; find the function by
   name if so.

## Nature of this batch

These are nine independent defensive-hardening fixes surfaced by an automated
security review and confirmed against the code. They do **not** share a
migration, a schema change, or a common helper to extract — treat each as its
own small, self-contained diff. Do not invent a shared validation module or
abstraction that spans multiple issues unless an issue explicitly asks for it;
each fix should read as the minimum change its own acceptance criteria require.

Work through them in the order below (roughly highest severity first). Nothing
in this batch blocks anything else — if one turns out to need a design
decision only a human can make, skip it, note why, and continue to the next.

## Issues

### #399 — GET-based `/api/auth/handoff` is a login-CSRF primitive

- `src/api/auth.py:138` — `handoff_login` (`@auth_router.get("/handoff")`)
  redeems `src/auth/session.py:143` `redeem_dashboard_handoff` and sets the
  session cookie, all from a plain top-level GET.
- `src/utils/__init__.py:34` — `dashboard_button_row` mints the token via
  `mint_dashboard_handoff(chat_id, ttl=7 * 24 * 3600)` and puts it directly in
  a Telegram inline-keyboard **URL button** (`{"text": "🔗 Open in
  Dashboard", "url": url}`), so the browser hitting that URL is exactly a
  top-level GET navigation with no user gesture beyond the Telegram tap.
- Redemption is already single-use (Redis `GETDEL` in
  `redeem_dashboard_handoff`) — that part is fine. The gap is that GET alone
  installs a session; a link forwarded/leaked before it's clicked lets
  whoever clicks it get silently logged into the token-minter's account.

**Fix direction** (issue's own reviewed suggestion — apply it, this is not a
"landing branch" design call, it's the shape of the acceptance criteria):

1. Split `GET /api/auth/handoff` so it no longer redeems or sets a cookie by
   itself — render a same-origin confirmation ("Open your dashboard") that
   POSTs to redeem. Add a `POST /api/auth/handoff` (or equivalent) that does
   the actual `redeem_dashboard_handoff` + `session_store.mint` + `set_cookie`
   + redirect. Telegram bot buttons still only do GET, so the GET response
   must render something that self-submits the POST (an auto-submitting form
   is fine — it's same-origin, not cross-site, so it's not itself a CSRF
   vector).
2. Drop the `mint_dashboard_handoff` TTL in `src/utils/__init__.py:34` from
   `7 * 24 * 3600` to minutes, not days (check `_COOKIE_MAX_AGE` / existing
   `mint_handoff` 60s convention in `src/auth/session.py` for the pattern this
   repo already uses elsewhere).
3. Optional/stretch: bind redemption to a browser-set nonce. Skip if it
   requires new client-side plumbing beyond what the acceptance criteria ask.

Existing valid "Open in Dashboard" → job page flow must keep working end to
end (mint → tap → land on `/jobs/{job_id}` signed in).

### #402 — `detect_pipeline` scheme/host validation

- `src/utils/validators.py:70` — `detect_pipeline` calls `urlparse` but never
  checks `parsed.scheme`. Host matching (`_match_short` / `_match_long` /
  `ARTICLE_DEFAULT_DOMAINS` check) uses `endswith`, so `evilyoutube.com`
  matches the `youtube.com` rule.
- Domain allow/ignore-list normalization (HTTP-side and Telegram-side, same
  file/module) only extracts a hostname without DNS-label validation, so
  values like `com` or hosts with underscores get stored, and a stored
  allowlist entry of `com` over-matches via the same `endswith` looseness.

Fix: require `parsed.scheme in ("http", "https")` before classifying; replace
`endswith` host checks with exact-or-`.`-suffix-bounded matching (e.g. `host
== target or host.endswith("." + target)`); validate stored allow/ignore-list
entries as well-formed DNS labels on both normalization paths (reject bare
TLDs, underscores, empty labels). Keep existing valid URLs/domains routing
the same — add regression tests for the lookalike-host and bad-scheme cases.

### #403 — cross-chat IDOR on Telegram job callback handlers

- `src/telegram/webhook.py` — callback handlers built around `ctx.job_id` /
  `ctx.chat_id` (e.g. `_handle_template_pick` ~line 219, `_handle_freestyle_arm`
  ~line 247, `_handle_prd_auto` ~line 290, `_handle_prd_intent_prompt` ~line
  308, `_handle_prd_intent_resend` ~line 323, `_handle_enrichment_retry`
  ~line 333) each do `job = await database.get_job(ctx.job_id)` (or the
  equivalent) and then mutate/requeue without checking `job["chat_id"] ==
  ctx.chat_id`. Confirmed by reading the file: none of these compare the two.
- Callback data also encodes a free-form "template" segment
  (`callback_data=f"template_pick:{name}:{ctx.job_id}"`) that isn't checked
  against an explicit allowlist before use.

Fix: after loading `job` in each handler that acts on `ctx.job_id`, add `if
job is None or job["chat_id"] != ctx.chat_id: log + return` (no-op) before any
mutation/requeue. Validate the template value against the known set already
implied by the five inline-keyboard buttons (`summary`, `method`, `technical`,
`review`, `narrative`, plus `freestyle`) rather than trusting the callback
payload verbatim. Add a regression test that a callback carrying a foreign
`job_id`/mismatched `chat_id` is rejected as a no-op.

### #404 — `transcript_server.py` has no auth or SSRF guards

- `transcript_server.py:199` (`/transcript`), `:212` (`/metadata`), `:293`
  (`/short_frames`) all accept a caller-supplied URL and hand it to yt-dlp
  with no auth check and no scheme/host validation.
- `:300–302` — `interval`, `max_frames`, `max_width` are parsed with
  `request.args.get(..., default)` and cast to `float`/`int` with no upper
  (or lower) bound.
- Per `CLAUDE.md`, this can run standalone on the host (`python
  transcript_server.py`) binding all interfaces, not just inside the compose
  network — so a host firewall gap makes this internet-reachable.

Fix: add a shared-secret header/token check consistent with how this repo
authenticates its other internal service calls (check `src/services/` for
the existing pattern the worker uses to call this sidecar, and mirror it —
don't invent a new auth scheme). Validate submitted URLs: reject non-http(s)
schemes, resolve the host and reject private/link-local/loopback ranges
(`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`,
`169.254.0.0/16`, etc.) before fetching. Add explicit bounds to `interval`,
`max_frames`, `max_width` (reject out-of-range with a 4xx, don't silently
clamp). Keep legitimate worker → sidecar calls working — update the worker's
call site to send whatever auth token the fix introduces.

### #405 — unbounded user-supplied text fields

- `src/api/jobs.py:141–144` — `JobCreateRequest.freestyle_prompt: str | None`,
  only checked for non-emptiness at `:170–173`.
- `src/api/jobs.py:348–349` — `AnnotationIn.notes: str`, no length bound.
- `src/api/spaces.py:48–55` — `BlobIn.content` / `BlobContentIn.content: str`
  (Context blobs, S7), `content: str = Field(default="")` with no max size.
- `src/api/brain.py:28` — `search_links(q: str = Query(...), k: int =
  Query(default=5, le=20))`: `q` unbounded and triggers a paid Gemini
  embedding call per request (`brain.search_links`); `k` has a max but no
  `ge=1` minimum.
- `src/api/brain.py:44` — `list_links(... q: str = Query(default=""), ...)`:
  the link-list filter `q`, also unbounded.

Fix: add `Field(max_length=...)` / `Query(max_length=...)` bounds to each
(pick sane values — e.g. a few thousand chars for prompt/notes/context, a few
hundred for search queries; match whatever similar bounded fields in the same
files already use as a reference, e.g. `SpaceIn.name`'s `max_length=120`
convention). Add `ge=1` to brain search's `k`. Requests over any bound must
return a 4xx validation error (Pydantic/`Query` constraints do this
automatically — don't hand-roll truncation).

### #406 — `/download_md` has no URL validation

- `src/telegram/webhook.py:831` — the `/download_md` command handler only
  checks that an argument was supplied before fetching it.

Fix: require `https` scheme (match whatever scheme convention #402/#404 land
on in this same pass — stay consistent across the three URL-validation
issues), resolve and reject private/link-local/loopback hosts (same range
list as #404), and cap the URL's length. Keep existing valid `/download_md
<url>` usage working.

### #407 — whitespace-only names pass Pydantic length checks

- Space/tag/context name fields (`src/api/spaces.py` `SpaceIn.name` /
  `SpaceUpdateIn.name`, and the equivalent tag name field in
  `src/api/controls.py`) are length-checked by Pydantic *before* the route
  calls `.strip()`, so `"   "` passes validation and is then stored as `""`.

Fix: switch these `Field(min_length=1, ...)` string fields to a validator (or
just check `body.name.strip()` truthiness) that enforces non-empty *after*
stripping, for spaces, tags, and contexts alike. Reject whitespace-only names
with a 4xx. Names that are non-empty after stripping (including ones with
incidental leading/trailing whitespace) must keep working.

### #408 — unbounded `sort_order` on reorder endpoints

- `src/api/spaces.py:44–45` — `ReorderIn.sort_order: int`, used by both the
  space-URL reorder endpoint (`:166`) and the context-blob reorder endpoint
  (`:243`). No range check on either.

Fix: bound `sort_order` to a sane non-negative range (e.g. `Field(ge=0,
le=<some generous ceiling like 10_000>)` — pick a ceiling well above any
realistic list length in this app, don't try to compute the exact live list
length server-side for this). Out-of-range values return a 4xx. Existing
valid reorders keep working.

### #409 — tag `icon` accepts arbitrary strings

- `src/api/controls.py:21` — `icon: str | None = Field(default=None,
  max_length=80)` on the tag create/update body, used at `:52` and `:64`
  (`create_tag` / `update_tag`, `src/database.py:1862`/`1873`).
- The frontend's fixed set lives in
  `web/components/ui/tag-picker.tsx:34`: `const TAG_ICONS: Record<string,
  LucideIcon> = { Brain, Code2, Database, FileText, Globe, Lightbulb, Link2
  }`.
- Note `src/api/spaces.py:13–17` already does this correctly for *space*
  icons via a `Literal[...]` type alias (`SpaceIcon`, issue #189) — mirror
  that pattern for tags rather than inventing a new validation style.

Fix: change the tag icon field to a `Literal["Brain", "Code2", "Database",
"FileText", "Globe", "Lightbulb", "Link2"]` (allow `None` to clear/omit, same
as today), matching the `SpaceIcon` convention. Values outside the set get a
422. Existing valid icon values keep working.

### #410 — SQL `LIKE` wildcard injection in `/users email <domain>`

- `src/services/ops_bot.py:216–217` — `list_users` builds `"lower(coalesce(
  email, '')) LIKE ?"` with `params.append("%@" + email_domain.lower()
  .lstrip("@"))`. The domain is parameterized (no SQL injection), but `%`/`_`
  inside `email_domain` retain `LIKE` wildcard meaning, so an operator-typed
  domain containing those characters matches more than the literal domain.
- `normalize_email_domain` (`:123–138`) already validates general domain
  shape (lowercases, strips `@`, checks for a `.`, splits into labels) but
  does not escape `%`/`_` before the value reaches the `LIKE` clause.

Fix: escape `%` and `_` (and the escape character itself) in the domain
value before interpolating it into the `LIKE` pattern, and add `ESCAPE
'\\'` (or your chosen escape char) to the SQL, or switch this specific
match to a non-wildcard comparison if that's simpler given there's already
a `%@` prefix wildcard by design (only escape the *domain* portion, not the
`%@` prefix). Existing valid `/users email <domain>` usage must keep working;
add a regression test that a domain containing `%` or `_` matches only the
literal value.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Treat each issue as an independent diff; don't merge them into one shared
  helper/module unless an issue's own acceptance criteria calls for it.
- Run `python -m pytest tests -q` and `ruff check src/` after each issue (or
  at the end of the batch) per `CLAUDE.md` — never through the `rtk` hook.
  Add regression tests per issue's acceptance criteria (colocated in
  `tests/`, matching existing test file naming for the module you touched).
- Don't touch unrelated code in files you open for one fix (e.g. don't
  refactor `src/telegram/webhook.py` beyond the #403 ownership checks).

## Deliverable

Uncommitted working-tree changes implementing #399, #402–#410, with
regression test coverage per issue's acceptance criteria, plus a short
summary of what was done per issue and anything that blocked you (e.g. if a
shared-secret auth convention for #404 doesn't exist yet and needs a human
call on where to source the secret from).
