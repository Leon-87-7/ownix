# Codex prompt — implement issues #608-613 (newsletter archive polling)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

## Required context — read these first, in this order

1. `PLAN.md` (repo root) — the frozen, already-reviewed spec for this whole
   batch. It went through seven rounds of adversarial cross-model review;
   **every clause is load-bearing and authoritative wherever it differs from
   older wording elsewhere**. Implement it exactly. If a step is impossible as
   written, implement the closest faithful version and report the deviation —
   do not redesign. Each issue below names the `PLAN.md` section it implements.
2. `docs/adr/0060-newsletter-digest-reads-public-archives.md` — the accepted
   decision: why the inbound-email transport is abandoned, what replaces it,
   and the recovery point (`e0df28f`) if this has to be unwound.
3. `PLAN-REVIEW-LOG.md` (repo root) — the seven review rounds. Read this
   **before "simplifying" any clause that looks redundant**: most odd-looking
   requirements exist because a reviewer proved the simpler version broken.
4. `CONTEXT.md` (repo root) — domain glossary. **Watched newsletter**,
   **Issue**, **Issue watermark** (lines 154-156) are the terms this feature
   must use in code and comments.
5. `CLAUDE.md` (repo root) — architecture, worker dispatch, migration
   conventions, test/lint commands.
6. `web/CLAUDE.md` — component layout rules for the UI work in #608/#609/#613.
7. Three ADRs `PLAN.md` cites as binding — exact filenames, because ADR
   numbers are not unique in this repo:
   - `docs/adr/0058-sqlite-migration-rollback-discipline.md` — every migration
     needs its `# rollback:` comment.
   - `docs/adr/0043-per-tenant-second-brain.md` — the shared-row rule.
     **Note:** `docs/adr/0043-expanding-rail-wordmark-morph-and-brand-sweep.md`
     also exists and is a different, unrelated ADR — not this one.
   - `docs/adr/0051-automatic-bookmark-capture-rejected.md` — the
     no-auto-processing line that rules out a "promote all" button.
8. `docs/plans/2026-09-05-email-digest-inbound-alias-superseded.md` — the
   superseded predecessor. Read only for *why* the email approach failed; it is
   **not** a spec any more.
9. The issues themselves, last — their acceptance criteria are the per-slice
   definition of done:
   `gh issue view 608 --repo Leon-87-7/ownix` (and 609, 610, 611, 612, 613).

## Nature of this batch

#608 → #609 → #610 → #611 is a **dependency chain**: each slice builds on the
previous one's helper, schema and poller. #612 depends on #610. #613 is
**independent** — it works against the candidate list already shipped in
`e0df28f` and can be done at any point. Implement in issue-number order.

Every slice must leave the suite green before you move to the next.

## Key decisions already made (do not relitigate)

- **`publications` and `publication_issues` are shared across tenants and carry
  no `chat_id`.** This is the whole scale claim: a public archive is
  byte-identical for every viewer, so one fetch serves every watcher. The
  user-facing display name lives on `newsletter_watches.name`; the scraped one
  is `publications.fetched_title` and is never shown.
- **The issue body is stored once**, in `publication_issues.body_html`, never
  copied per watcher. It is cleared **only** when the two-half predicate in
  `PLAN.md` §1 proves no live delivery still needs it (see #611). Half 2 alone
  passes vacuously when payload rows don't exist yet — checking only it is a
  race, and clearing at fan-out or enqueue time makes every errored digest
  permanently unretryable.
- **`watched_from` is a TIMESTAMP, not a slug.** Slugs are publisher strings
  with no chronological order. The fan-out filter is
  `publication_issues.first_seen_at > watched_from`.
- **Processing order is
  `ORDER BY published_at ASC NULLS LAST, source_order DESC, first_seen_at ASC`.**
  The `DESC` on `source_order` is not a typo — both feeds and archive pages
  list newest first, so it reverses the source ordering to get oldest-first.
- **Feeds and archives share one fetch path.** Both go through Jina with
  `X-Return-Format: html` — verified: Jina renders `alphasignal.ai/feed.xml`
  into clean HTML carrying 100 `/news/` permalinks. **Do not add an XML
  parser.** Acceptance for both is the same rule: ≥2 distinct issue links.
- **`issue_path_prefix` is learned at resolve time, never hardcoded.** `/p/`
  for beehiiv, `/news/` for AlphaSignal, discovered by grouping same-origin
  links. No provider allowlist.
- **`context_md` is owned entirely by the poll worker.** Generated once per
  issue, persisted on the payload row, cleared on success, retained on error.
  `run()` inserts it when present and inserts nothing when absent — it must
  **never** fall back to `_create_context_blob()`, or one Gemini failure during
  polling silently becomes one Gemini call per watcher.
- **All payload rows for an issue are created before any of their jobs is
  enqueued.** Enqueuing as you go lets a fast job finish, run the cleanup
  predicate and clear `body_html` while later watchers still have no payload
  row.
- **The `email_digest` task discriminator and the `email_digest:` job-URL
  sentinel are deliberately kept**, despite email being gone. They are
  load-bearing in 8 production sites (verified below). Add a comment recording
  why the name lies; do not rename.
- **No durable outbox.** Reuse the existing commit → enqueue → mark-error
  posture. The crash gap is closed by #610's missing-delivery scan.
- **Bulk dismiss is pending-only**, exposed as a flag on the existing endpoint
  — not a new batch endpoint (all-or-nothing semantics are wrong here) and not
  multi-select checkboxes (out of scope).

## Verified codebase grounding (re-checked 2026-09-07 against current `main`)

| Reference | Current state |
|---|---|
| `src/api/email_webhook.py:83` | `if sender != subscription["sender_email"].lower():` — the drop that made onboarding impossible |
| `src/api/email_webhook.py:118-125` | the 2 MB payload cap the new streaming helper must mirror |
| `src/api/email_webhook.py:142-147` | commit → enqueue → mark-`error` posture to reuse |
| `src/services/jina.py:78,85,91,97` | `fetch_markdown` sends `Accept: text/plain`, does a plain `client.get`, and reads `response.text` wholesale — **confirms the streaming problem is real**: a cap layered on this shape takes the full memory hit before it can reject |
| `src/utils/public_html.py:72` | `_fetch_pinned` — pins **direct** httpx connections. Note the path is `src/utils/`, not `src/services/`. It does **not** protect a fetch made through the `r.jina.ai` proxy, which is why #608 needs its own pure validator |
| `src/database.py:302-312` | `CREATE TABLE newsletter_subscriptions` + index inside `SCHEMA_SQL` |
| `src/database.py:332-342` | `email_digest_payloads` inside `SCHEMA_SQL` (`subject`/`html`/`text`, `subscription_id`) |
| `src/database.py:1488-1524` | the same two tables in the **last** `_MIGRATIONS.append` entry — the shape your new entry must follow, `# rollback:` comment included |
| `src/database.py:1716` | `await conn.executescript(SCHEMA_SQL)` — the fresh-install path that runs **independently of** `_MIGRATIONS`. This is why both places must be updated |
| `src/database.py:3133,3154,3460` | `j.url LIKE 'email_digest:%'` sentinel sites |
| `src/database.py:3444,3448` | `dismiss_digest_candidate` — `WHERE id = ? AND space_id = ? AND status IN ('pending', 'promoting')` |
| `src/database.py:3454-3460` | `latest_retryable_email_digest_job(subscription_id)` — **the issue body says `:3462`; it is actually `:3454`**. It filters on `edp.subject`/`html`/`text`, the exact columns #609 drops, so it must be **rewritten**, not re-pointed |
| `src/worker.py:333` | `_ROWLESS_TASKS = {"job_purge", "bookmarks_enrich"}` |
| `src/worker.py:317-332` | `_TASK_HANDLERS` dict — where `_handle_newsletter_poll` is registered |
| `src/worker.py:352,383` | `reap_stale_jobs()` and its generic `reprocess:{job_id}` button — the #612 fix |
| `src/job_queue.py:56-59` | `enqueue()` raises `ValueError` on any envelope missing `task` or `job_id` |
| `src/main.py:15,178` | `email_webhook_router` import + `include_router` |
| `src/main.py:94,110,140-149` | `_reap_intake_state` / `_drain_purge_outbox` and the `AsyncIOScheduler` block the 15-minute poll tick joins |
| `src/auth/middleware.py:17` | `/webhook/email-digest` in `_OPEN_PATHS` |
| `src/config.py:23` | `EMAIL_WEBHOOK_SECRET: str = Field(min_length=1)` |
| `src/api/jobs.py:82,100,338` | `url NOT LIKE 'email_digest:%'` feed filters |
| `src/services/job_recovery.py:27,229` | sentinel-aware recovery filters — the pattern #612 must mirror |
| `src/api/newsletter_digest.py:50` | `_get_owned_subscription(subscription_id, chat_id)` → becomes `_get_owned_watch` |
| `src/api/newsletter_digest.py:161-172` | `DELETE /{subscription_id}/candidates/{candidate_id}` — the endpoint #613 adds its pending-only flag to |
| `src/processors/email_digest.py:267,287,318` | `_create_context_blob`, `run(job)`, and `run`'s unconditional call to it |
| `web/lib/newsletter-digest.ts:82` | `dismissDigestCandidate(...)` — the client call `Dismiss rest` loops |
| `web/components/newsletter-digest/newsletter-digest-detail.tsx:80,188-195` | `handleDismiss` and the candidate list render — where `Dismiss rest (N)` goes |
| `ops/email-worker/` | 7 entries incl. `node_modules/` — delete the whole directory |

## Work order

### #608 — resolve a newsletter's archive from a URL or sender address (§2, §4 step 2)

Two pieces, in this order.

**A shared streaming Jina fetch helper.** One byte-counted streaming helper
that aborts at 4 MB + 1 and never materialises the body, used by **every** Jina
fetch in this feature — archive, feed and issue alike. Streaming is the
requirement, not the cap: `fetch_markdown` (`jina.py:78`) does
`response = await client.get(...)` then `response.text` (`:91,:97`), so a cap
layered on that shape takes the full memory hit *before* it can reject. Use
`httpx`'s streaming API and count bytes as they arrive. Add
`X-Return-Format: html` support **without breaking `fetch_markdown`'s existing
Markdown callers** — existing callers must keep working unchanged.

**`src/services/newsletter_archive.py`** (new). Pure resolution, **no writes**:
returns `(archive_url, feed_url | None, issue_path_prefix, fetched_title,
recent_issues)`. URL input → strip query string, strip a trailing issue path →
root. Email input → probe `[f"{local}.{root}", root, domain]`. Prefer a feed
(inline `<link rel="alternate">`, then `/feed.xml`, `/atom.xml`, `/feed`,
`/rss`), else scrape the archive and learn `issue_path_prefix` by grouping
same-origin links by first path segment and taking the segment with the most
distinct dated children. Accept either **only on ≥2 distinct issue links** —
that is what correctly rejects beehiiv's `/feed`, which returns its HTML app
shell with a 200 (Jina renders 404s as 200, so status proves nothing). Resolve
relative hrefs against the base URL. Canonicalize via `<link rel="canonical">`
/ `og:url` from one issue page, so `slothbytes.beehiiv.com` collapses onto
`www.slothbytes.dev`.

**Abuse controls**: a pure public-URL validator (scheme in `http`/`https`,
hostname resolves to a public address) applied to the *target* URL **before**
the `r.jina.ai/<url>` string is built. Deliberately separate from
`src/utils/public_html.py:72` `_fetch_pinned`, which pins direct httpx
connections and does not protect a fetch through a third-party proxy — mirror
its address-classification approach, don't reuse the pinning transport. Plus
max 4 probe fetches per request and a per-`chat_id` rate limit. Cache by
**normalized** query with a short TTL; **re-validate every cache hit** against
the public-URL check before use.

Then `POST /api/newsletter-digest/resolve` → `{query}` ⇒ the resolver result,
**read-only, creating nothing**, rate-limited per chat; and the subscribe
form's first step: one field → resolve → confirmation card listing recent issue
titles.

Regression clause: existing `fetch_markdown` Markdown callers must keep working
byte-for-byte.

Tests: resolver abuse limits (scheme, private host, probe cap, rate limit);
cache re-validation; feed-vs-scrape selection including beehiiv's "200 but an
HTML app shell" `/feed`; `issue_path_prefix` discovery against captured `/p/`
and `/news/` fixtures; streaming abort at 4 MB + 1 without materialising the
body.

### #609 — watch a newsletter and deliver its latest issue (§1, §5, §6)

**Schema in both places.** New tables in **both** `SCHEMA_SQL` and
`_MIGRATIONS`: this repo creates fresh databases from `SCHEMA_SQL`
(`database.py:1716`) independently of migrations, so a migration alone leaves
new installs on the old schema. Follow the shape of the existing entry at
`database.py:1488-1524`, `# rollback:` comment included (ADR-0058).

`publications`, `publication_issues`, `newsletter_watches`, and the reshaped
`email_digest_payloads` — drop `subject`/`html`/`text`; add `watch_id`,
`publication_id`, `slug`, `context_md`; UNIQUE `(watch_id, slug)`; composite
`FOREIGN KEY (publication_id, slug) REFERENCES publication_issues` `ON DELETE
RESTRICT`; indexed on `watch_id` **and** `(publication_id, slug)`. Exact column
lists are in `PLAN.md` §1 and the issue's acceptance criteria.

**Teardown order is load-bearing**: delete legacy `email_digest:%` receipt jobs
and their payload rows → for each `newsletter_subscriptions` row delete its
backing `spaces` row (cascading `space_urls`, `context_blobs`,
`digest_candidates`, the subscription) → `DROP TABLE newsletter_subscriptions`.
Dropping first orphans every space and candidate, because the cascade runs
spaces→subscription, not the reverse.

**API.** `POST /api/newsletter-digest` → `{archive_url, name}` **re-resolves
`archive_url` server-side** (the resolve response is not carried in the request
and must not be trusted from the client), creates-or-reuses the `publications`
row via an **atomic upsert-or-select** (two users adding the same newsletter
race on `archive_url UNIQUE`), seeds `publication_issues`, and inserts the
watch with `watched_from` set — **all in one transaction**, so no window exists
where a watch is poll-visible but unseeded. Metadata is **reconciled, not
frozen**: a missing `feed_url` / `issue_path_prefix` / `fetched_title` is
always filled; an existing one is replaced when the resolver returns a
validated value **and** `last_resolved_at` is older than a cooldown (stamped on
write). Fill-only-if-missing would preserve a wrong `feed_url` forever; the
cooldown is what stops two concurrent adds ping-ponging metadata.

**First delivery.** The newest issue is delivered as an **explicit
`(watch_id, slug)` delivery**, not as a consequence of the `watched_from`
filter — both timestamps are written in the same transaction, so
`watched_from < first_seen_at` can collapse at clock precision and skip the
very issue meant to prove the feature works. It uses the **same skip-aware
path** as the poller: an issue carrying `skip_reason` is passed over for the
next-newest.

**Processor.** `src/processors/email_digest.py` keeps `extract_digest_links`,
`canonicalize_candidate_url`, `_resolve_links`, `_insert_candidates`,
`_create_context_blob`, `run`. `run()` (`:287`) reads
`email_digest_payloads.context_md` and **skips its `_create_context_blob` call
(`:318`) when present**, inserting the stored text as the Space's
`context_blobs` row. **A null `context_md` never triggers per-job generation.**
`latest_retryable_email_digest_job` (`database.py:3454`, **not** `:3462`) is
**rewritten** against the new schema — its current filter references the exact
columns this slice drops. `_get_owned_subscription`
(`api/newsletter_digest.py:50`) → `_get_owned_watch`, same `(id, chat_id)`
ownership shape. `PUT` edits the watch's `name` only. Subscribe form's confirm
step creates the watch.

Regression clause: candidate list / promote / dismiss / `/retry` behaviour is
unchanged apart from the ownership-helper rename; `digest_candidates` is
otherwise untouched.

Tests: migration teardown leaves no orphaned spaces/candidates/legacy jobs;
fresh-`SCHEMA_SQL` and fully-migrated databases produce identical
`sqlite_master` output; composite FK rejects a payload whose issue row is gone;
first-watch explicit delivery when `watched_from` equals the issue's
`first_seen_at`; first-watch delivery skipping a `skip_reason` issue;
concurrent `POST` for the same `archive_url` yields one publication row;
metadata refreshed after the cooldown but not ping-ponged by two concurrent
adds; retry reads persisted `context_md` without a second Gemini call.

### #610 — poll watched publications every 4 hours and fan out (§3, §4)

**Scheduler**: a 15-minute `AsyncIOScheduler` job in `src/main.py` beside
`_drain_purge_outbox` / `_reap_intake_state` (`main.py:140-149`), selecting
publications that are due, unleased **and watched**. `IS NULL` on **both** time
clauses matters — a new publication has neither, and `<` alone would never
claim it. Spreading is by **per-tick cap plus `ORDER BY`**, not delayed
delivery: the queue is a plain Redis list (`LPUSH`) with no scheduled-task
support, so "enqueue with jitter" is not available.

**Worker**: `src/processors/newsletter_poll.py`, envelope
`{"task": "newsletter_poll", "job_id": <publication_id>}`. `newsletter_poll`
joins `_ROWLESS_TASKS` (`worker.py:333`) **and** `_TASK_HANDLERS`
(`worker.py:317-332`) gains a dedicated `_handle_newsletter_poll(task)` that
reads `task["job_id"]` as a publication id and does **not** go through
`_make_handler()`'s job-load path. Carrying the id in `job_id` satisfies
`job_queue.enqueue()`'s hard check (`job_queue.py:56-59`) without touching the
shared envelope contract — mirror how `job_purge` and `bookmarks_enrich`
already do this, don't invent a new envelope shape.

**Lease**: `UPDATE publications SET poll_lease_until = :now_plus_10m WHERE id =
? AND (poll_lease_until IS NULL OR poll_lease_until < :now) AND
(next_poll_after IS NULL OR next_poll_after < :now)`. No match → another worker
owns it **or it is not due yet** — the second clause is what stops a duplicate
queued envelope from re-polling immediately after a successful run.

Fetch `feed_url` if set, else the archive root, via the shared streaming helper
from #608, resolving relative hrefs against the base URL. `INSERT OR IGNORE`
every discovered issue into `publication_issues` (recording `source_order`) —
this is the **seen-set, not the work list**.

**Compute outstanding work as missing deliveries**: join **all**
`publication_issues` for the publication against live `newsletter_watches`
where `watched_from < first_seen_at`, selecting `(watch_id, slug)` pairs with
no `email_digest_payloads` row. "Rows that just inserted" would lose an issue
permanently whenever a run crashes after insert but before fan-out. **No
recency window** — a bounded "last N days" scan silently gives up on any outage
longer than N. The same scan re-enqueues payloads whose `jobs` row has been
`pending` past a threshold, repairing a crash between commit and enqueue; this
is why no durable outbox is added.

Per issue, oldest first (`ORDER BY published_at ASC NULLS LAST, source_order
DESC, first_seen_at ASC`): fetch the page **once**, generate the Gemini
editorial context **once** and **best-effort** — a Gemini failure sets
`context_md = NULL` and fan-out proceeds, matching `_create_context_blob`'s
existing non-fatal posture. **No per-watcher fallback generation.** Then per
watcher, create the `jobs` row **and** its `email_digest_payloads` row in
**one transaction**; a `UNIQUE(watch_id, slug)` violation rolls the whole
transaction back — disposing of the just-created job row, so no orphan survives
— and that watcher is skipped. **All payload rows for an issue are created
before any of their jobs is enqueued.** Enqueue failure marks the job `error`,
mirroring `email_webhook.py:142-147`, so the existing retry endpoint can
re-drive it.

Success: clear lease, set `last_successful_poll_at`, `next_poll_after = now +
4h`, reset `poll_failures`. Failure: clear lease, increment `poll_failures`,
`next_poll_after = now + min(4h × 2^poll_failures, 24h)` — a failed run must
not be hidden for four hours.

Regression clause: the existing `_dispatch` path for every other task
discriminator must be unaffected; no other task gains or loses its job-load.

Tests: queue-envelope contract and `_handle_newsletter_poll` dispatch;
first-poll claim on `NULL` columns; idempotency across a replayed envelope;
multi-watcher fan-out (N jobs, 1 fetch, 1 Gemini call); lease contention
between two workers; lease refusing a not-yet-due publication; failure backoff
advancing `next_poll_after`; **crash-recovery: issue rows inserted but fan-out
never ran → next poll still delivers**; **job committed but never enqueued →
next poll re-enqueues the stale pending payload**; delivery repair after an
outage longer than any recency window; issue ordering with missing or
malformed `published_at`, including the newest-first reversal; duplicate
fan-out rolling back job **and** payload, leaving no orphan job; **Gemini
failure still produces candidates with `context_md` NULL and no per-watcher
fallback**.

### #611 — reclaim issue bodies and skip oversized issues (§1, §4 step 2)

`body_html` is cleared **only when a DB predicate proves no live delivery still
needs it**, and that predicate has **two halves, both required**:

1. **no live watch is still missing a payload row** for this
   `(publication_id, slug)` — the same missing-delivery definition #610 uses
   for repair; **and**
2. every existing payload row for it, whose watch still exists, is a `done` job
   or an intentionally cancelled/dismissed one.

**Half 2 alone must not be sufficient.** It passes vacuously when payload rows
do not exist yet: a fast first watcher could finish and clear the body before
later watchers' rows are created, and a crash after storing `body_html` but
before any payload creation would look "clean" with zero rows. **Clearing at
fan-out or at enqueue completion is not acceptable** — it strips the body out
from under jobs that are merely *created*, and makes every errored digest
permanently unretryable.

An issue whose fetch exceeds the 4 MB cap is marked `skip_reason = 'oversize'`
and treated as **terminal**: fan-out continues with the remaining issues rather
than aborting the run. A `skip_reason` issue stops being selected as
outstanding work, so it is neither re-fetched every poll nor left blocking that
issue's body-cleanup accounting.

Regression clause: an errored digest job must still be retryable after the
cleanup pass runs.

Tests: `body_html` survives until every live delivery is terminal, and an
errored digest is still retryable afterwards; **`body_html` NOT cleared while a
live watch still lacks a payload row**, including the zero-payload-rows case
after a crash; oversized issue marked terminal-skipped without aborting the
rest of the run.

### #612 — retire the inbound-email transport (§7) (HITL — repo side only)

Delete: `ops/email-worker/` (whole directory), `src/api/email_webhook.py`, the
`email_webhook_router` import (`main.py:15`) and its `include_router`
(`main.py:178`), `/webhook/email-digest` from `_OPEN_PATHS`
(`auth/middleware.py:17`), `EMAIL_WEBHOOK_SECRET` (`config.py:23`), and the
webhook-path tests in `tests/test_email_digest.py` and `tests/test_config.py`.

One **fix**, not a deletion: `reap_stale_jobs()` (`worker.py:352`) offers a
generic `reprocess:{job_id}` button for stale `processing` rows
(`worker.py:383`). Only the dashboard recovery path special-cases
`email_digest:%`, so a stalled digest job gets a button that would re-drive it
as a plain link job against a non-fetchable sentinel URL. Suppress generic
reprocess notifications for `email_digest:%` and defer to the digest retry path
— **mirror `job_recovery.py:27,229`; do not invent a new pattern.**

The `email_digest` task discriminator and the `email_digest:` job-URL sentinel
are **retained** — load-bearing in 8 production sites (`api/jobs.py:82,100,338`,
`services/job_recovery.py:27,229`, `database.py:3133,3154,3460`), excluding
receipt jobs from the Feed and from generic recovery retry. Add a comment
recording why the name lies.

**HITL**: removing the Cloudflare Email Routing catch-all rule needs the user's
own dashboard access. Your part is everything in the repo; call the Cloudflare
change and its docs out explicitly in your summary as a human action, don't
silently leave it behind.

Regression clause: every other `_OPEN_PATHS` entry and every other config field
keeps working; the reaper's behaviour for non-`email_digest:%` jobs is
unchanged.

Tests: `reap_stale_jobs()` suppresses generic reprocess for `email_digest:%`.

### #613 — dismiss remaining candidates in one action (§8) — independent

`Dismiss rest (N)` on the candidate list
(`web/components/newsletter-digest/newsletter-digest-detail.tsx`, list render
at `:188-195`, `handleDismiss` at `:80`) **loops the existing per-candidate
`DELETE`** via `dismissDigestCandidate` (`web/lib/newsletter-digest.ts:82`). A
batch **endpoint** is deliberately not added: it would impose all-or-nothing
semantics that are wrong here (one candidate failing must not roll back the
others) to save round-trips that do not matter at this size.

**One small backend change is required, not zero**: `dismiss_digest_candidate`
(`database.py:3444`) currently accepts `status IN ('pending', 'promoting')`
(`:3448`), so a bulk loop over a UI snapshot could dismiss a candidate that
turned `promoting` in the meantime — flipping it to `dismissed` while its job
is being created. Bulk dismiss uses a **pending-only** variant (`status =
'pending'`), exposed as a **flag on the existing endpoint**
(`api/newsletter_digest.py:161-172`). **Single-card dismiss keeps today's
behaviour** (`pending` or `promoting`).

The **count goes in the label** (`Dismiss rest (12)`) as the guard —
`CONTEXT.md`'s [[Job delete]] entry records a Bookmark import card where one
misclick took hundreds of links. **No confirm modal**: dismissal is a soft
status flip that leaves the row in the dedup set. A partial failure mid-loop
leaves the successfully-dismissed candidates dismissed and surfaces the
failure, rather than rolling back.

Web component follows `web/CLAUDE.md`:
`web/components/<area>/<kebab-name>.tsx` with a colocated `.test.tsx`, no
barrel files.

Regression clause: single-card dismiss must keep accepting a `promoting`
candidate exactly as it does today.

Tests: `Dismiss rest` clears only `pending` candidates — explicitly **not** a
candidate that turned `promoting` after the UI snapshot — and survives a
partial failure mid-loop.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **No new Python or npm dependencies. No XML parser** — feeds are fetched
  through the same Jina HTML path as archives.
- **Do not rename** the `email_digest` task discriminator or the
  `email_digest:` job-URL sentinel.
- Do not merge issues into a shared abstraction beyond what an issue's own
  acceptance criteria calls for — the streaming helper (#608) is shared by
  explicit requirement; nothing else is.
- Scope fence: do not touch anything outside the paths named above, and do not
  refactor unrelated code in a file you opened for one change. In particular,
  `digest_candidates` is otherwise untouched — its `UNIQUE(space_id,
  canonical_url)` dedup and `pending/promoting/promoted/dismissed` claim lock
  stand as-is.
- Follow existing repo idioms: `_MIGRATIONS` entries with `# rollback:`
  comments, aiosqlite access patterns, structlog logging, ruff line-length 100
  / py311, kebab-case web components with colocated tests.
- Tests must not hit real external APIs unless gated behind `RUN_INTEGRATION`.
- Proof: `python -m pytest tests -q --timeout=120` — **the suite hangs without
  `--timeout`**; with it, it takes ~4-5 minutes. Known-good baseline before
  your changes is **1409 passed, 0 failed**; treat any failure as a real
  regression, not known noise. Lint: `ruff check src/` (that is the documented
  lint scope and passes clean; `tests/` carries pre-existing ruff findings that
  are out of scope — do not "fix" them). Never run tests through the `rtk`
  hook.
- Frontend, from `web/`: `npm run test:run`, `npm run lint`, `npm run build`.

## Out of scope (do not build)

- Gmail OAuth ingestion for email-only newsletters.
- Back-catalogue import; adaptive per-newsletter poll cadence.
- Per-card multi-select checkboxes; batch promotion; a batch dismiss endpoint.
- A `publication_aliases` table; a durable enqueue outbox.
- Deleting orphaned `publications` rows when their last watch goes.
- Fixing the pre-existing `bookmarks` mis-retry exposure.

## Deliverable

Uncommitted working-tree changes implementing #608-613, with the regression
tests each issue's acceptance criteria names, plus a short summary of what was
done per issue and anything that blocked you — including the Cloudflare
catch-all removal #612 leaves to a human. **Report every deviation from
`PLAN.md` explicitly, with the reason** — a silent deviation is the one thing
that makes review fail.
