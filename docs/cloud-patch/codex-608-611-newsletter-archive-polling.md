# Codex prompt — implement issues #608-611 (newsletter archive polling)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

**Scope note:** a previous run on this batch delivered only #612 and #613 and
stopped. Those two are **out of scope here** — do not delete
`src/api/email_webhook.py`, `ops/email-worker/`, `EMAIL_WEBHOOK_SECRET`, or
`/webhook/email-digest`, and do not touch `dismiss_digest_candidate` or the
candidate-list UI. This run is **#608, #609, #610, #611 only**, and all four are
required. They are the four largest slices and they chain: #608 → #609 → #610 →
#611. If you run short on budget, finish fewer slices **completely** and say so
explicitly in your summary — a half-built slice is worse than an unstarted one.

## Required context — read these first, in this order

1. `PLAN.md` (repo root) — the frozen, already-reviewed spec. It went through
   seven rounds of adversarial cross-model review; **every clause is
   load-bearing and authoritative wherever it differs from older wording
   elsewhere**. Implement it exactly. If a step is impossible as written,
   implement the closest faithful version and report the deviation — do not
   redesign. Each issue below names the `PLAN.md` section it implements.
   §7 (delete the email path) and the `Dismiss rest` bullet in §8 are **out of
   scope for this run**.
2. `docs/adr/0060-newsletter-digest-reads-public-archives.md` — the accepted
   decision: why the inbound-email transport is abandoned and what replaces it.
3. `PLAN-REVIEW-LOG.md` (repo root) — the seven review rounds. Read this
   **before "simplifying" any clause that looks redundant**: most odd-looking
   requirements exist because a reviewer proved the simpler version broken.
4. `CONTEXT.md` (repo root) — domain glossary. **Watched newsletter**,
   **Issue**, **Issue watermark** (lines 154-156) are the terms this feature
   must use in code and comments.
5. `CLAUDE.md` (repo root) — architecture, worker dispatch, migration
   conventions, test/lint commands.
6. `web/CLAUDE.md` — component layout rules for the subscribe-form work in
   #608/#609.
7. Two ADRs `PLAN.md` cites as binding — exact filenames, because ADR numbers
   are not unique in this repo:
   - `docs/adr/0058-sqlite-migration-rollback-discipline.md` — every migration
     needs its `# rollback:` comment.
   - `docs/adr/0043-per-tenant-second-brain.md` — the shared-row rule.
     **Note:** `docs/adr/0043-expanding-rail-wordmark-morph-and-brand-sweep.md`
     also exists and is a different, unrelated ADR — not this one.
8. `docs/plans/2026-09-05-email-digest-inbound-alias-superseded.md` — the
   superseded predecessor. Read only for *why* the email approach failed; it is
   **not** a spec any more.
9. The issues themselves, last — their acceptance criteria are the per-slice
   definition of done:
   `gh issue view 608 --repo Leon-87-7/ownix` (and 609, 610, 611).

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
  sentinel are deliberately kept**, despite email being on its way out. They
  are load-bearing in 8 production sites (verified below). Do not rename them.
- **No durable outbox.** Reuse the existing commit → enqueue → mark-error
  posture. The crash gap is closed by #610's missing-delivery scan.

## Verified codebase grounding (re-checked 2026-09-07 against current `main`)

| Reference | Current state |
|---|---|
| `src/services/jina.py:78,85,91,97` | `fetch_markdown` sends `Accept: text/plain`, does a plain `client.get`, and reads `response.text` wholesale — **confirms the streaming problem is real**: a cap layered on this shape takes the full memory hit before it can reject |
| `src/utils/public_html.py:72` | `_fetch_pinned` — pins **direct** httpx connections. Note the path is `src/utils/`, not `src/services/`. It does **not** protect a fetch made through the `r.jina.ai` proxy, which is why #608 needs its own pure validator |
| `src/database.py:302-312` | `CREATE TABLE newsletter_subscriptions` + index inside `SCHEMA_SQL` |
| `src/database.py:332-342` | `email_digest_payloads` inside `SCHEMA_SQL` (`subject`/`html`/`text`, `subscription_id`) |
| `src/database.py:1488-1524` | the same two tables in the **last** `_MIGRATIONS.append` entry — the shape your new entry must follow, `# rollback:` comment included |
| `src/database.py:1716` | `await conn.executescript(SCHEMA_SQL)` — the fresh-install path that runs **independently of** `_MIGRATIONS`. This is why both places must be updated |
| `src/database.py:3133,3154,3460` | `j.url LIKE 'email_digest:%'` sentinel sites |
| `src/database.py:3454-3460` | `latest_retryable_email_digest_job(subscription_id)` — it filters on `edp.subject`/`html`/`text`, the exact columns #609 drops, so it must be **rewritten**, not re-pointed |
| `src/worker.py:333` | `_ROWLESS_TASKS = {"job_purge", "bookmarks_enrich"}` |
| `src/worker.py:317-332` | `_TASK_HANDLERS` dict — where `_handle_newsletter_poll` is registered |
| `src/job_queue.py:56-59` | `enqueue()` raises `ValueError` on any envelope missing `task` or `job_id` |
| `src/main.py:94,110,140-149` | `_reap_intake_state` / `_drain_purge_outbox` and the `AsyncIOScheduler` block the 15-minute poll tick joins |
| `src/api/email_webhook.py:118-125` | the 2 MB payload cap the new streaming helper must mirror (read it; **do not delete this file**) |
| `src/api/email_webhook.py:142-147` | commit → enqueue → mark-`error` posture to reuse |
| `src/api/newsletter_digest.py:50` | `_get_owned_subscription(subscription_id, chat_id)` → becomes `_get_owned_watch` |
| `src/processors/email_digest.py:267,287,318` | `_create_context_blob`, `run(job)`, and `run`'s unconditional call to it |

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
`latest_retryable_email_digest_job` (`database.py:3454`) is **rewritten**
against the new schema — its current filter references the exact columns this
slice drops. `_get_owned_subscription` (`api/newsletter_digest.py:50`) →
`_get_owned_watch`, same `(id, chat_id)` ownership shape. `PUT` edits the
watch's `name` only. Subscribe form's confirm step creates the watch.

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

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **#612 and #613 are out of scope.** Leave `src/api/email_webhook.py`,
  `ops/email-worker/`, `EMAIL_WEBHOOK_SECRET`, `/webhook/email-digest`,
  `reap_stale_jobs()`, `dismiss_digest_candidate` and the candidate-list UI
  exactly as they are. The email webhook stays wired and importable through
  this run — its 2 MB cap and enqueue-failure posture are reference material
  here, not deletion targets.
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

- **#612 and #613** — see the scope note at the top.
- Gmail OAuth ingestion for email-only newsletters.
- Back-catalogue import; adaptive per-newsletter poll cadence.
- Per-card multi-select checkboxes; batch promotion; a batch dismiss endpoint.
- A `publication_aliases` table; a durable enqueue outbox.
- Deleting orphaned `publications` rows when their last watch goes.
- Fixing the pre-existing `bookmarks` mis-retry exposure.

## Deliverable

Uncommitted working-tree changes implementing **#608, #609, #610 and #611**,
with the regression tests each issue's acceptance criteria names, plus a short
summary of what was done per issue and anything that blocked you. State
explicitly which of the four issues you completed and which you did not start —
do not leave a slice half-built. **Report every deviation from `PLAN.md`
explicitly, with the reason** — a silent deviation is the one thing that makes
review fail.
