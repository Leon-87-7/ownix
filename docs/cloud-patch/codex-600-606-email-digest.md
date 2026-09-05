# Codex prompt — implement issues #600–#606 (email digest pipeline)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `PLAN.md` (repo root) — the full, locked implementation plan for this
   feature (subscriptions → webhook → processor → promotion → frontend →
   recovery fix → ops Worker). This is authoritative. Where it differs from
   anything below or from your own instincts, `PLAN.md` wins.
2. `PLAN-REVIEW-LOG.md` (repo root) — 7 rounds of adversarial review that
   produced `PLAN.md`. Read this when a `PLAN.md` decision looks arbitrary or
   underspecified — the reasoning (and the alternative that was tried and
   rejected) is almost always recorded here. In particular: Round 6 (job
   created before payload row, not after — an FK-ordering correction to an
   earlier round), Round 5 (atomic processor self-claim, `receipt_key`
   uniqueness, recovery-panel exclusion scope), Round 3 (document-pipeline
   promotion branch, `url`/`canonical_url` split), Round 4 (dedup-before-cap
   ordering, sender normalization).
3. `docs/research/2026-09-05-email-digest-claudex-research.md` — primary-source
   research on Cloudflare Email Routing/Workers mechanics, ESP tracking-link
   conventions, and why SPF/DKIM can't be trusted from inside a Worker. Needed
   for #606 and for the webhook's trust-boundary reasoning in #601.
4. `CLAUDE.md` (repo root) — layout, test/lint commands. Run
   `python -m pytest tests -q` via PowerShell only, never through the `rtk`
   Bash hook (`.claude/rules/rtk-tests.md` if present) — `npm test` /
   `npm run lint` for `web/`.
5. `docs/adr/0048-bookmark-import.md` and
   `docs/adr/0051-automatic-bookmark-capture-rejected.md` — precedent for
   reusing `content_type='link'` for a sibling worker task with a synthetic,
   non-navigable `jobs.url` (`bookmarks:<hash>` there, `email_digest:<hash>`
   here), and the product philosophy ("candidates, not auto-jobs" / "the card
   is a receipt, not a container") this feature extends.
6. GitHub issues #600–#606 (`gh issue view <n> --repo Leon-87-7/ownix`) — each
   carries its own acceptance criteria; treat those as the per-slice
   definition of done.

## Key decisions already made (do not relitigate)

- **Schema**: `newsletter_subscriptions`, `digest_candidates`,
  `email_digest_payloads` — exact columns and constraints per `PLAN.md` §1.
  No new `jobs.content_type` value; `email_digest` is a new **task**
  discriminator sharing `content_type='link'`, mirroring ADR-0048's
  `bookmarks` task exactly.
- **Transaction ordering for the receipt job is fixed and non-obvious**: the
  `jobs` row is created **first**, then the `email_digest_payloads` row
  (which has a non-null FK to `jobs.id`) is inserted in the **same
  transaction**. A `UNIQUE(subscription_id, receipt_key)` conflict on that
  insert rolls back the whole transaction (job included); catch the
  conflict and look up/reuse the existing `job_id` by `receipt_key` instead
  of creating a duplicate. Do not insert the payload before the job — that
  was tried and reverted in Review Round 6 for exactly this FK reason.
- **Step ordering inside the webhook**: dedup check (via the receipt-job
  URL / `receipt_key`) runs **before** the daily-cap check. Only a genuinely
  new message counts against the cap. Getting this backwards (checked and
  reverted in Round 4) silently drops legitimate retries.
- **The processor's first action is an atomic self-claim**:
  `UPDATE jobs SET status='processing' WHERE id=? AND status IN
  ('pending','error')`, no-op if it matched nothing. This is what makes
  running the same task envelope twice (webhook re-push, Cloudflare retry,
  the dedicated manual retry from #605) safe, rather than relying on the
  webhook's duplicate-detection being perfect.
- **Sender-address check is a noise filter, not authentication.** Say so in
  code comments if you touch that logic — the alias's own entropy is the
  real boundary.
- **`canonical_url` strips only `utm_*`/`fbclid`/`gclid`/`mc_[ce]id`/`_ga`.
  `ref` is deliberately excluded** (Round 4 reversed an earlier inclusion) —
  do not add it back. `url` (the real resolved destination) is never
  stripped; only `canonical_url` is, and only for the `UNIQUE(space_id,
  canonical_url)` dedup key.
- **Promotion branches on `detect_pipeline()`**: `document` →
  `POST /api/parsed/url`; everything else → the same handler
  `POST /api/jobs` uses. Never a bare `detect_pipeline()` +
  `create_and_enqueue_job()` reimplementation — that diverges from what a
  human pasting the URL through the dashboard gets (allowed-domain lookup,
  templates).
- **Payload content (`subject`/`html`/`text`) is cleared only on a
  successful processor run**, never unconditionally in a `finally` — a
  failed run needs its payload intact for #605's dedicated retry. This was
  proposed and explicitly rejected in Round 3.
- **Subscription deletion**: the `DELETE` route explicitly deletes the
  Space row itself (FK cascade only runs Space→subscription, not the
  reverse) and force-clears any remaining
  `email_digest_payloads.subject/html/text` for that subscription. Receipt
  jobs themselves are left behind, inert — matches existing Space-deletion
  behavior (deleting a Space never deletes its pinned jobs today either).
- **`email_digest:<hash>` receipt jobs are excluded entirely from the Feed**
  — not shown-with-special-casing like the Bookmark import card. Locate and
  patch *every* shared job-scope query that backs list, count, and
  prev/next navigation, not just one.
- **Recovery-panel exclusion is one predicate in one shared place**: add
  `url NOT LIKE 'email_digest:%'` inside `_scope_where()` in
  `src/services/job_recovery.py:26-32` — it is already the single helper
  behind `recovery_summary()` (line 35), `retry_pending()` (line 61), and
  `_claim_error_rows()` → `retry_error()` (line 195/220), so one edit there
  covers all three. Do not duplicate the predicate per function. Do **not**
  touch `database.fetch_and_mark_stale_jobs()` (the separate stale-processing
  reaper) — out of scope for this fix.
- **`bookmarks` jobs have the identical mis-retry exposure today and it is
  explicitly out of scope for #605** — do not fix it as a drive-by; a
  comment noting it's a known, separate pre-existing gap is fine, a silent
  fix is not (it would be an unrequested, unreviewed behavior change to an
  unrelated pipeline).

## Work order

Implement in issue order — each slice builds on the last. Verify
`python -m pytest tests -q` (backend slices) and `npm run build && npm run
test:run && npm run lint` from `web/` (frontend slice) stay green after each
slice.

### #600 — subscription schema + management API + index page

- New migration in `src/database.py` (append to `_MIGRATIONS`, following the
  existing plain-SQL-list or async-callable pattern used throughout the file
  — e.g. `_MIGRATIONS.append([...])` for simple `CREATE TABLE`/`ALTER TABLE`
  statements). `newsletter_subscriptions` per `PLAN.md` §1: `id`, `chat_id`,
  `name`, `sender_email` (lowercase), `alias_local_part` (~22 base64url
  chars, globally unique), `space_id` FK → `spaces.id` `ON DELETE CASCADE`,
  `created_at`.
- `POST /api/newsletter-digest`: generate `alias_local_part` (use `secrets`,
  not `random`, for the token), create the subscription and its Space
  (`icon='newspaper'`) in the same transaction — mirror `create_space()`
  (`src/database.py:2901-2909`) for the Space insert shape. Return the full
  alias (`u_<token>@leondev.xyz`).
- `GET /api/newsletter-digest`: list the caller's own subscriptions with
  candidate counts (0 for now — `digest_candidates` doesn't exist until
  #602; write the count subquery now so #602 needs no follow-up change here).
- `DELETE /api/newsletter-digest/{id}`: delete the Space explicitly (`await
  database.delete_space(...)`-equivalent for this table), which cascades
  into `space_urls`/`context_blobs`/the subscription row via the existing FK
  behavior. Cross-tenant delete → 404/403.
- **Ownership gating**: every route loads `newsletter_subscriptions` scoped
  by `(id, chat_id)` first, mirroring `_get_owned_space()`
  (`src/api/spaces.py:76-83`) exactly — same 404-then-403 shape.
- Frontend: new `web/app/(dashboard)/newsletter-digest/page.tsx` — list +
  "add newsletter" form (name + sender email → alias) + copy-alias button +
  delete. Follow the `spaces` route's conventions: `web/lib/hooks/` gets a
  `useNewsletterDigestList.ts` (mirror `useSpaceList.ts`), components live
  under `web/components/newsletter-digest/` (kebab-case, colocated
  `.test.tsx`, no barrel files — same layout rule as every other feature
  folder per `web/CLAUDE.md`). Use `apiPost`/`apiDelete` from
  `web/lib/fetch-utils.ts`, not a hand-rolled `fetch`.
- Tests: ownership scoping (cross-tenant 404/403), the create-transaction
  (subscription + Space both land or neither does), delete cascade.

### #601 — inbound webhook + receipt job creation

- New migration: `email_digest_payloads` per `PLAN.md` §1 — `job_id` PK/FK →
  `jobs.id` `ON DELETE CASCADE`, `receipt_key`, `UNIQUE(subscription_id,
  receipt_key)`, `subscription_id` FK → `newsletter_subscriptions.id`
  nullable + `ON DELETE SET NULL`, `subject`/`html`/`text`, plus
  `CREATE INDEX idx_email_digest_payloads_subscription_id ON
  email_digest_payloads(subscription_id)`.
- `src/config.py`: add `EMAIL_WEBHOOK_SECRET: str = Field(min_length=1)`
  next to `TELEGRAM_WEBHOOK_SECRET` (`src/config.py:22`) — in the "Required
  at startup" block, not the optional block `OPS_WEBHOOK_SECRET`
  (`src/config.py:93`) lives in.
- `src/auth/middleware.py:17`: add `"/webhook/email-digest"` to
  `_OPEN_PATHS` (currently `frozenset(["/webhook", "/webhook/ops",
  "/health"])`).
- New `src/api/email_webhook.py`, mounted in `src/main.py` alongside the
  other routers (`src/main.py:175-186` — `app.include_router(...)` block).
  `POST /webhook/email-digest` implementing all 8 steps in `PLAN.md` §3 /
  the issue body verbatim — secret check via `secrets.compare_digest`,
  `envelopeTo`-based alias lookup, case-insensitive sender check, byte-size
  cap, dedup-before-cap ordering (see Key Decisions), the job-then-payload
  transaction with rollback-and-reuse on conflict, re-push on a `pending`
  dedup hit.
- Feed exclusion: find every query underlying job list/count/adjacent-nav
  (start from wherever `src/api/jobs.py` builds its `WHERE` clause — see
  `_scope_where`-style patterns already in this codebase, e.g.
  `src/services/job_recovery.py:26-32` for the idiom) and add a
  `url NOT LIKE 'email_digest:%'` predicate everywhere jobs are listed for
  the Feed. This must be one predicate applied consistently, not
  copy-pasted per call site if a shared helper exists or can reasonably be
  introduced.
- Extend #600's subscription `DELETE` to also null any remaining
  `email_digest_payloads.subject/html/text` for that `subscription_id`.
- Tests: missing/wrong secret, unknown alias, sender mismatch, byte cap,
  cap-vs-dedup ordering (a retry of an already-accepted message must not be
  blocked by a full cap), concurrent duplicate delivery (simulate two
  near-simultaneous requests, assert one job), re-push of a still-`pending`
  duplicate, `email_digest:` jobs absent from Feed list/count/nav, payload
  clearing on subscription delete.

### #602 — processor: link extraction + candidates + context blob

- New migration: `digest_candidates` per `PLAN.md` §1 — `id`, `space_id` FK
  → `spaces.id` `ON DELETE CASCADE`, `url`, `canonical_url`,
  `title`/`thumbnail_url` nullable, `status` enum, `job_id` nullable,
  `created_at`, `UNIQUE(space_id, canonical_url)`.
- New `src/processors/email_digest.py`; register `"email_digest"` in
  `worker.py`'s `_TASK_HANDLERS` dict (`src/worker.py:310-323`), same shape
  as the existing `"bookmarks"` entry.
- Step 0: atomic self-claim (see Key Decisions).
- Link extraction: new `HTMLParser` subclass mirroring `_BookmarkParser` in
  `src/utils/bookmarks_html.py` (the whole file is ~76 lines — read it, this
  is a much simpler extraction: only `<a href>`, no folder-nesting state).
- Redirect resolution: add a new function to `src/utils/public_html.py`
  built on the existing `_fetch_pinned()` helper (`src/utils/public_html.py:
  72-117`, same SSRF-pinning/3-hop-cap machinery already used by
  `fetch_public_html()`/`fetch_public_image()`), but returning the terminal
  URL (`str(response.url)`) on any non-redirect response regardless of
  content type. `fetch_public_html()` itself (line 133-141) rejects any
  terminal response whose content-type isn't `text/html`/
  `application/xhtml+xml` — that's correct for the "view online" fallback
  fetch (step 5, which needs the HTML body) but wrong for tracking-link
  resolution, where a direct PDF/document destination must survive.
- OG metadata: use `extract_essential_og()` from `src/utils/og_image.py`
  (`src/utils/og_image.py:45-49`) directly — one fetch, one parse pass
  returns both `og:title` and `og:image` in the same dict. Do **not** call
  `fetch_og_image_url()` (line 61-65) — it only extracts the image and would
  mean re-fetching the same page to also get a title.
- Candidate insert: `INSERT OR IGNORE` on `UNIQUE(space_id, canonical_url)`
  for free repeat-issue dedup, per row fetch OG data via the above. Cap
  surviving links at 50 before this step (per `PLAN.md` §4 step 3).
- Gemini context blob: one call, insert via the existing
  `create_context_blob()` (`src/database.py:3098-3110`) — appends, matching
  its existing `sort_order = max+1` behavior; never overwrite an existing
  blob.
- Step 8: null `email_digest_payloads.subject/html/text` for this `job_id`
  on success only; mark job `done`. Non-fatal per-candidate/per-blob
  failures must not fail the whole job.
- Tests: candidates get resolved (not tracking-wrapper) URLs; a direct
  PDF/document link behind a tracking wrapper survives; zero-inline-links →
  "view online" fallback produces candidates; re-processing doesn't
  duplicate candidates; a link differing only by a non-analytics query param
  is NOT collapsed; one blob per issue, appended not overwritten; concurrent
  duplicate envelope processes once; payload nulled on success / retained on
  failure; 50-link cap enforced.

### #603 — candidate promotion + dismissal

- `POST /api/newsletter-digest/{sub_id}/candidates/{candidate_id}/promote`:
  atomic claim first — `UPDATE digest_candidates SET status='promoting'
  WHERE id=? AND status='pending'`, proceed only if it matched a row. Mirror
  the exact slot-lock idiom already documented for `prd_auto_status` in
  `docs/seed/PRD.md:3607-3616` (`UPDATE jobs SET prd_auto_status =
  'generating' WHERE id = ? AND (prd_auto_status IS NULL OR
  prd_auto_status = 'error')`).
- Branch on `detect_pipeline()` (`src/utils/validators.py`) result:
  `document` → delegate to `upload_url()` (`src/api/parsed.py:123-128`,
  `POST /api/parsed/url`) — confirmed `src/api/jobs.py:213-214` hard-rejects
  `pipeline == "document"` with a 422 ("Document URLs belong in the Doc
  Parser"), so a document candidate must never go through the `POST
  /api/jobs` path. Everything else → whatever internal function/handler
  `POST /api/jobs`'s `_create_pipeline_job()` (`src/api/jobs.py:211-226`)
  uses, so allowed-domain lookup and template rules apply identically to a
  human pasting the same URL.
- On success: `digest_candidates.status='promoted'`, `job_id=<new job>`, pin
  via `add_space_url()` (`src/database.py:3032-3041`) so it shows in the
  Space's URLs tab too. On failure: reset `status` back to `pending`.
- `DELETE .../candidates/{candidate_id}`: `status='dismissed'` — must stay
  in the dedup set (do not delete the row) so it never resurfaces.
- **Ownership**: scope every route through `(id, chat_id)` on the
  subscription first (mirror `_get_owned_space`), then constrain the
  candidate lookup through that subscription's `space_id` — never a bare
  `candidate_id` alone.
- Tests: promotion creates a job via the actual `POST /api/jobs` path
  (assert allowed-domain/template behavior matches, not a reimplementation);
  document candidate routes through the Doc Parser path; two concurrent
  promotes on the same candidate never create two jobs; promoted candidate
  is pinned into `space_urls` and visible on `/spaces/{id}`; dismissed
  candidate never reappears on re-scan; cross-tenant access rejected.

### #604 — web: newsletter-digest detail page

- New `web/app/(dashboard)/newsletter-digest/[id]/page.tsx`. Use
  `web/app/(dashboard)/spaces/[id]/page.tsx` as the structural reference
  (`PageShell`, `useParams()` for the client-side id — not the async page
  props, per that file's own comment on why — `TabBar`, loading/not-found/
  forbidden states) but this is its own page, not a `spaces/[id]` variant.
- Candidate feed: cards (title/thumbnail/URL, tolerate missing
  title/thumbnail) with a "Create job" button (calls #603's promote
  endpoint) and dismiss (calls delete-candidate). Reflect `promoting`/
  `promoted` state without a full reload — disable/relabel the button, link
  through to the resulting job once `job_id` is set.
- Context list: reuse `MarkdownEditor`
  (`web/components/ui/markdown-editor.tsx`) exactly as
  `web/app/(dashboard)/spaces/[id]/ContextTab.tsx` does — no new editor
  component.
- New hook(s) under `web/lib/hooks/` (mirror `useSpaceDetail.ts` /
  `useSpaceUrls.ts` naming and shape) rather than inlining fetch logic in
  the page component.
- Wire navigation from #600's index page into this detail page (`<Link
  href={\`/newsletter-digest/${id}\`}>`).
- Tests (Vitest + RTL, colocated `.test.tsx`): promote/dismiss interactions,
  blob rendering, navigation from index.

### #605 — job-recovery exclusion + dedicated retry

- `src/services/job_recovery.py`: add `url NOT LIKE 'email_digest:%'` to the
  `conditions` list built in `_scope_where()` (lines 26-32) — this is
  consumed by `recovery_summary()` (35), `retry_pending()` (61), and
  `_claim_error_rows()` (195) underlying `retry_error()` (220), so the one
  edit covers all three call sites without duplication.
- Add one dedicated retry action — an API route (natural home: alongside
  #603/#604's newsletter-digest routes) scoped specifically to
  `email_digest`-task error jobs, that re-enqueues the **same** `job_id`
  (`{"task": "email_digest", "job_id": ...}`), not `retry_error()`'s
  create-a-new-row shape. Reset the job to `pending`/`error`-appropriate
  status before re-enqueueing, matching how other same-job retries in
  `retry_error()` (e.g. the `article`/`long`-with-transcript branches,
  `src/services/job_recovery.py:239-250`) reset status before calling
  `queue.enqueue`.
- Add a one-line comment at the `bookmarks` task's equivalent retry path (or
  in `job_recovery.py` near `_scope_where`) noting that `content_type='link'`
  bookmark-receipt jobs have the identical mis-retry exposure and it is
  explicitly out of scope here — do not fix it.
- Tests: an errored `email_digest` job is untouched by generic
  `retry_error()`/`retry_pending()`, and is absent from `recovery_summary()`
  counts; the dedicated retry action successfully re-enqueues the same
  `job_id` and only accepts `email_digest`-task error jobs (reject/404 on
  anything else, including a `bookmarks` receipt job).

### #606 — ops(email-worker): Cloudflare Worker + runbook (HITL — code + docs only)

The Cloudflare dashboard catch-all rule wiring and live email round-trip
verification need the human's own Cloudflare account — **not yours to do**.
Your part is everything code- and doc-side:

- New `ops/email-worker/` (TypeScript, not part of Docker Compose, not
  wired into this repo's `npm`/`pytest` scripts): `email(message, env, ctx)`
  handler using `postal-mime` to parse `message.raw` into
  `{subject, html, text, messageId}`.
- `from` forwarded as `parsedEmail.from.address.toLowerCase()` only — never
  the raw structured/header value (needed so #601's case-insensitive Python
  compare can't false-negative on a display-name-inclusive string).
- `envelopeTo: message.to` read directly off the Workers runtime object
  (`ForwardableEmailMessage.to`), never off postal-mime's parsed `To:`
  header — per
  `docs/research/2026-09-05-email-digest-claudex-research.md` §2, a parsed
  header is unreliable for catch-all/BCC/forwarded mail.
- `fetch()`s the resulting JSON to
  `https://api.leondev.xyz/webhook/email-digest` with header
  `X-Ownix-Email-Secret: <shared secret via Worker secret binding, wrangler
  secret put>`, matching the header name and comparison scheme #601's
  webhook expects.
- `wrangler.toml` for the Worker.
- `docs/ops/` runbook: Cloudflare dashboard steps for the catch-all Email
  Routing rule, `wrangler secret put` for the shared secret, and how to
  verify a test email round-trips into a receipt job — written for a human
  to execute, not automated.
- Do not attempt to configure the actual Cloudflare catch-all rule, request
  Cloudflare credentials, or claim end-to-end verification happened — state
  plainly in your summary that this step is deferred to the human runbook.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch files outside what each slice above names; don't refactor
  unrelated code in a file you open for one fix (e.g. don't restyle
  unrelated parts of `src/api/jobs.py` while adding the recovery predicate).
- No new Python dependency — stdlib `HTMLParser` for extraction, existing
  `httpx`/`public_html.py` machinery for fetching. `ops/email-worker/` is a
  separate TS project and may use `postal-mime` there only.
- Test commands: `python -m pytest tests -q` (PowerShell, never the `rtk`
  Bash hook) for backend slices; `npm run build && npm run test:run && npm
  run lint` from `web/` for #604. `ruff check src/` for any new/edited
  Python file.
- Every new API route enforces ownership via `(id, chat_id)` scoping before
  touching a row — no bare `candidate_id`/`sub_id` path param used alone.

## Deliverable

Uncommitted working-tree changes implementing #600–#605 fully (schema,
backend routes/processor/worker task, frontend pages, recovery fix) plus
#606's Worker code and runbook (with Cloudflare-side wiring explicitly
called out as deferred to the human). Regression tests per issue's
acceptance criteria. A short summary per issue/slice noting what was done
and anything that needed a judgment call not already settled in `PLAN.md`/
`PLAN-REVIEW-LOG.md`.
