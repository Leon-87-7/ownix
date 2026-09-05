# Codex prompt — implement issues #600–#602 (email digest pipeline, core: subscriptions + webhook + processor)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

This is the **first of four batches** implementing the full email-digest
feature (#600–#606). This batch covers only #600–#602 — subscription
schema/API/index page, the inbound webhook, and the worker processor that
turns a received email into candidates + a context blob. #603–#606
(promotion, the frontend detail page, a job-recovery fix, and the ops
Cloudflare Worker) are separate batches that build on what you produce here
— do not attempt them, but do build exactly what `PLAN.md` specifies for
them to land on (e.g. `digest_candidates.status` values `promoted`/
`dismissed` exist in the schema even though nothing sets them yet).

## Required context — read these first, in this order

1. `PLAN.md` (repo root) — the full, locked implementation plan for this
   feature. This is authoritative. Read all of it for context, but you are
   only implementing §1 (schema), §2/§3 (webhook), §4 (processor) in this
   batch — not §5 (promotion) or §7 (frontend detail page).
2. `PLAN-REVIEW-LOG.md` (repo root) — 7 rounds of adversarial review that
   produced `PLAN.md`. Read this when a `PLAN.md` decision looks arbitrary or
   underspecified. Relevant rounds for this batch: Round 6 (job created
   before payload row, not after — an FK-ordering fix), Round 5 (atomic
   processor self-claim, `receipt_key` uniqueness, recovery-panel exclusion
   scope — the exclusion itself is a later batch, but the *reason* the
   processor self-claims is explained here), Round 4 (dedup-before-cap
   ordering, sender normalization, `ref` removed from the strip-list),
   Round 2/3 (redirect resolver vs. `fetch_public_html`, `url`/
   `canonical_url` split).
3. `docs/research/2026-09-05-email-digest-claudex-research.md` — primary-source
   research on Cloudflare Email Routing/Workers mechanics and why SPF/DKIM
   can't be trusted from inside a Worker (relevant to the webhook's trust
   boundary — you are not building the Worker itself in this batch, only the
   Python side that receives its POST).
4. `CLAUDE.md` (repo root) — layout, test/lint commands. Run
   `python -m pytest tests -q` via PowerShell only, never through the `rtk`
   Bash hook.
5. `docs/adr/0048-bookmark-import.md` — precedent for reusing
   `content_type='link'` for a sibling worker task with a synthetic,
   non-navigable `jobs.url` (`bookmarks:<hash>` there, `email_digest:<hash>`
   here), and for the Feed-exclusion pattern this feature extends.
6. GitHub issues #600, #601, #602
   (`gh issue view <n> --repo Leon-87-7/ownix`) — each carries its own
   acceptance criteria; treat those as the per-slice definition of done.

## Key decisions already made (do not relitigate)

- **Schema**: `newsletter_subscriptions`, `digest_candidates`,
  `email_digest_payloads` — exact columns and constraints per `PLAN.md` §1.
  No new `jobs.content_type` value; `email_digest` is a new **task**
  discriminator sharing `content_type='link'`, mirroring ADR-0048's
  `bookmarks` task exactly. Build the full `digest_candidates` schema now
  (including `status` enum `pending`/`promoting`/`promoted`/`dismissed` and
  `job_id` nullable) even though the promotion batch (#603) is what actually
  transitions those states — this batch only ever inserts rows as `pending`.
- **Transaction ordering for the receipt job is fixed and non-obvious**: the
  `jobs` row is created **first**, then the `email_digest_payloads` row
  (which has a non-null FK to `jobs.id`) is inserted in the **same
  transaction**. A `UNIQUE(subscription_id, receipt_key)` conflict on that
  insert rolls back the whole transaction (job included); catch the
  conflict and look up/reuse the existing `job_id` by `receipt_key` instead
  of creating a duplicate. Do not insert the payload before the job.
- **Step ordering inside the webhook**: dedup check (via the receipt-job
  URL / `receipt_key`) runs **before** the daily-cap check. Only a genuinely
  new message counts against the cap.
- **The processor's first action is an atomic self-claim**:
  `UPDATE jobs SET status='processing' WHERE id=? AND status IN
  ('pending','error')`, no-op if it matched nothing. This is what makes
  running the same task envelope twice (webhook re-push, Cloudflare retry,
  a future manual retry) safe.
- **Sender-address check is a noise filter, not authentication.** The
  alias's own entropy is the real boundary — say so in a comment if you
  touch that logic.
- **`canonical_url` strips only `utm_*`/`fbclid`/`gclid`/`mc_[ce]id`/`_ga`.
  `ref` is deliberately excluded** — do not add it back. `url` (the real
  resolved destination) is never stripped; only `canonical_url` is, and
  only for the `UNIQUE(space_id, canonical_url)` dedup key.
- **Payload content (`subject`/`html`/`text`) is cleared only on a
  successful processor run**, never unconditionally in a `finally` — a
  failed run needs its payload intact for a later manual-retry feature
  (#605, not this batch, but don't foreclose it by clearing unconditionally).
- **Subscription deletion**: the `DELETE` route explicitly deletes the
  Space row itself (FK cascade only runs Space→subscription, not the
  reverse) and force-clears any remaining
  `email_digest_payloads.subject/html/text` for that subscription. Receipt
  jobs themselves are left behind, inert.
- **`email_digest:<hash>` receipt jobs are excluded entirely from the Feed**
  — not shown-with-special-casing like the Bookmark import card. Locate and
  patch *every* shared job-scope query that backs list, count, and
  prev/next navigation, not just one.

## Work order

Implement in issue order — each slice builds on the last. Verify
`python -m pytest tests -q` stays green after each slice.

### #600 — subscription schema + management API + index page

- New migration in `src/database.py` (append to `_MIGRATIONS`, following the
  existing plain-SQL-list or async-callable pattern used throughout the
  file). `newsletter_subscriptions` per `PLAN.md` §1: `id`, `chat_id`,
  `name`, `sender_email` (lowercase), `alias_local_part` (~22 base64url
  chars via `secrets`, globally unique), `space_id` FK → `spaces.id`
  `ON DELETE CASCADE`, `created_at`. Also add `digest_candidates` and
  `email_digest_payloads` in this same migration pass (or a second one
  immediately after) since #601/#602 below need them — one coherent
  migration for this batch's whole schema is fine.
- `POST /api/newsletter-digest`: generate `alias_local_part`, create the
  subscription and its Space (`icon='newspaper'`) in the same transaction —
  mirror `create_space()` (`src/database.py:2901-2909`) for the Space insert
  shape. Return the full alias (`u_<token>@leondev.xyz`).
- `GET /api/newsletter-digest`: list the caller's own subscriptions with
  candidate counts (via a `digest_candidates` count subquery — will return 0
  until #602 actually inserts rows, that's fine).
- `DELETE /api/newsletter-digest/{id}`: delete the Space explicitly, which
  cascades into `space_urls`/`context_blobs`/the subscription row via
  existing FK behavior; also null any remaining
  `email_digest_payloads.subject/html/text` for that `subscription_id`
  (relevant once #601 exists — write it now, it's a no-op until then).
  Cross-tenant delete → 404/403.
- **Ownership gating**: every route loads `newsletter_subscriptions` scoped
  by `(id, chat_id)` first, mirroring `_get_owned_space()`
  (`src/api/spaces.py:76-83`) exactly.
- Frontend: new `web/app/(dashboard)/newsletter-digest/page.tsx` — list +
  "add newsletter" form (name + sender email → alias) + copy-alias button +
  delete. Mirror `web/lib/hooks/useSpaceList.ts`'s shape for a new
  `useNewsletterDigestList.ts` hook; components under
  `web/components/newsletter-digest/` (kebab-case, colocated `.test.tsx`, no
  barrel files, per `web/CLAUDE.md`). Use `apiPost`/`apiDelete` from
  `web/lib/fetch-utils.ts`. Do **not** build the detail page
  (`/newsletter-digest/[id]`) — that's a later batch; a plain (even
  non-clickable) list row is fine here.
- Tests: ownership scoping (cross-tenant 404/403), the create-transaction
  (subscription + Space both land or neither does), delete cascade.

### #601 — inbound webhook + receipt job creation

- `email_digest_payloads` per `PLAN.md` §1 — `job_id` PK/FK → `jobs.id`
  `ON DELETE CASCADE`, `receipt_key`, `UNIQUE(subscription_id, receipt_key)`,
  `subscription_id` FK → `newsletter_subscriptions.id` nullable + `ON DELETE
  SET NULL`, `subject`/`html`/`text`, plus
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
  other routers (`src/main.py:175-186`). `POST /webhook/email-digest`
  implementing all 8 steps in `PLAN.md` §3 / the issue body verbatim —
  secret check via `secrets.compare_digest`, `envelopeTo`-based alias
  lookup, case-insensitive sender check, byte-size cap, dedup-before-cap
  ordering, the job-then-payload transaction with rollback-and-reuse on
  conflict, re-push on a `pending` dedup hit.
- Feed exclusion: find every query underlying job list/count/adjacent-nav
  in `src/api/jobs.py` (and wherever else jobs are listed for the Feed) and
  add a `url NOT LIKE 'email_digest:%'` predicate consistently.
- Tests: missing/wrong secret, unknown alias, sender mismatch, byte cap,
  cap-vs-dedup ordering, concurrent duplicate delivery (simulate two
  near-simultaneous requests, assert one job), re-push of a still-`pending`
  duplicate, `email_digest:` jobs absent from Feed list/count/nav, payload
  clearing on subscription delete.

### #602 — processor: link extraction + candidates + context blob

- `digest_candidates` per `PLAN.md` §1 — `id`, `space_id` FK → `spaces.id`
  `ON DELETE CASCADE`, `url`, `canonical_url`, `title`/`thumbnail_url`
  nullable, `status` enum, `job_id` nullable, `created_at`,
  `UNIQUE(space_id, canonical_url)`.
- New `src/processors/email_digest.py`; register `"email_digest"` in
  `worker.py`'s `_TASK_HANDLERS` dict (`src/worker.py:310-323`), same shape
  as the existing `"bookmarks"` entry.
- Step 0: atomic self-claim (see Key Decisions).
- Link extraction: new `HTMLParser` subclass mirroring `_BookmarkParser` in
  `src/utils/bookmarks_html.py` (read the whole ~76-line file — this
  extraction is simpler: only `<a href>`, no folder-nesting state).
- Redirect resolution: add a new function to `src/utils/public_html.py`
  built on the existing `_fetch_pinned()` helper (`src/utils/public_html.py:
  72-117`, same SSRF-pinning/3-hop-cap machinery already used by
  `fetch_public_html()`/`fetch_public_image()`), but returning the terminal
  URL (`str(response.url)`) on any non-redirect response regardless of
  content type. `fetch_public_html()` itself (line 133-141) rejects any
  terminal response whose content-type isn't `text/html`/
  `application/xhtml+xml` — correct for the "view online" fallback fetch
  (step 5, which needs the HTML body) but wrong for tracking-link
  resolution, where a direct PDF/document destination must survive.
- OG metadata: use `extract_essential_og()` from `src/utils/og_image.py`
  (`src/utils/og_image.py:45-49`) directly — one fetch, one parse pass
  returns both `og:title` and `og:image`. Do **not** call
  `fetch_og_image_url()` (line 61-65) — it only extracts the image.
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

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch files outside what each slice above names; don't refactor
  unrelated code in a file you open for one fix.
- Do not build #603 (promotion), #604 (detail page), #605 (recovery fix), or
  #606 (ops Worker) — those are separate batches. It's fine (expected) that
  `digest_candidates` rows just sit at `status='pending'` forever after this
  batch; nothing promotes them yet.
- No new Python dependency — stdlib `HTMLParser` for extraction, existing
  `httpx`/`public_html.py` machinery for fetching.
- Test commands: `python -m pytest tests -q` (PowerShell, never the `rtk`
  Bash hook). `ruff check src/` for any new/edited Python file. `npm run
  build && npm run test:run && npm run lint` from `web/` for the #600
  frontend piece.
- Every new API route enforces ownership via `(id, chat_id)` scoping before
  touching a row.

## Deliverable

Uncommitted working-tree changes implementing #600–#602 fully: schema
migration(s), subscription CRUD API + index page, the inbound webhook, and
the `email_digest` worker processor. Regression tests per issue's acceptance
criteria. A short summary per issue noting what was done and anything that
needed a judgment call not already settled in `PLAN.md`/`PLAN-REVIEW-LOG.md`.
