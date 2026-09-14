# Codex prompt — implement issues #632–#635 (MCP Gardener, Phase 1)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/mcp-roadmap.md` — the roadmap. Phase 1 ("Gardener") section is what
   this batch builds; Phase 2/Phase 3 are out of scope, do not build toward
   them.
2. `docs/adr/0062-gardener-reuses-hard-delete-no-undo-tier.md` — the accepted
   decision that Gardener deletes are hard, via the existing `delete_link`
   primitive, with no new soft-delete/trash tier. Authoritative on delete
   semantics.
3. `CONTEXT.md` — read the **Gardener** and **MCP brain server** glossary
   entries specifically; they cross-reference every settled decision this
   batch depends on (scope, no-duplicate-detection, live-check-only).
4. `CLAUDE.md` (repo root) — layout and the test/lint commands below.
5. Concrete files this batch touches or mirrors:
   - `src/main.py` — where routers/middleware are wired onto the FastAPI app.
   - `src/auth/middleware.py` — the session gate. Read this closely: it only
     applies its auth logic to paths starting with `/api/` — anything outside
     that prefix bypasses the gate entirely (see `_OPEN_PATHS` and the
     early-return for non-`/api/` paths). This is why the MCP mount path
     decision below is load-bearing, not cosmetic.
   - `src/auth/extension_tokens.py` — the bearer-token module to mirror in
     shape (mint/store/resolve/list/revoke), not import from or generalize.
   - `src/api/extension_auth.py` — the pairing/redeem/list/revoke endpoint
     shape to mirror.
   - `web/components/controls/extension-tokens-panel.tsx` and
     `web/app/(dashboard)/controls/page.tsx` — the dashboard UI pattern to
     mirror for the new MCP pairing panel.
   - `src/brain.py` (`list_links`, `get_link_preview`) and `src/db/tags.py`
     (`delete_link`) — the existing tenant-scoped functions the MCP tools
     wrap. Do not reimplement their logic.
   - `src/api/brain.py` — shows how these functions are already called from
     an HTTP route (ownership check, 404-not-403 on a miss/foreign id) —
     match that error-shape convention in the MCP tool layer too.
   - `requirements.txt` — no MCP SDK is installed yet; add the official
     Python MCP SDK (verify current package name/version before pinning).
6. GitHub issues #631 (parent spec), #632, #633, #634, #635
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each of #632-635 carries its
   own acceptance criteria; treat those as the definition of done per slice.
   #631 is the full spec these four slices implement pieces of.

## Key decisions already made (do not relitigate)

- **Scope is Brain links only.** No Job-record operations are exposed over
  MCP in this phase.
- **Three MCP tools total, no more:** `list_items`, `get_item_detail`, and a
  confirm-gated delete. There is no `flag_item` tool — flagging is the
  calling agent's own conversational reasoning, nothing about a flag is
  persisted server-side.
- **No duplicate detection anywhere in this batch.** `links` already has a
  unique `(chat_id, url)` index; a real duplicate flag needs
  similarity-search infra that doesn't exist yet (Phase 2, not this batch).
- **Delete is hard, via `delete_link` exactly as it stands.** No new column,
  no trash tier, no undo window, no soft-delete flag. Do not add one even as
  a "just in case" — ADR-0062 explicitly rejected this.
- **Mount the MCP server under `/api/mcp/`, not outside `/api/`.** The
  session middleware's auth logic only runs for `/api/*` paths (see
  `src/auth/middleware.py` above) — mounting anywhere else means the MCP
  surface bypasses authentication entirely. This is a hard requirement, not
  a style preference.
- **New bearer-token module (`src/auth/mcp_tokens.py`), not a shared
  abstraction with `extension_tokens.py`.** `extension_tokens.py`'s own
  docstring already states it deliberately mirrors `session_store`'s
  mint/redeem helpers directly rather than generalizing further — follow
  that same precedent for MCP: a same-shape sibling module, not a shared
  base class or helper extracted for two call sites.
- **New allow-listed bearer prefix:** add `/api/mcp/` to
  `_BEARER_ALLOWED_PREFIXES` in `src/auth/middleware.py`, resolving via
  `mcp_tokens.resolve_mcp_token` the same way the existing entry resolves via
  `extension_tokens.resolve_extension_token`. A token minted for MCP must
  never resolve on any other prefix, and an extension token must never
  resolve on `/api/mcp/`.
- **Health checks are live, in-call, never cached or scheduled.** No new
  cron job, no new column on `links` for reachability status. A transient
  fetch failure (timeout/rate-limit/5xx) must be classified and reported
  distinctly from a confirmed-dead result (404/DNS failure) — never
  conflated into one boolean.
- **Rate limiting on every MCP endpoint**, reusing the existing rate-limit
  mechanism (`src/intake/rate_limit.py`'s pattern, as already used by the
  extension pairing/redeem endpoints) — not a new implementation.
- **Ownership-check error shape matches `src/api/brain.py`'s existing
  convention:** a link that doesn't exist or belongs to another tenant
  returns "not found," never a distinguishable "forbidden" — no ownership
  probing via response difference.

## Work order

Implement in issue order — each slice builds on the previous. Run the full
backend test/lint suite after each slice, not just at the end.

### #632 — bearer-token pairing, issuance, listing, revocation

Build `src/auth/mcp_tokens.py` mirroring `extension_tokens.py`'s shape
(mint pairing code → redeem for a long-lived token, hash-only storage, raw
token shown once). Add pairing/redeem/list/revoke endpoints under `/api/mcp/`
mirroring `src/api/extension_auth.py`'s endpoint shape (pairing endpoint
session-authed; redeem endpoint added to `_OPEN_API_PATHS` since the code
itself is the credential, matching how `/api/extension/token` is already
listed there). Add `/api/mcp/` to `_BEARER_ALLOWED_PREFIXES`. Add a minimal
placeholder route (e.g. `GET /api/mcp/ping`) that requires the resolved
bearer and echoes the resolved chat id — this is what proves the whole path
end-to-end before the real MCP protocol server exists (#633 replaces/extends
this mount point, doesn't remove the auth wiring). Add the dashboard panel
(`web/components/controls/mcp-tokens-panel.tsx`, mirroring
`extension-tokens-panel.tsx`) wired into Controls.

Test per #632's acceptance criteria: mint→redeem→resolve round trip, hash-only
storage, immediate effect of revocation, rate limiting on both mint and
redeem, cross-prefix isolation (an MCP token must not resolve on
`/api/intake/` and vice versa), ownership-checked list/revoke.

### #633 — server mount + `list_items`/`get_item_detail`

Mount the MCP server (via the SDK's ASGI transport) at `/api/mcp/`,
in-process on the existing FastAPI app in `src/main.py` — no new
service/container/entry in `docker-compose.yml`. Implement `list_items`
(wraps `brain.list_links`, same pagination/search/order params) and
`get_item_detail` (wraps `brain.get_link_preview`) as MCP tools, both
resolving the calling chat id from the bearer token before touching data.

Test per #633's acceptance criteria: tenant isolation (verified with two
distinct tokens/chat ids, not assumed), not-found on a bad/foreign link id,
auth rejection before either tool executes, rate limiting.

### #634 — live URL health-check signal

Add a live reachability check (new small module, e.g.
`src/services/link_health.py` or similar — name it to fit the existing
`src/services/` convention) that both tools' responses call into per link:
classify into reachable / confirmed-dead (404, DNS/domain failure) /
transient-failure (timeout, rate-limit, 5xx), fetched at call time. A failure
on one link's check must not fail the whole batch response.

Test per #634's acceptance criteria: unit tests against mocked fetch outcomes
for all four+ cases (200, 404, DNS failure, timeout, rate-limit, 5xx),
asserting the transient/confirmed-dead distinction is preserved in the tool
response shape.

### #635 — confirm-gated delete tool

Add the delete tool: takes one link id, calls `database.delete_link` (via
`src/db/tags.py`, matching how `src/api/brain.py`'s `delete_link` route
already calls it) exactly as-is — no new deletion logic, no batch path.
Owner-checked, 404-shaped not-found on a bad/foreign/already-deleted id.

Test per #635's acceptance criteria: single-id-only invocation (no path that
could act on more than the explicitly passed id), Drive-purge verified (not
just the DB row), rate limiting, ownership-check error shape matches #633's
tools.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Do not touch Job-record code paths, Phase 2/3 roadmap items, or anything
  resembling duplicate/similarity detection — out of scope for this batch.
- Do not add a soft-delete column, trash tier, or undo window anywhere —
  ADR-0062 already rejected this; don't reopen it.
- Do not mount the MCP server outside `/api/mcp/` — see the middleware note
  above.
- Do not generalize `extension_tokens.py` and the new `mcp_tokens.py` into a
  shared module — same-shape siblings, not a shared abstraction.
- Backend tests: `python -m pytest tests -q` (never through the `rtk` hook —
  see `.claude/rules/rtk-tests.md`), lint via `ruff check src/`
  (line-length 100, py311). Frontend, if the Controls panel needs its own
  test: `npm test` / `npm run lint` from `web/`, colocated `.test.tsx`
  beside the new component, matching `extension-tokens-panel.tsx`'s test.

## Deliverable

Uncommitted working-tree changes implementing #632–#635 in full, tests per
each issue's acceptance criteria, and a short summary of what was done per
issue plus anything that blocked you (e.g. the exact MCP SDK package/version
chosen, if current docs suggest something other than an obvious default).

## Post-implementation note

The landed PR deviates from "do not generalize `extension_tokens.py` and
`mcp_tokens.py` into a shared module" above: both now delegate to a new
`src/auth/bearer_token_store.py::BearerTokenStore`, namespaced per caller
(`"extension"` / `"mcp"`). Once written out, the two facades were the same
helpers with a different key prefix — extracting that shared piece was less
risk than maintaining two copies of the same Redis/memory dance. Each
facade's public surface (`mint_pairing_code`/`redeem_pairing_code`/
`issue_*_token`/`resolve_*_token`/`list_*_tokens`/`revoke_*_token`) is still
a distinct, namespaced module — nothing calls into the other facade's
namespace directly.
