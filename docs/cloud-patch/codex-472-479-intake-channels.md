# Codex prompt — implement issues #472–#479 (Ownix Intake channels: dashboard, router, share sheet, Telegram adapter, Chrome extension)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `docs/plans/2026-08-03-ownix-intake-channels-extension-share.md` — the
   authoritative plan. Its **"Intake Message Contract"** and **"Scalability And
   Hardening"** sections override any looser paraphrase below if they disagree.
   Note two hard scope fences from its **Non-Goals**: do **not** migrate
   ownership from `chat_id` to `user_id` (Phase 9 — deferred), and do **not**
   build the Discord adapter (Phase 10 — deferred). Jobs and all user-owned
   rows stay `chat_id`-owned in this batch.
2. `docs/adr/0033-shared-job-creation-core.md` — `create_and_enqueue_job()`
   owns dedup + create + enqueue and **intentionally does not notify** the
   caller. Every intake surface reuses it and owns its own result
   notification. Do not fork job-routing logic.
3. `docs/adr/0003-*` (photo processed inline, never queued) and
   `docs/adr/0036-ops-bot-internal-operations-interface.md` (ops-bot stays
   separate from user intake) — relevant to #475 and #477 respectively.
4. `CLAUDE.md` (repo root) — module layout, the `web/components/<area>/<kebab>.tsx`
   rule (no barrel `index.ts`), and the exact test/lint commands. Never run
   pytest through the `rtk` hook (`.claude/rules/rtk-tests.md`).
5. The concrete seams each issue builds on (line numbers current as of this
   writing — find by name if drifted):
   - `src/services/jobs.py:55` — `create_and_enqueue_job(chat_id, url, content_type, *, template, message_id, freestyle_prompt, skip_cache)`.
   - `src/api/jobs.py:22` `jobs_router = APIRouter(prefix="/api/jobs")`; `:207` `create_job` reads `chat_id = request.state.user["id"]`; `:136` the `Field(..., max_length=4_000)` bounds convention (from security issue #405 — mirror it, don't invent a new one).
   - `src/main.py:142-151` router registration; `:120` `AsyncIOScheduler` with `scheduler.add_job(_drain_purge_outbox, "interval", seconds=30)` — the model for the #474 expiry sweeper.
   - `src/database.py:120` `chat_state` table; `:333` the v3 migration that already added `mode = 'awaiting_freestyle'` via `PRAGMA user_version` — mirror that migration convention for the new `expires_at` column.
   - `src/auth/session.py:99-148` — `_mint_token` / `_redeem_token` and the `mint_handoff` / `mint_dashboard_handoff` single-use-TTL convention. #479's pairing token mirrors this exactly.
   - `web/app/manifest.json:23` `share_target`; `web/lib/share-target.ts` `extractSharedUrl(shareUrl, shareText)`; `web/components/shell/sidebar.tsx` (nav entries); `src/processors/document.py` + `src/services/pdf_intake.py` (PDF path); photo intake lives inline in `src/telegram/webhook.py` (no `processors/photo.py`).
6. GitHub issues #472–#479 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the per-slice
   definition of done.

## Key decisions already made (do not relitigate)

- **Reuse, don't fork.** URL intake calls `create_and_enqueue_job()`; it never
  re-implements dedup or enqueue. `/api/jobs` stays the low-level job API and is
  **not** modified — `/api/intake/*` is the new product-interaction API.
- **The router is channel-neutral.** `src/intake/router.py` receives an
  `IntakeMessage` and returns an `IntakeResponse`; it must not import Telegram,
  FastAPI request objects, or extension types, and must not branch on
  `metadata` for core decisions.
- **The contract is versioned and retry-safe from the first commit.**
  `IntakeMessage`/`IntakeResponse` carry `schema_version`; `IntakeMessage`
  carries `idempotency_key`; `IntakeResponse` carries `retryable`. Dedup on
  `idempotency_key` **before** falling back to `create_and_enqueue_job()`
  content dedup — one logical submit == one job.
- **Hardening is a gate, not a follow-up.** Every exposed endpoint enforces a
  per-user rate limit and payload/size caps *before* doing work; uploads add
  MIME content-sniffing (never trust the client `Content-Type`) and a per-user
  quota. Reject early (429/413/415).
- **Ownership is untouched.** No `users.id`/`user_identities`/`intake_channels`
  tables, no `user_id` columns. `request.state.user["id"]` (the `chat_id`) is
  the owner key everywhere in this batch.
- **Auth stays as-is for the web surfaces.** Dashboard/PWA intake authenticate
  via the existing session middleware (`request.state.user`). Only the Chrome
  extension gets a new token path, and only in #479.

## Nature of this batch & suggested sequencing

Cohesive feature, but large — eight vertical slices. Implement in dependency
order and treat the spine as the gate:

- **Spine:** #472 (page + endpoint) → #473 (router + contract). Everything else
  depends on the router existing.
- **Depends on spine:** #474 (state), #475 (files/actions), #476 (share
  target — depends only on #472's page), #477 (Telegram adapter).
- **Extension track:** #478 → #479.

If the single working-tree diff grows too large to review in one pass, it is
acceptable to hand back the spine + one track complete and clearly list which
slices remain — do **not** leave a half-applied migration or a router that some
callers bypass. State exactly where you stopped.

## Work order

### #472 — Dashboard Intake MVP (/intake URL submit)

- New router `src/api/intake.py`: `intake_router = APIRouter(prefix="/api/intake")`,
  registered in `src/main.py` alongside the block at `:142-151`. Add
  `POST /api/intake/message` reading `chat_id = request.state.user["id"]` exactly
  as `src/api/jobs.py:207` does. For a URL payload, run
  `detect_pipeline(url, frozenset(await database.list_allowed_domains(chat_id)))`
  (mirror `src/api/jobs.py:178`) then `create_and_enqueue_job(chat_id, url, content_type)`,
  and **build the result notification in the endpoint** (ADR-0033 — the core
  does not notify). Return a structured body carrying the job id and a link
  target for `/jobs/{id}`.
- **Hardening before work:** an `Idempotency-Key` header (repeat within the
  dedup window returns the original response, HTTP 200, no second job); a
  per-user rate limit; and length caps on `text`/`url` using the
  `Field(..., max_length=…)` convention from `src/api/jobs.py:136`. If the repo
  has no shared rate-limit helper, add a minimal per-user limiter local to the
  intake module and note in your summary that a shared one may be worth
  extracting (human call).
- Web: `web/app/(dashboard)/intake/page.tsx` plus `web/components/intake/*`
  (`intake-composer.tsx`, `intake-thread.tsx`, `intake-response-card.tsx` at
  minimum) following the `web/components/<area>/<kebab>.tsx` rule — no barrel
  file, import each directly. Add an Intake nav entry in
  `web/components/shell/sidebar.tsx`. Design per `DESIGN.md`/`PRODUCT.md`: quiet
  dashboard tool surface, stable composer height, real buttons (not simulated
  chat markup), no marketing hero.
- Tests: backend `tests/test_api_intake.py` covering successful URL submit,
  unsupported URL, auth error, rate-limit rejection, and idempotent re-submit;
  colocated `web/app/(dashboard)/intake/page.test.tsx` (or a component
  `.test.tsx`) for submit success/error render. Existing `/api/jobs` behavior
  must keep working unchanged.

### #473 — Shared channel-neutral intake router + versioned contract (blocked by #472)

- New `src/intake/models.py` (`IntakeActor`, `IntakeFile`, `IntakeAction`,
  `IntakeMessage`, `IntakeResponse` per the plan's "Intake Message Contract",
  including `schema_version`, `idempotency_key`, `retryable`), `src/intake/router.py`
  (`async def handle(msg: IntakeMessage) -> IntakeResponse`), and
  `src/intake/responses.py` (response constructors).
- Move the URL-routing decision (`detect_pipeline` + `create_and_enqueue_job`)
  out of the #472 endpoint and into the router. The endpoint's new job is:
  authenticate → resolve idempotency → normalize into `IntakeMessage` → call
  `router.handle()` → serialize `IntakeResponse`.
- Router rejects an unknown `schema_version` instead of mis-parsing; dedups on
  `idempotency_key` before content dedup; handles URL, unsupported-text, and
  command-looking input. Must not import FastAPI/Telegram types.
- Tests: `tests/test_intake_router.py` — `IntakeMessage -> IntakeResponse`
  across URL / unsupported / command inputs and idempotent replay.

### #474 — Dashboard conversational intake state + expiry sweeper (blocked by #473)

- `src/intake/state.py` wrapping the existing `chat_state` table
  (`src/database.py:120`; `mode='awaiting_freestyle'` already exists per the v3
  migration at `:333`). Support `awaiting_intent` + `awaiting_freestyle`.
- Add an `expires_at` column via the **next** `PRAGMA user_version` migration
  step, mirroring the existing migration convention (do not touch prior
  migrations). Add a sweeper the way `_drain_purge_outbox` is wired:
  `scheduler.add_job(<reap_expired_intake_state>, "interval", seconds=…)` in
  `src/main.py:120-126`.
- `GET /api/intake/state` and `DELETE /api/intake/state` (state scoped to
  `request.state.user["id"]`). Render a pending-state banner + cancel/resume in
  `/intake`. Decide and document the per-channel-vs-last-write-wins semantics in
  a code comment / `CONTEXT.md` entry.
- Tests: state create/resume/cancel, scoping to the signed-in user, and the
  expiry sweep reaping an expired row.

### #475 — Dashboard intake files + inline actions (blocked by #473)

- `POST /api/intake/upload`: PDF → the existing document pipeline
  (`src/services/pdf_intake.py` → `src/processors/document.py`); image → the
  existing inline photo path (ADR-0003) or an explicitly documented queued
  replacement. Enforce max file size, an allowed-MIME allowlist verified by
  **content sniffing** (not the client header), and a per-user daily
  upload/byte quota — reject with 413/415/429 before the pipeline runs.
- `POST /api/intake/action`, idempotent per `(actor, action_id)`. Represent the
  former Telegram inline keyboards as generic `IntakeAction`s rendered as real
  dashboard buttons (`web/components/intake/intake-actions.tsx`).
- Tests: upload validation (size, MIME sniffing, quota) and action idempotency
  (a double-fired action does not double-apply).

### #476 — PWA share target → /intake/share (blocked by #472)

- Change `web/app/manifest.json:23` `share_target.action` from `/feed` to
  `/intake/share`. Add the `/intake/share` route reusing
  `extractSharedUrl(shareUrl, shareText)` from `web/lib/share-target.ts`. If
  authenticated, prefill (or auto-submit — the plan leaves this an open
  question; default to **prefill + confirm** and note it) into `/intake`; if
  unauthenticated, preserve the shared payload across login and return to
  `/intake` so the URL is never lost.
- This intentionally supersedes the Feed-prefill behavior from the closed #423 —
  make sure the old `/feed` share landing is replaced/redirected, not left
  dangling.
- Tests: share-target extraction (reuse existing `share-target` test
  conventions) and the authed-vs-unauthed landing paths.

### #477 — Refactor Telegram webhook into an intake-router adapter (blocked by #473)

- New `src/channels/telegram/adapter.py`: convert Telegram updates →
  `IntakeMessage` (populate `idempotency_key` from the Telegram `update_id` so
  webhook redelivery can't double-create) and render `IntakeResponse` →
  send/edit operations. Move reusable command bodies out of
  `src/telegram/webhook.py`'s `_SLASH_TABLE` into a shared
  `src/intake/commands.py`; leave Telegram-only concerns (callback-query acks,
  message editing, `file_id` download, formatting, ops-bot transport) in the
  adapter/webhook.
- Keep ops-bot behavior separate (ADR-0036) unless a command is genuinely
  shared. **Preserve the existing webhook tests** — Telegram behavior must stay
  functionally equivalent. Add adapter tests covering both conversion
  directions.

### #478 — Chrome extension MVP (blocked by #472)

- New `extension/chrome/` — Manifest V3 `manifest.json`, `src/background.ts`
  (context-menu registration for page/link/selection), `src/popup.tsx` (reads
  active tab URL/title, "Send to Ownix"), `src/api.ts` (POST to
  `/api/intake/message`). Auth for the MVP uses the existing Ownix web session
  where browser policy allows it locally — production-safe auth is #479, not
  here. Document load-unpacked install/dev steps in an `extension/chrome/README.md`.
- Tests: API-client payload construction, context-menu payload normalization,
  popup success/error states (match whatever test runner the extension folder
  adopts; if none, a minimal vitest setup local to `extension/` is fine — note
  the choice).

### #479 — Production-safe extension pairing auth (blocked by #478)

- Dashboard endpoint mints a **single-use, short-TTL** pairing code and the
  extension redeems it for an opaque bearer token — mirror the
  `_mint_token`/`_redeem_token` + `mint_handoff` TTL convention at
  `src/auth/session.py:99-148`; do not invent a new token scheme. Store only a
  **hash** of the extension token server-side (raw shown once at pairing).
  Bearer traffic authenticates via `Authorization: Bearer <token>`; the auth
  layer must distinguish session traffic from token traffic. Add revocation +
  an extension-token list in settings UI, and rate-limit both the pairing and
  token endpoints.
- The extension must never store a raw dashboard session cookie.
- Tests: pairing-code single-use/expiry, hash-only storage (raw token never
  persisted/logged), token auth, and revocation taking effect immediately.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **Do not** add `user_id`/`user_identities`/`intake_channels` or migrate any
  `chat_id` ownership (Phase 9, deferred). **Do not** build any Discord code
  (Phase 10, deferred).
- **Do not** modify `/api/jobs`, `create_and_enqueue_job`, or
  `find_recent_job_by_url` — intake reuses them as-is. The only new schema
  change permitted is the single `expires_at` migration in #474, appended as the
  next `_MIGRATIONS` step (never edit a prior migration).
- Keep the router free of channel-specific imports; keep ops-bot logic separate.
- Don't refactor unrelated code in a file opened for one slice.
- Backend: `python -m pytest tests -q` and `ruff check src/` (never via the
  `rtk` hook — `.claude/rules/rtk-tests.md`). Web: `npm run test:run`,
  `npm run lint`, `npm run build` from `web/`.

## Deliverable

Uncommitted working-tree changes implementing #472–#479 in dependency order
(or the spine plus whichever tracks you completed, with the remainder clearly
listed), regression tests per each issue's acceptance criteria, and a short
per-issue summary of what was done plus anything that blocked you — e.g. whether
a shared rate-limiter should be extracted, the chosen share-target
prefill-vs-auto-submit behavior, and the per-channel pending-state semantics you
settled on.
