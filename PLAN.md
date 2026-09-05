# Plan: Email digest pipeline (newsletter → curated candidate feed)

_Locked via claudex-loop — by Claude + Leon_

## Goal

Let a user route a newsletter subscription (by giving out an Ownix-generated
inbound alias, either as the subscribe-form address or as a forwarding
target) into Ownix. Each incoming digest email is parsed for real content
links (resolving ESP tracking-redirect wrappers to actual destinations),
which surface as lightweight, non-committal **candidates** in a new
`newsletter-digest` dashboard page — a feed the user can click into and
individually promote to a real job (full auto-routed pipeline processing,
identical to a manual paste) — alongside a Gemini-authored editorial summary
of that issue. Candidates accumulate per-newsletter (one Space per
subscription, growing over time), not per-issue. No link is ever processed,
enriched, or spent-on automatically — only the deliberate per-candidate
"create job" click triggers real pipeline work, preserving the same
human-judgment boundary the existing `Ctrl+Shift+1` capture command and
ADR-0051 already establish elsewhere in this codebase.

## Approach

### 1. Schema (new migration)

- `newsletter_subscriptions`: `id`, `chat_id`, `name` (user label), `sender_email`
  (lowercase, allowlisted From address), `alias_local_part` (opaque token,
  globally unique, **~22 base64url chars, ~130 bits** — revised up from an
  initial 8-char draft per Codex round 1: a public catch-all address with no
  inbound rate limit needs real capability-secret entropy, not a display
  token), `space_id` (FK → `spaces.id`, `ON DELETE CASCADE`), `created_at`.
  One row per registered newsletter.
- `digest_candidates`: `id`, `space_id` (FK → `spaces.id`, `ON DELETE CASCADE`),
  `url` (the actual resolved, post-redirect destination — **left intact**,
  this is what gets displayed/clicked/promoted), `canonical_url` (same URL
  with common tracking query params — `utm_*`/`fbclid`/`gclid`/`mc_[ce]id`/`_ga` —
  **`ref` deliberately excluded from the strip-list** (Codex round 4: I'd
  kept `ref` in the denylist even after round 3 named it as semantically
  risky — stripping it into the dedup key can collapse two genuinely
  different destinations into one `canonical_url`, silently dropping the
  second as a false-positive duplicate; only params with no observed
  semantic role — pure analytics tags — get stripped) — stripped, used
  **only** for the uniqueness check; Codex round 2 flagged repeat-issue
  dedup breaking on varying tracking params, and round 3 walked back my
  round-2 call to store one column only: the real, unmodified resolved URL
  has to survive intact for display/promotion — only the dedup key gets
  canonicalized), `title`,
  `thumbnail_url` (both nullable, from a cheap OG fetch), `status`
  (`pending` / `promoting` / `promoted` / `dismissed`), `job_id` (nullable,
  set on promotion), `created_at`. `UNIQUE(space_id, canonical_url)` guards
  re-insertion of an already-seen candidate on a later issue. The
  `promoting` state is a claim lock — see step 5.
- `email_digest_payloads`: `job_id` (PK, FK → `jobs.id`, `ON DELETE CASCADE`),
  `receipt_key` (the `sha256(alias_token + ":" + message_id)` value itself,
  **`UNIQUE(subscription_id, receipt_key)` at the DB level** — Codex round 5:
  `find_recent_job_by_url()` is app-level read-then-write with no DB
  constraint behind it, so two truly concurrent deliveries of the same
  `Message-ID` — a real possibility with retry-happy mail infrastructure —
  could both pass the check and create duplicate receipt jobs/processing
  runs. **Correction to my own round-5 fix** (Codex round 6: `job_id` is a
  non-null FK to `jobs.id`, so this row cannot be inserted *before* the job
  row exists — my round-5 wording was self-contradictory): the job row is
  created **first**, then this payload/receipt row is inserted **in the
  same transaction**; if the `UNIQUE(subscription_id, receipt_key)`
  constraint rejects it (a genuinely concurrent duplicate), the whole
  transaction rolls back — including the just-created job row, so no orphan
  job survives — and the `IntegrityError` is the signal to look up and
  reuse the existing `job_id` via `receipt_key` instead of creating a second
  one), `subscription_id` (FK → `newsletter_subscriptions.id`, **nullable, `ON
  DELETE SET NULL`** — Codex round 4: with FK enforcement on, a plain
  cascade-less reference would make subscription deletion fail outright
  once a payload row references it; `SET NULL` lets the subscription go
  while the row survives for existing cap-accounting purposes, which stop
  mattering once the subscription itself is gone. Kept even after content is
  cleared — Codex round 2: needed so a subscription's daily issue-count cap
  can be counted, since a receipt job itself carries no subscription
  reference), `subject`, `html`, `text` (all three **nulled out
  by the processor once step 8 completes** — Codex round 2: indefinite
  retention of full newsletter HTML/text is unnecessary exposure of
  potentially-personal content; matches ADR-0048's "the HTML is not
  persisted" precedent, just deferred one step since the processor needs the
  body during the run). Inserted in the **same transaction** as the receipt
  job row (step 3) — durable storage, not Redis (Codex round 1: a Redis-only
  payload can be dequeued-before-written or dropped by a TTL/restart; the
  job row and its payload must land atomically together, same transaction,
  before enqueue).
- Creating a subscription creates its Space in the same transaction
  (`icon = 'newspaper'`, default color) — reuses the existing `spaces` table,
  no new "collection" concept. **Deleting a subscription explicitly deletes
  its Space too** (the FK cascade only runs Space→subscription, not the
  reverse — Codex round 1) — the subscription route's `DELETE` handler
  deletes the Space row itself, cascading normally into `space_urls`/
  `context_blobs`/the subscription row. **Receipt jobs (`email_digest:<hash>`)
  are deliberately left behind** — Codex round 2 raised these as orphaned
  after subscription deletion, but this matches existing product philosophy
  exactly: deleting a Space today never deletes its pinned jobs either (only
  the `space_urls` pin — CONTEXT.md's [[Job delete]]/[[Space]] entries:
  "the card is a receipt, not a container"). **Retained failed-run payloads
  are force-cleared on subscription deletion** (Codex round 5 caught a real
  contradiction: I'd written "payload content is already nulled by the time
  a subscription is deleted," but a failed, not-yet-retried digest job
  deliberately keeps its payload for retry — those two statements collide
  exactly there). Resolution: the subscription's `DELETE` route nulls any
  remaining `email_digest_payloads.subject/html/text` for that
  `subscription_id` as part of the same deletion — a failed, un-retried
  digest's content doesn't survive deleting the subscription it belongs to,
  same as everything else that subscription owns. So nothing sensitive
  lingers in every case, not just the already-processed one — an inert job
  row is the same harmless residue Bookmark import already leaves behind
  indefinitely.

### 2. Inbound transport (outside the Python repo)

- **Cloudflare Email Routing**: one catch-all rule on `leondev.xyz` → one
  Worker (plus-addressing is not usable here — Cloudflare collapses
  `user+detail@` to the `user@` rule, so the opaque token must be the whole
  local-part).
- **Worker** (`ops/email-worker/`, new small TS project, Wrangler-deployed —
  not part of Docker Compose): uses `postal-mime` to parse `message.raw` into
  `{subject, html, text, messageId}`, **plus `from` sent as the normalized
  lowercase addr-spec only** — `parsedEmail.from.address.toLowerCase()`, not
  the raw `From` header string (Codex round 4: `postal-mime` returns `from`
  as a structured `{name, address}` object; forwarding anything other than
  the bare address risks the Python side's case-insensitive compare failing
  on a display-name-inclusive or differently-encoded string) — *inside the
  Worker*, then
  `fetch()`s that JSON — **plus `envelopeTo: message.to`, read directly off
  the Workers runtime's `ForwardableEmailMessage` object, not off postal-
  mime's parsed header** (Codex round 2: a parsed MIME `To:` header is
  unreliable for catch-all/BCC/forwarded mail — the envelope recipient
  Cloudflare itself used to route the message is the only fact the alias
  lookup can trust) — to `POST https://api.leondev.xyz/webhook/email-digest`
  with header `X-Ownix-Email-Secret: <shared secret>`. Parsing happens once,
  in the Worker — the Python side never touches raw MIME.
- **Trust boundary**: a shared-secret header checked with
  `secrets.compare_digest`, exactly mirroring the existing
  `TELEGRAM_WEBHOOK_SECRET` / `OPS_WEBHOOK_SECRET` pattern
  (`src/telegram/webhook.py:2005/2117`). SPF/DKIM verdicts are not reliably
  exposed to a Worker (confirmed via research — a documented
  `cloudflare/workerd` gap), so authenticity is *not* checked that way.
- New setting: `EMAIL_WEBHOOK_SECRET: str = Field(min_length=1)` in
  `src/config.py` — **required at startup**, matching `TELEGRAM_WEBHOOK_SECRET`'s
  fail-fast pattern rather than `OPS_WEBHOOK_SECRET`'s optional-with-warning
  one (Codex round 2: an unset-secret behavior was previously unspecified;
  the weaker existing precedent has a latent gap where an absent header
  against an unset secret both compare equal-empty, which this feature
  should not copy).

### 3. Webhook (new `src/api/email_webhook.py`, mounted in `main.py`)

**Must be added to `_OPEN_PATHS` in `src/auth/middleware.py`** (currently
`frozenset(["/webhook", "/webhook/ops", "/health"])`) — otherwise the session
middleware blocks it exactly like every other `/api/*` route (Codex round 1:
this was missing from the original draft entirely).

`POST /webhook/email-digest`:
1. Check `X-Ownix-Email-Secret` via `compare_digest` — reject (log + 200, to
   avoid Cloudflare retry-storms on a rejected message) if missing/wrong.
2. Extract the alias token from **`envelopeTo`** (not a parsed header — see
   above); look up `newsletter_subscriptions` by `alias_local_part`. No
   match → log + 200, silently drop (no enumeration signal).
3. Check `from` (case-insensitive) against the subscription's `sender_email`.
   Mismatch → log + 200, drop. **Note this is a noise filter, not
   authentication** (Codex round 1): a parsed `From` header is trivially
   spoofable by anyone who already has the alias, so this only raises the
   bar for an opportunistic/leaked-alias sender, not a targeted one. The
   alias's own entropy (above) is the actual security boundary; the sender
   check just keeps an honest subscription's candidate feed clean of
   unrelated mail.
4. Enforce a **payload byte-size cap** (e.g. 2 MB combined `html`+`text` —
   generous for any real newsletter, defense-in-depth under Cloudflare's own
   25 MiB message cap). **The 50-link-per-issue cap lives in the processor
   (step 3 below), not here** (Codex round 2 correction: the webhook never
   parses HTML, so it cannot count links — only the processor, which does
   the extraction, can enforce that cap).
5. Compute the receipt identity key (`sha256(alias_token + ":" + message_id)`,
   same formula step 6 uses for the job's `url`) and check for an existing
   job with that URL **before** applying the daily-issue cap (Codex round 4:
   my round-3 fix put the cap check ahead of the dedup check, so a
   legitimate retry of an already-accepted message could get silently
   dropped by a full cap instead of recognized as the duplicate it is — only
   a genuinely new message counts against the **per-subscription daily
   issue-count cap** (20 receipt jobs per rolling 24h, counted via
   `email_digest_payloads.subscription_id` joined to `jobs.created_at`).
   Reject over-cap *new* deliveries with log + 200.
6. Create one receipt job — same shape as Bookmark import (ADR-0048):
   `content_type='link'`,
   `url='email_digest:<sha256(alias_token + ":" + message_id)[:16]>'` — using
   the email's `Message-ID` (forwarded by the Worker), not a timestamp
   (Codex round 2: `received_at` isn't a stable identity, so a Cloudflare
   Worker retry of the same delivery would have created a second receipt job
   and a second processing pass; hashing the actual `Message-ID` makes a
   retried delivery collide with the existing job, and existing job-URL
   dedup — `find_recent_job_by_url` — handles the rest for free, same as
   every other pipeline's dedup, no new mechanism needed. A missing
   `Message-ID` — rare, but not impossible — falls back to hashing the raw
   `html`/`text` content instead of a timestamp, preserving the same
   stable-identity property) — and insert its `email_digest_payloads` row
   (including `subscription_id`, indexed —
   `CREATE INDEX idx_email_digest_payloads_subscription_id ON
   email_digest_payloads(subscription_id)`, Codex round 3: the daily-cap
   count needs this or it's a growing unindexed scan) **in the same
   transaction**, via the existing shared job-creation core extended to
   accept an optional payload-insert callback (or a small dedicated insert
   wrapping both writes in one `async with database.transaction()`), so the
   payload is durably committed *before* the task is enqueued — never a
   separate after-the-fact write. Enqueue
   `{"task": "email_digest", "job_id": ..., "subscription_id": ...}` only
   after that commit succeeds. **If the URL-dedup hit finds an existing job
   still in `pending`** (Codex round 3: a crash between this commit and the
   Redis push would otherwise leave a retried delivery silently deduping
   against a job that was never actually queued) — re-push the task
   envelope for that existing job_id instead of treating the duplicate as
   fully handled. A narrow, targeted fix for this one task's duplicate-
   delivery path, not an attempt to close the general lost-enqueue window
   every `create_and_enqueue_job` caller already lives with today.

### 4. Worker task (new `src/processors/email_digest.py`, new discriminator
in `_TASK_HANDLERS`, `worker.py`)

0. **First action, before touching the payload**: atomically claim the job —
   `UPDATE jobs SET status='processing' WHERE id=? AND status IN
   ('pending','error')`, no-op (return immediately) if the update matched
   nothing. Codex round 5: the webhook's "re-push on `pending`" duplicate
   handling (step 6) can't tell a genuinely-never-enqueued job apart from
   one that's validly queued but just hasn't started yet — both look
   `pending`. Rather than trying to make that distinction perfect at the
   webhook layer, the processor makes running the same task envelope twice
   (from any source — a legitimate re-push, a Cloudflare Worker retry, the
   dedicated manual retry action) safe by construction: only one concurrent
   run ever gets past this claim. Mirrors the same atomic-slot-lock idiom
   used for candidate promotion and PRD generation.
1. Read `{subject, html, text}` back from `email_digest_payloads` by `job_id`.
2. Extract `<a href>` links from `html` via a small new `HTMLParser` subclass
   (mirrors `_BookmarkParser` in `src/utils/bookmarks_html.py` — no new
   dependency).
3. Drop non-content links: tracking-pixel `<img>` sources (not links to begin
   with — irrelevant to `<a>` extraction, but any 1x1-image-hosting domains
   seen in `href`s get filtered too), unsubscribe/manage-preferences links,
   and the "view online"/"view in browser" wrapper link itself (matched by
   anchor text, case-insensitive) — held aside rather than discarded. Cap
   the surviving link list at 50 (step 3's per-issue budget).
4. Resolve each remaining link's real destination via a **new small
   content-type-agnostic redirect resolver** added to `src/utils/public_html.py`
   (built on the existing `_fetch_pinned`, same SSRF-pinning/3-hop-cap
   machinery, but returning `str(response.url)` on the first non-redirect
   response regardless of content type — Codex round 2: `fetch_public_html`
   itself rejects any terminal response that isn't `text/html`, so a direct
   PDF/document link behind an ESP tracking wrapper would silently vanish
   here even though `detect_pipeline()` can classify document URLs fine once
   promoted). Confirmed: plain HTTP redirect-following is sufficient for
   Mailchimp/Beehiiv/ConvertKit/Substack wrappers — no JS rendering needed.
5. **If zero usable links resolved after step 4**, fetch the held-aside "view
   online" link's landing page via `fetch_public_html` (this step *does*
   need the HTML body, unlike step 4) and re-run steps 2–4 against its HTML.
6. Insert surviving links as `digest_candidates` rows: `url` = the resolved
   destination as-is, `canonical_url` = the same with tracking query params
   stripped (round 3: stripping only feeds the dedup key, never the stored/
   clickable URL) — capped at 50 per issue (Codex round 2: this cap belongs
   here, where extraction happens, not in the webhook). `INSERT OR IGNORE`
   on the `UNIQUE(space_id, canonical_url)` constraint handles repeat-issue
   dedup for free. For each newly-inserted row, fetch OG title/image via the
   existing `src/utils/og_image.py` (reused from the Link pipeline).
7. One Gemini call: `subject` + cleaned `text`/stripped-`html` → short
   editorial framing of the issue. Insert as a new `context_blobs` row for
   the space (existing multi-blob, ordered support — each issue appends its
   own blob rather than overwriting one).
8. Null out `email_digest_payloads.subject/html/text` for this `job_id`
   (Codex round 2: no reason to keep full newsletter content around once
   candidates/blob are extracted — matches ADR-0048's "the HTML is not
   persisted" precedent, just deferred until the processing run that needs
   the body has finished). The row itself (now just `job_id`+`subscription_id`)
   stays, so the daily-cap count in webhook step 4 keeps working. Mark the
   receipt job `done`. Non-fatal failures (Gemini down, OG fetch fails for a
   given link) degrade per-candidate/per-blob, not job-fatal — same posture
   as `Short transcript step`/`Enrichment`'s non-fatal design.

### 5. Promotion (extends `src/api/spaces.py` or a small new
`src/api/newsletter_digest.py` — TBD at implementation time, whichever the
existing route module organization favors)

- `POST /api/newsletter-digest/{sub_id}/candidates/{candidate_id}/promote`:
  first **atomically claims** the candidate — `UPDATE digest_candidates SET
  status='promoting' WHERE id=? AND status='pending'`, proceeding only if the
  update actually matched a row — before doing anything else, so two
  concurrent clicks (or a click racing a repeat-issue re-scan) can't both
  pass and create duplicate jobs (Codex round 1: `create_and_enqueue_job`'s
  own dedup is read-before-write with no unique constraint backing it, so
  the race has to be closed at the candidate-claim layer instead). This
  mirrors the existing atomic-slot-lock pattern PRD generation already uses
  (`prd_auto_status`, PRD.md §14.4: `UPDATE ... SET status='generating' WHERE
  status IS NULL OR status='error'`). Then runs `detect_pipeline()` on the
  candidate's `url` and branches: **`document` → delegates to
  `POST /api/parsed/url`** (`upload_url`, `src/api/parsed.py:123`) — verified
  `POST /api/jobs` itself hard-rejects document pipeline with a 422
  ("Document URLs belong in the Doc Parser", `src/api/jobs.py:214`), so a
  document candidate promoted through that handler would simply fail (Codex
  round 3); **everything else → the exact same handler `POST /api/jobs`
  uses** (allowed-domain lookup, template rules included — Codex round 1: a
  bare `detect_pipeline()` + `create_and_enqueue_job()` call would silently
  diverge from what a human pasting that URL through the dashboard actually
  gets), not a reimplementation of its logic. On success: set
  `digest_candidates.status='promoted'`, `job_id=<new job>`, and pin into
  `space_urls` (so it now also shows in the Space's own URLs tab via the
  existing `/spaces/{id}` surface). On failure: reset `status` back to
  `pending` so the claim isn't a permanent dead end.
- `DELETE .../candidates/{candidate_id}`: dismiss (status='dismissed', stays
  in the dedup set so it never resurfaces from a later issue).

**Ownership on every new route** (Codex round 2: `sub_id`/`candidate_id` in a
raw path param is an IDOR risk without an explicit gate): every
`newsletter-digest` route loads `newsletter_subscriptions` scoped by
`(id, chat_id)` first — mirroring the existing `_get_owned_space` pattern in
`src/api/spaces.py` — and candidate lookups are constrained through that
subscription's `space_id`, never a bare `candidate_id` alone.

### 6. Subscription management API

- `POST /api/newsletter-digest`: `{name, sender_email}` → generates
  `alias_local_part`, creates the Space, returns the full alias
  (`u_xxxxxxxx@leondev.xyz`) for the user to paste into the newsletter's
  subscribe form or their own forwarding rule.
- `GET /api/newsletter-digest`: list subscriptions (name, alias, Space id,
  candidate counts).
- `GET /api/newsletter-digest/{id}/candidates`: the candidate feed.
- Context blobs need no new endpoints — reuse the existing
  `/api/spaces/{id}/blobs` CRUD as-is.

### 7. Frontend (`web/app/(dashboard)/newsletter-digest/`, new route)

- Index: list of subscriptions, each showing its alias (copy button), name,
  candidate count; an "add newsletter" form (name + sender email → alias).
- Detail (`/newsletter-digest/[id]`): candidate feed (clickable cards —
  title/thumbnail/URL — each with a "Create job" button and a dismiss
  action) plus the Context list (reusing the same `MarkdownEditor` component
  Space's Context tab already uses) rendered read-mostly (auto-generated,
  editable like any other blob).
- New page, not a variant of `/spaces/[id]` — candidates aren't jobs, so the
  existing Space detail page's URLs tab (which only ever lists pinned jobs)
  doesn't fit; a promoted candidate does show up there too, automatically,
  via the `space_urls` pin in step 5.

## Key decisions & tradeoffs

- **Candidates, not auto-created jobs.** Every extracted link is a cheap,
  non-committal row; only an explicit per-item click spends a real job/
  pipeline run. Resolves the ADR-0051 Second-Law tension directly — the
  subscription itself is the deliberate act; per-link processing stays a
  second deliberate act, same as everywhere else in the codebase.
- **One persistent Space per newsletter**, keyed by registered sender
  identity, not one Space per issue — avoids a dated-Space flood (the same
  hoarding-graveyard failure mode ADR-0051's brand rationale already named).
- **Allowlist-gated aliases**: a subscription registers its sender email
  upfront; mail from any other sender to that alias is silently dropped.
  Bounds the blast radius of a leaked/guessed alias token.
- **"View online" fallback fetch, not a v1 gap**: when a newsletter (the
  documented Substack "everything behind one wrapper link" pattern) yields
  zero inline content links, the pipeline follows that link and re-extracts
  — adds one conditional fetch, no new fetch mechanism (reuses existing
  page-fetch utilities).
- **Gemini-authored context blob**, one call per incoming issue — matches
  how context blobs work everywhere else in Spaces (the user's own editorial
  lens) and is the part of the feature that actually solves "subscribes and
  never reads it."
- **MIME parsing happens once, in the Cloudflare Worker** (via `postal-mime`),
  not duplicated in Python — the webhook receives already-clean
  `{from, to, subject, html, text}` JSON, so no `email.message` parsing is
  needed on the Python side at all (narrower than the original assumption of
  reusing stdlib `email` parsing).
- **Trust boundary is a shared secret, not SPF/DKIM inspection** — Cloudflare
  Workers don't reliably expose a usable authentication verdict; this
  mirrors the codebase's existing webhook-secret pattern instead of adding a
  new, weaker home-grown check.

## Assumptions

1. Spaces (`spaces`/`space_urls`/`context_blobs`) is the right data
   foundation — reused, not reinvented. New page, not new tables for the
   Space concept itself. — confirmed by user
2. Inbound transport: Cloudflare Email Routing catch-all → Worker → new
   authenticated webhook, not Gmail OAuth polling (blocked by the existing
   restricted-scope rejection in `docs/ops/oauth-verification.md`) and not a
   third-party mail provider account. — confirmed by user; mechanics
   verified via research (`docs/research/2026-09-05-email-digest-claudex-research.md`)
3. New sibling worker task (`email_digest`), not a new `content_type` (SQLite
   `CHECK` can't be altered) and not a branch in an existing processor. —
   confirmed by user, precedent ADR-0048
4. Extracted links are non-committal candidates; promotion reuses the normal
   manual-submission path (`detect_pipeline` + `create_and_enqueue_job`). —
   corrected by user (originally assumed auto-job-creation)
5. Redirect-resolution reuses `src/utils/public_html.py`'s existing helper,
   not a new HTTP client. — confirmed by user
6. No new Python dependency (stdlib `HTMLParser` for link extraction; MIME
   parsing moved entirely into the Worker's `postal-mime`, so not even
   stdlib `email` parsing is needed on the Python side). — refined during
   planning
7. No existing skill in `agent-knowledge/skills/` or `~/.claude/skills/`
   targets email/newsletter ingestion specifically; `brand-lens` is relevant
   background (Second-Law framing) but nothing to auto-load into the build.
   — skill inventory scan
8. Per-newsletter allowlist (sender email registered at subscription-creation
   time), not an open-to-any-sender alias. — confirmed by user
9. "View online" landing-page fallback fetch is in scope for v1, not
   deferred. — confirmed by user
10. Context blob is Gemini-authored per issue, not a literal subject/body
    dump. — confirmed by user

## Risks / open questions

- **Cloudflare Worker deployment is outside this repo's normal build/deploy
  path** (Wrangler, Cloudflare dashboard catch-all rule) — genuinely new ops
  surface, not something a `docker-compose up` or CI run touches. Needs a
  short runbook in `docs/ops/` and is not automatable by an agent session
  the way the rest of this plan is.
- **Sender-match granularity**: matching `from` against a single registered
  `sender_email` assumes a newsletter's sending address is stable per
  issue. Some ESPs vary the sending subdomain per campaign — if that turns
  out to be common for newsletters people actually use, the allowlist may
  need to loosen to a domain-suffix match instead of an exact address match.
  Flagged for Codex/implementation-time attention rather than resolved here.
- **`digest_candidates` OG-fetch cost**: fetching title/thumbnail per
  candidate at ingest time is one more network call per link per issue
  (bounded by a single newsletter's typical link count, now further bounded
  by the 50-link cap — not the 300+ scale ADR-0048 had to defer for). Should
  stay cheap, but worth confirming against a real multi-link newsletter
  during implementation.
- **Receipt-job Feed visibility: firm decision, not deferred** (Codex rounds
  1/3/4 went back and forth on this — settling it here rather than leaving
  it as "check at implementation time"): `email_digest:<hash>` receipt jobs
  are **excluded entirely from the Feed** — a `url NOT LIKE 'email_digest:%'`
  predicate placed in **whichever shared job-scope query underlies list,
  count, and adjacent (prev/next) navigation alike** (Codex round 5: hiding
  it only in `list_jobs()` would still leave a receipt job reachable via
  detail-page prev/next or counted elsewhere if those use a different query
  path — needs locating precisely at implementation time, but the predicate
  belongs in the shared scope, not duplicated ad hoc per entry point), not
  just a rendering tweak — rather than shown-but-special-cased like
  Bookmark import's receipt card. Unlike a bookmark import (a card the user
  meaningfully recognizes — "Bookmarks 8/6/26"), a digest receipt job is
  pure internal plumbing the user experiences entirely through the new
  `newsletter-digest` page; a stray `email_digest:<hash>` row in the main
  Feed adds nothing and is confusing clutter, so it doesn't need the
  half-solved non-navigable-card treatment ADR-0048 settled for at all.
- **Failed-digest retry: a real gap in the generic Recovery panel, worked
  around, not silently relied on.** Read `src/services/job_recovery.py`
  directly (Codex round 4 pushed on this rather than accepting "payloads
  persist" as sufficient): `retry_error()` maps a job's retry task via
  `task_for_content_type(row_content_type)`, keyed **only on `content_type`**
  — but `content_type='link'` is now shared by three different real tasks
  (`link`, `bookmarks`, `email_digest`), which that lookup cannot
  distinguish. Retrying an errored `email_digest` receipt job through the
  generic panel today would incorrectly re-enqueue it as a plain `link` job
  against a non-fetchable `email_digest:<hash>` URL. Fix, scoped to this
  feature: exclude `url LIKE 'email_digest:%'` from **every** consumer of
  `_scope_where()` in `job_recovery.py` — `recovery_summary()`,
  `retry_pending()`, and `_claim_error_rows()`/`retry_error()` alike (Codex
  round 5: my round-4 fix only patched `_claim_error_rows()`; `retry_pending()`
  has the identical content_type-keyed blind spot for stuck-pending rows,
  and letting `recovery_summary()` count a job the panel can't actually fix
  correctly is its own small honesty gap) — cleanest added once, in the
  shared `_scope_where()` helper itself, not duplicated per function — so
  they're correctly left alone as `error`/`pending` rather than mis-retried,
  and add one dedicated "Retry" action in the new `newsletter-digest`
  page/API — scoped
  specifically to `email_digest`-task error jobs — that re-enqueues the
  **same** `job_id` (not `retry_error`'s create-a-new-job-row shape, which
  is what makes its content_type-keyed task lookup necessary in the first
  place). Note: `bookmarks` jobs already have this exact same
  mis-retry exposure today, pre-existing and out of scope for this plan to
  fix — flagged, not silently inherited without comment. Payload retention
  on a failed run (step 8's clear only fires on success) is what makes this
  dedicated retry possible at all; clearing unconditionally in a `finally`
  (considered per Codex round 3) was rejected because it would make a
  failed digest permanently unrecoverable, no better than losing the email
  — matching the same posture every other pipeline already has toward its
  own retry inputs (e.g. a failed document job's GCS blob persists until
  retried or deleted too).

## Out of scope

- Gmail/IMAP polling of a user's real inbox (blocked by the restricted-scope
  decision).
- Full pipeline processing (transcripts, article enrichment) automatically
  triggered on digest arrival — only on explicit promotion.
- A digest-specific export (Spaces' existing export already covers whatever
  ends up pinned via `space_urls`).
- Rate limiting beyond the per-subscription daily issue cap and the
  per-issue link cap (both now specified above) — e.g. cross-subscription
  global throttling, or anything account-wide — is not designed for here.
