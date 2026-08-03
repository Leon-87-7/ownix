# Ownix Intake Channels, Chrome Extension, And Share Sheet Plan

Date: 2026-08-03

Status: Draft implementation plan

Owner surface: dashboard intake, browser extension, PWA share target, future channel adapters

Target routes:

- `/intake`
- `/intake/share`
- `/api/intake/*`

Primary files likely affected:

- `src/intake/*`
- `src/channels/*`
- `src/telegram/webhook.py`
- `src/services/jobs.py`
- `src/database.py`
- `src/api/*`
- `web/app/(dashboard)/intake/*`
- `web/components/intake/*`
- `web/app/manifest.json`
- `web/lib/share-target.ts`
- `extension/*` or `apps/chrome-extension/*`

Related product decisions and context:

- `CLAUDE.md`
- `PRODUCT.md`
- `DESIGN.md`
- `CONTEXT.md`
- `docs/adr/0033-shared-job-creation-core.md`
- `docs/adr/0036-ops-bot-internal-operations-interface.md`
- `docs/adr/0039-link-pipeline-direct-add.md`
- `docs/archive/ISSUE_KANBAN-archive.md` entries for PWA installability and share-target intake

## Current Grounding

Ownix is already partway toward standalone intake, but the core model is still
Telegram-shaped.

Verified current facts:

- `jobs.chat_id` owns jobs.
- `users.tg_id` owns dashboard auth identity.
- `chat_state.chat_id` stores conversational pending state.
- `google_oauth_tokens.chat_id` stores per-user Google OAuth.
- `tags`, `spaces`, `templates`, `allowed_domains`, `ignored_domains`, and settings are scoped by `chat_id`.
- `src/services/jobs.py:create_and_enqueue_job()` is already the shared job creation core.
- `src/api/jobs.py` already lets the dashboard create URL jobs.
- `src/telegram/webhook.py` still owns most command routing, conversational state, file handling, callback actions, and user-facing response copy.
- `web/app/manifest.json` already has a GET-based PWA `share_target` aimed at `/feed`.
- `web/lib/share-target.ts` already extracts URLs from `share_url` / `share_text`.

## Goal

Create a first-class Ownix Intake system that works inside the dashboard, from a
Chrome extension, from the PWA share sheet where the platform supports it, and
later from Discord or other channels.

The product primitive is:

```txt
Ownix Intake
```

Telegram, Dashboard, Chrome extension, Android share sheet, Discord, and email
are channels into that primitive.

## Architecture Direction

Move from this:

```txt
Telegram webhook
  owns commands, state, URLs, files, replies
        ↓
jobs / processors / dashboard
```

To this:

```txt
Dashboard /intake
Chrome extension
PWA share target
Telegram bot
Future Discord bot
Future email forwarder
        ↓
channel adapter
        ↓
shared Ownix intake router
        ↓
jobs, commands, state, files, templates, approvals
        ↓
channel-specific response renderer
```

Telegram should become one adapter, not the product's architectural center.

## Identity Direction

Do not replace `chat_id` with email directly. Email is a login and contact
address, not a durable internal owner key.

Target identity model:

```txt
users
  id
  email
  status
  display_name
  created_at
  updated_at

user_identities
  id
  user_id
  provider              -- email | google | telegram | discord
  provider_subject      -- email address | Google sub | Telegram tg_id | Discord user id
  created_at
  updated_at

intake_channels
  id
  user_id
  type                  -- dashboard | chrome_extension | pwa_share | telegram | discord | email
  external_id           -- Telegram chat_id, Discord channel/user id, null for dashboard
  display_name
  created_at
  updated_at

intake_state
  channel_id
  mode
  job_id
  payload_json
  expires_at
```

Long term, jobs and user-owned resources should belong to `user_id`, not
`chat_id`.

Compatibility rule during migration:

```txt
existing chat_id == legacy user owner id until the user_id cutover is complete
```

## Intake Message Contract

Introduce a channel-neutral request model.

Suggested shape:

```python
class IntakeActor:
    user_id: str | int
    channel_id: str
    channel_type: str
    legacy_chat_id: int | None = None

class IntakeMessage:
    schema_version: int = 1          # bump on any breaking contract change
    idempotency_key: str | None = None  # caller-supplied dedup key for safe retries
    actor: IntakeActor
    text: str | None = None
    url: str | None = None
    files: list[IntakeFile] = []
    action: IntakeAction | None = None
    source_message_id: str | int | None = None
    received_at: float | None = None  # server ingest timestamp for latency/ordering
    metadata: dict = {}

class IntakeResponse:
    schema_version: int = 1
    kind: str
    text: str
    job_id: str | None = None
    actions: list[IntakeAction] = []
    state: dict | None = None
    artifacts: list[dict] = []
    retryable: bool = False          # signal transient failures to channel adapters
```

The router should not know whether the caller is Telegram, dashboard, extension,
or Discord. It should receive `IntakeMessage` and return `IntakeResponse`.

Contract stability rules (these keep the fan-out of channels from fossilizing an
accidental v1):

- Every `IntakeMessage` / `IntakeResponse` carries `schema_version`. Adapters
  reject a version they cannot parse instead of silently mis-reading fields.
- Fields are added, never repurposed. A removed field is tombstoned, not reused.
- `idempotency_key` is the retry contract: the same key from the same actor must
  yield the same job, never a duplicate. Channels that can double-deliver
  (extension network retries, PWA share re-fires, Telegram webhook redelivery)
  MUST populate it.
- `metadata` is channel-private scratch space; the router must never branch on
  its contents to make core decisions.

## Dashboard Intake Page

Add a new dashboard page:

```txt
/intake
```

It should be the main Ownix-native intake surface, not a Telegram clone.

Expected capabilities:

- paste a URL
- submit plain text
- submit slash commands
- choose templates
- submit freestyle prompts
- upload PDF/document
- upload image/photo
- show pending state such as `awaiting_intent` or `awaiting_freestyle`
- show created jobs inline
- show recent intake history
- render action buttons that replace Telegram inline keyboards
- let the user resume/cancel pending state
- link created jobs to `/jobs/{id}`

Suggested UI modules:

```txt
web/app/(dashboard)/intake/page.tsx
web/components/intake/intake-composer.tsx
web/components/intake/intake-thread.tsx
web/components/intake/intake-response-card.tsx
web/components/intake/intake-actions.tsx
web/components/intake/intake-upload-dropzone.tsx
web/components/intake/intake-state-banner.tsx
web/components/intake/intake-template-picker.tsx
```

Design requirements:

- quiet dashboard tool surface
- dense enough for repeated use
- no marketing hero
- no chat novelty for its own sake
- stable composer height
- keyboard-friendly command entry
- clear file upload states
- action buttons use actual buttons, not simulated chat markup

## Chrome Extension

Add a Chrome extension as a lightweight capture client.

Suggested location:

```txt
extension/chrome/
```

or, if the repo later adopts app folders:

```txt
apps/chrome-extension/
```

Core extension surfaces:

- toolbar popup: send current tab to Ownix
- context menu: save page, link, selected text, image, or video URL
- optional side panel: full mini intake without leaving the current page
- options page: choose Ownix host, connection status, logout

Suggested files:

```txt
extension/chrome/manifest.json
extension/chrome/src/background.ts
extension/chrome/src/popup.tsx
extension/chrome/src/side-panel.tsx
extension/chrome/src/api.ts
extension/chrome/src/auth.ts
```

Minimum viable extension behavior:

1. User clicks extension icon.
2. Popup reads active tab URL and title.
3. User clicks `Send to Ownix`.
4. Extension calls `/api/intake/message`.
5. Ownix returns a created job or a validation/action response.
6. Popup shows the job result and link to dashboard.

Authentication options:

- Phase 1: rely on existing Ownix web session cookie when same-site/browser policy allows it.
- Phase 2: add extension-specific token minting from the logged-in dashboard.
- Phase 3: add device/session management for revoking extension tokens.

Preferred durable auth model:

```txt
Dashboard: /settings/extensions/connect
  mint one-time pairing code

Extension:
  redeem pairing code
  store short opaque extension token

API:
  Authorization: Bearer <extension token>
```

Do not store long-lived raw session cookies inside the extension.

## Share Sheet

Ownix already has a basic PWA share target. Move it from Feed prefill to Intake.

Current shape:

```json
"share_target": {
  "action": "/feed",
  "method": "GET",
  "params": {
    "title": "share_title",
    "text": "share_text",
    "url": "share_url"
  }
}
```

Target first iteration:

```json
"share_target": {
  "action": "/intake/share",
  "method": "GET",
  "params": {
    "title": "share_title",
    "text": "share_text",
    "url": "share_url"
  }
}
```

Target richer iteration:

```json
"share_target": {
  "action": "/intake/share",
  "method": "POST",
  "enctype": "multipart/form-data",
  "params": {
    "title": "title",
    "text": "text",
    "url": "url",
    "files": [
      {
        "name": "files",
        "accept": ["image/*", "application/pdf", "text/plain"]
      }
    ]
  }
}
```

Platform reality:

- Android Chrome installed PWA share target is the practical web path.
- iOS Safari PWA share target is not a dependable web-only path.
- A true iOS share sheet target likely requires a native iOS wrapper/app,
  Shortcuts-based bridge, or a future platform capability.

Short-term iOS fallback ideas:

- bookmarklet that opens `/intake?url=...`
- iOS Shortcut that calls `/api/intake/message`
- "Copy link, open Ownix" flow with clipboard prefill
- future native iOS share extension

## API Surface

Add dashboard/extension/share friendly endpoints:

```txt
POST /api/intake/message
POST /api/intake/upload
POST /api/intake/action
GET  /api/intake/state
DELETE /api/intake/state
GET  /api/intake/history
```

Endpoint responsibilities:

- authenticate user
- enforce per-user rate limits and payload/upload size caps before doing work
- resolve or create channel (idempotently — see channel-resolution race below)
- honor `Idempotency-Key` header / `idempotency_key` field for safe retries
- normalize payload into `IntakeMessage`
- call shared intake router
- return structured `IntakeResponse`

`/api/jobs` should remain the low-level job API. `/api/intake/*` is the product
interaction API.

Endpoint hardening requirements:

- `POST /api/intake/message` and `/api/intake/action` are mutating and MUST
  accept an `Idempotency-Key` header. A repeat within the dedup window returns
  the original `IntakeResponse` (HTTP 200) rather than creating a second job.
- `POST /api/intake/upload` enforces a max file size, an allowed-MIME allowlist
  with content sniffing (do not trust the client `Content-Type`), and a
  per-user daily upload/byte quota. Reject early with 413/415/429, before the
  bytes hit the pipeline.
- `GET /api/intake/history` is cursor-paginated (opaque cursor + `limit`), never
  an unbounded scan. Cap `limit` server-side.
- All `/api/intake/*` responses set explicit cache headers (`no-store` for
  mutating and state reads) and a consistent error envelope so extension and
  share clients can branch on `retryable`.
- CORS is locked to the dashboard origin plus the published extension origin(s);
  the extension authenticates by token (see Phase 8), not ambient cookies, so
  these endpoints stay CSRF-safe without relying on same-site cookie behavior.

## Command Migration

Extract current Telegram commands into shared handlers.

Candidate command groups:

- help/start
- recent jobs
- find/search
- spec/PRD generation
- force/reprocess
- cancel
- allowlist/unallowlist/list allowlist
- ignored domains
- templates
- freestyle
- pending invite/approval user flows where user-facing

Telegram-only operations should stay in the Telegram adapter:

- Telegram callback query acknowledgements
- Telegram message editing
- Telegram file download by `file_id`
- Telegram sticker/message formatting
- Telegram ops-bot transport

Shared behavior should move to `src/intake/commands.py` and related modules.

## Scalability And Hardening

These are cross-cutting concerns that every phase inherits. They are not a phase
of their own — bolting them on last is how an intake surface becomes a DoS
vector. Treat each as a definition-of-done gate for the phase that first exposes
the surface.

### Abuse and load control

- Per-user and per-channel rate limits on all `/api/intake/*` mutating
  endpoints, plus a global ceiling so one account cannot saturate the worker
  queue. Return 429 with `retryable=true` and a `Retry-After`.
- Payload caps: max text length, max URL length, max files per message, max
  bytes per file, max bytes per user per day.
- Intake is authenticated-only (per Non-Goals: no public unauthenticated
  intake). Keep that invariant enforced at the router, not just the route, so a
  future channel adapter cannot accidentally bypass it.

### Idempotency and delivery semantics

- The intake path is at-least-once from every real channel (webhook redelivery,
  extension retry, share re-fire, Discord gateway resume). Dedup on
  `idempotency_key` first, then fall back to the existing `create_and_enqueue_job()`
  content dedup. One logical submit == one job.
- `POST /api/intake/action` must be idempotent per `(actor, action_id)` so a
  double-tapped dashboard button or re-delivered callback does not double-apply.

### Datastore concurrency reality

- SQLite WAL is single-writer. The intake fan-out multiplies write pressure
  (jobs, intake_state, channels, history). Keep intake writes short, batched,
  and off the request's critical path where possible; do not hold a write
  transaction across an external call (Gemini, Drive, Telegram send).
- Channel resolution is a read-then-maybe-insert race under concurrent
  submits from the same new user. Use an upsert / `INSERT ... ON CONFLICT` keyed
  on `(user_id, type, external_id)` with a unique index, not select-then-insert.
- If write contention becomes the ceiling, that is the signal to plan the
  SQLite→server-DB move — call it out explicitly rather than discovering it in
  production. This does not change the plan's phases; it changes `src/database.py`
  underneath them.

### State lifecycle

- `intake_state.expires_at` needs an actual sweeper (scheduled job) that reaps
  expired rows; an expiry column no one enforces is a slow leak.
- Pending state is per-channel; reconcile what "one user, two channels, two
  pending flows" means before Phase 3 ships (last-write-wins vs. per-channel
  isolation). Document the choice.

### Observability

- Structured logs and metrics tagged with `channel_type`, `user_id`, and a
  request/correlation id that flows from adapter → router → job. Without it,
  "which channel is generating load / errors" is unanswerable.
- Counters for intake volume, dedup hits, rate-limit rejections, upload
  rejections, and router error kinds, per channel.

### Migration safety (Phase 9)

- Backfill in bounded batches with progress tracking and resumability, never one
  giant transaction.
- Dual-write behind a feature flag with a documented rollback: prefer `user_id`
  on read only after backfill is verified, and keep `chat_id` authoritative
  until the cutover is signed off.
- Add a reconciliation check (counts + spot-diff `chat_id` vs `user_id`
  ownership) before removing any `chat_id` dependency.

## Implementation Phases

### Phase 1 - Dashboard Intake MVP

Goal: ship `/intake` as a first-class dashboard page using current ownership.

Tasks:

- [ ] Add `web/app/(dashboard)/intake/page.tsx`.
- [ ] Add `web/components/intake/*` composer/thread/action components.
- [ ] Add `POST /api/intake/message` for text and URL payloads.
- [ ] Enforce per-user rate limit + text/URL length caps on the endpoint.
- [ ] Honor `Idempotency-Key` so a double-submit returns one job.
- [ ] Reuse `create_and_enqueue_job()` for URL intake.
- [ ] Show created job result inline with link to `/jobs/{id}`.
- [ ] Add navigation entry to app shell/sidebar.
- [ ] Add tests for successful URL submit, unsupported URL, auth errors,
      rate-limit rejection, and idempotent re-submit.

Acceptance criteria:

- signed-in approved user can submit a URL from `/intake`
- created job appears in Feed and in the intake response
- invalid URLs return a clear response
- a repeated submit with the same idempotency key returns the original job
- oversized/abusive input is rejected before any job is created
- page works without Telegram
- no database ownership migration required yet

### Phase 2 - Shared Intake Router

Goal: introduce channel-neutral intake models and route dashboard messages
through them.

Tasks:

- [ ] Add `src/intake/models.py`.
- [ ] Add `src/intake/router.py`.
- [ ] Add `src/intake/responses.py`.
- [ ] Add `src/intake/state.py`.
- [ ] Move URL routing from dashboard endpoint into the intake router.
- [ ] Keep `/api/jobs` intact.
- [ ] Add tests for `IntakeMessage -> IntakeResponse`.

Acceptance criteria:

- `/api/intake/message` no longer directly owns job-routing behavior
- intake router handles URL, unsupported text, and command-looking input
- responses are structured enough for dashboard and Telegram renderers

### Phase 3 - Dashboard Conversational State

Goal: support current Telegram pending flows inside the dashboard.

Tasks:

- [ ] Add generic state wrapper around existing `chat_state`.
- [ ] Support `awaiting_intent`.
- [ ] Support `awaiting_freestyle`.
- [ ] Add `GET /api/intake/state`.
- [ ] Add `DELETE /api/intake/state`.
- [ ] Add an `expires_at` and a scheduled sweeper that reaps expired state.
- [ ] Decide and document per-channel vs. last-write-wins pending semantics.
- [ ] Render pending state banner in `/intake`.
- [ ] Add cancel/resume actions.

Acceptance criteria:

- user can start an intent/freestyle flow in dashboard
- refresh preserves pending state
- cancel clears pending state
- expired state is reaped automatically, not left to accumulate
- state remains scoped to the signed-in user

### Phase 4 - Dashboard Files And Actions

Goal: bring document/photo intake and inline actions into dashboard intake.

Tasks:

- [ ] Add `POST /api/intake/upload` with size caps, MIME allowlist + content
      sniffing, and a per-user daily byte/upload quota.
- [ ] Support PDF upload through existing document pipeline.
- [ ] Support image upload through photo/OCR pipeline or a new queued path if needed.
- [ ] Add `POST /api/intake/action`, idempotent per `(actor, action_id)`.
- [ ] Represent Telegram inline keyboards as generic actions.
- [ ] Render actions as dashboard buttons.

Acceptance criteria:

- PDF upload creates a document job
- image upload follows the existing Ownix photo behavior or an explicitly documented replacement path
- oversized, wrong-type, or over-quota uploads are rejected before the pipeline runs
- a double-fired action does not double-apply
- dashboard can perform actions that are no longer Telegram-specific

### Phase 5 - Telegram Adapter Refactor

Goal: make Telegram call the shared intake router.

Tasks:

- [ ] Add `src/channels/telegram/adapter.py`.
- [ ] Convert Telegram updates into `IntakeMessage`.
- [ ] Convert `IntakeResponse` into Telegram send/edit operations.
- [ ] Move reusable command behavior out of `src/telegram/webhook.py`.
- [ ] Keep ops-bot behavior separate unless a command is truly shared.
- [ ] Preserve existing webhook tests during extraction.

Acceptance criteria:

- Telegram behavior remains functionally equivalent
- dashboard and Telegram share core URL/command/state behavior
- Telegram-specific code is mainly transport parsing and rendering

### Phase 6 - PWA Share Target To Intake

Goal: make system share open Ownix Intake instead of Feed prefill.

Tasks:

- [ ] Change `web/app/manifest.json` share target action to `/intake/share`.
- [ ] Add `/intake/share` route that extracts shared title/text/url.
- [ ] Reuse `web/lib/share-target.ts`.
- [ ] If authenticated, prefill or auto-submit into `/intake`.
- [ ] If unauthenticated, preserve shared payload through login and return to `/intake`.
- [ ] Decide whether first iteration remains GET or moves directly to POST/multipart.

Acceptance criteria:

- Android installed PWA can receive shared URL into Ownix Intake
- unsupported/missing URL still lands in a useful intake state
- unauthenticated user does not lose the shared URL
- existing `/feed` share-target behavior is intentionally replaced or redirected

### Phase 7 - Chrome Extension MVP

Goal: capture the current browser context outside the PWA.

Tasks:

- [ ] Add Chrome extension project folder.
- [ ] Add Manifest V3 `manifest.json`.
- [ ] Add background service worker.
- [ ] Add toolbar popup.
- [ ] Add context menu items for page/link/selection.
- [ ] Add API client for `/api/intake/message`.
- [ ] Implement initial auth using existing web session if viable locally.
- [ ] Document install/load-unpacked steps.

Acceptance criteria:

- extension can send current tab URL to Ownix
- extension can send right-clicked link to Ownix
- extension shows success/error state
- created job opens in dashboard

### Phase 8 - Extension Pairing Auth

Goal: make extension auth production-safe.

Tasks:

- [ ] Add extension pairing model to the database.
- [ ] Add dashboard endpoint to create a one-time, short-TTL pairing code
      (single-use, rate-limited).
- [ ] Add extension endpoint to redeem pairing code.
- [ ] Store only a hash of the extension token server-side; show the raw token
      once, at pairing time.
- [ ] Rate-limit extension-token traffic and record last-used per token.
- [ ] Add token revocation (and optional expiry/rotation).
- [ ] Add extension settings UI listing active tokens with revoke.

Acceptance criteria:

- extension does not need to store raw dashboard session cookie
- pairing codes are single-use and expire quickly
- raw tokens are never stored or logged server-side (hash only)
- user can revoke extension access and it takes effect immediately
- API can distinguish dashboard session traffic from extension token traffic

### Phase 9 - User Identity Migration

Goal: migrate from `chat_id` ownership to durable `user_id` ownership.

Tasks:

- [ ] Add `users.id` or a parallel durable user id column/table.
- [ ] Add `user_identities`.
- [ ] Add `intake_channels`.
- [ ] Backfill existing Telegram users.
- [ ] Add `user_id` to jobs and user-owned tables.
- [ ] Dual-write `chat_id` and `user_id`.
- [ ] Update API ownership checks to prefer `user_id`.
- [ ] Migrate Google tokens to `user_id`.
- [ ] Remove direct `chat_id` dependency from new intake APIs.

Acceptance criteria:

- email/dashboard user is the durable owner
- Telegram identity maps to the same user
- existing jobs remain visible to existing users
- future Discord identity can attach to the same user

### Phase 10 - Discord Adapter

Goal: prove the adapter model with a second chat channel.

Tasks:

- [ ] Add Discord OAuth/bot identity mapping.
- [ ] Add `src/channels/discord/*`.
- [ ] Convert Discord messages to `IntakeMessage`.
- [ ] Render `IntakeResponse` to Discord messages/buttons.
- [ ] Store Discord channel identity in `intake_channels`.
- [ ] Reuse shared command and job behavior.

Acceptance criteria:

- Discord can submit URLs into the same Ownix account
- Discord does not fork business logic from dashboard/Telegram
- channel-specific behavior stays inside the Discord adapter

## Testing Strategy

Backend tests:

- intake router unit tests
- dashboard API endpoint tests
- idempotency tests (repeated submit/action yields one job/effect)
- rate-limit and payload-cap rejection tests
- state lifecycle + expiry-sweeper tests
- upload validation tests (size, MIME sniffing, quota)
- channel-resolution concurrency/upsert test
- migration backfill + dual-write reconciliation tests (Phase 9)
- Telegram adapter regression tests
- extension token auth tests when pairing exists (hash-only, revocation, TTL)

Frontend tests:

- `/intake` page render
- URL submit success/error
- pending state banner
- upload component states
- action buttons
- share-target extraction

Extension tests:

- API client payload construction
- context menu payload normalization
- popup success/error states

Manual verification:

- dashboard URL intake
- dashboard PDF upload
- dashboard pending freestyle/intent flow
- Android installed PWA share target
- Chrome extension current tab capture
- Chrome extension right-click link capture
- Telegram legacy behavior after adapter refactor

## Open Questions

1. Should `/intake` auto-submit shared URLs, or prefill and let the user confirm?
2. Should Chrome extension capture be one-click silent, or always show a confirmation popup?
3. Should extension side panel ship in MVP, or only popup/context menu?
4. Should image upload inside dashboard use the existing inline Telegram photo path or be converted to a queued job first?
5. Should intake history be stored as a durable thread, or reconstructed from jobs/state/actions?
6. What is the first production auth method for standalone non-Telegram users: email magic link, Google sign-in, or both?
7. Is iOS share sheet important enough to justify a native wrapper/share extension, or is Shortcut/bookmarklet acceptable for now?

## Non-Goals

Do not build in the first pass:

- full Discord support
- native iOS app
- native Android app
- email inbox forwarding
- replacement of all `chat_id` columns in one migration
- ops-bot rewrite
- public unauthenticated intake
- new processing pipelines

## Definition Of Done

This plan is complete when:

- `/intake` is the primary dashboard intake surface
- dashboard, Telegram, PWA share target, and Chrome extension all use the same intake core
- Telegram is an adapter rather than the owner of product behavior
- share-target payloads land in Intake, not Feed prefill
- Chrome extension can capture current page and context-menu links
- intake state works outside Telegram
- ownership is ready for `user_id` and future Discord identity
- every exposed intake surface is rate-limited, idempotent, and size-capped
- intake contract is versioned so channels can evolve independently
- expired intake state is swept, not leaked
- tests cover the shared router, dashboard endpoint, share target, and adapter behavior
