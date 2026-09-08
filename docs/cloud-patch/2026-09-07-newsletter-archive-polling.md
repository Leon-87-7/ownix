# Codex prompt — newsletter digest reads public archives (ADR-0060)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

There are no GitHub issues for this batch. The unit of work is `PLAN.md`
sections 1–9; each slice below names the section it implements.

## Required context — read these first, in this order

1. `PLAN.md` (repo root) — the frozen, already-reviewed spec. It went through
   seven rounds of adversarial cross-model review; **every clause is
   load-bearing and authoritative wherever it differs from older wording
   elsewhere**. Implement it exactly. If a step is impossible as written,
   implement the closest faithful version and report the deviation — do not
   redesign.
2. `docs/adr/0060-newsletter-digest-reads-public-archives.md` — the accepted
   decision: why the inbound-email transport is abandoned, what replaces it,
   and the recovery point (`e0df28f`) if this has to be unwound.
3. `PLAN-REVIEW-LOG.md` — the seven review rounds. Read this **before
   "simplifying" any clause that looks redundant**: most odd-looking
   requirements exist because a reviewer proved the simpler version broken.
   It is the fastest way to see which mistakes have already been made.
4. `CONTEXT.md` (repo root) — domain glossary. **Watched newsletter**,
   **Issue**, **Issue watermark** are the terms this feature must use in code
   and comments.
5. `CLAUDE.md` (repo root) — architecture, worker dispatch, migration
   conventions, test/lint commands.
6. `web/CLAUDE.md` — component layout rules for the slice 7 UI work.
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
   superseded predecessor. Read only for *why* the email approach failed; it
   is **not** a spec any more.

## Key decisions already made (do not relitigate)

- **`publications` and `publication_issues` are shared across tenants and
  carry no `chat_id`.** This is the whole scale claim: a public archive is
  byte-identical for every viewer, so one fetch serves every watcher. The
  user-facing display name lives on `newsletter_watches.name`; the scraped one
  is `publications.fetched_title` and is never shown.
- **The issue body is stored once**, in `publication_issues.body_html`, never
  copied per watcher. It is cleared **only** when the two-half predicate in
  §1 proves no live delivery still needs it. Half 2 alone passes vacuously
  when payload rows don't exist yet — checking only it is a race, and
  clearing at fan-out or enqueue time makes every errored digest permanently
  unretryable.
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
  **never** fall back to `_create_context_blob()`, or one Gemini failure
  during polling silently becomes one Gemini call per watcher.
- **All payload rows for an issue are created before any of their jobs is
  enqueued.** Enqueuing as you go lets a fast job finish, run the cleanup
  predicate and clear `body_html` while later watchers still have no payload
  row.
- **The `email_digest` task discriminator and the `email_digest:` job-URL
  sentinel are deliberately kept**, despite email being gone. They are
  load-bearing in 8 production sites (verified below). Add a comment
  recording why the name lies; do not rename.
- **No durable outbox.** Reuse the existing commit → enqueue → mark-error
  posture. The crash gap is closed by slice 4's missing-delivery scan.
- **Bulk dismiss is pending-only**, exposed as a flag on the existing
  endpoint — not a new batch endpoint (all-or-nothing semantics are wrong
  here) and not multi-select checkboxes (out of scope).

## Verified codebase grounding (re-checked 2026-09-07, all current)

| Reference | Current state |
|---|---|
| `src/api/email_webhook.py:83` | `if sender != subscription["sender_email"].lower():` — the drop that made onboarding impossible |
| `src/api/email_webhook.py:118-125` | the 2 MB payload cap the new streaming helper must mirror |
| `src/api/email_webhook.py:143-147` | commit → enqueue → mark-`error` posture to reuse |
| `src/database.py:302` | `CREATE TABLE ... newsletter_subscriptions` inside `SCHEMA_SQL` |
| `src/database.py:3133,3154,3460` | `j.url LIKE 'email_digest:%'` sentinel sites |
| `src/database.py:3448` | `dismiss_digest_candidate` — `status IN ('pending','promoting')` |
| `src/database.py:3462` | `latest_retryable_email_digest_job` filters on `edp.subject/html/text` — **the columns slice 1 drops, so this must be rewritten, not re-pointed** |
| `src/worker.py:333` | `_ROWLESS_TASKS = {"job_purge", "bookmarks_enrich"}` |
| `src/worker.py:352` | `reap_stale_jobs()` — needs the slice 6 fix |
| `src/job_queue.py:57-59` | `enqueue()` rejects any envelope without `job_id` |
| `src/main.py:15,178` | `email_webhook_router` import + `include_router` |
| `src/auth/middleware.py:17` | `/webhook/email-digest` in `_OPEN_PATHS` |
| `src/config.py:23` | `EMAIL_WEBHOOK_SECRET` |
| `src/api/jobs.py:82,100,338` | `url NOT LIKE 'email_digest:%'` feed filters |
| `src/services/job_recovery.py:27,229` | sentinel-aware recovery filters |
| `src/processors/email_digest.py:314` | `_extract_resolved_links(html, ...)` — HTML-primary, which is why `X-Return-Format: html` matters |
| `src/services/jina.py:78,85,97` | `fetch_markdown` sends `Accept: text/plain` and reads `response.text` wholesale — **confirms the streaming problem is real**: a cap layered on this shape takes the full memory hit before it can reject |
| `ops/email-worker/` | 7 entries, 2232 lines incl. `node_modules/` — delete the directory |

## Work order

Implement in slice order — each builds on the previous. Every slice must
leave the suite green (`python -m pytest tests -q --timeout=120`).

### Slice 1 — schema + teardown migration (§1)

Apply the new tables in **both** `SCHEMA_SQL` and `_MIGRATIONS`: this repo
creates fresh databases from `SCHEMA_SQL` independently of migrations, so a
migration alone leaves new installs on the old schema. Every `_MIGRATIONS`
entry carries the `# rollback:` comment ADR-0058 requires.

Tables: `publications`, `publication_issues`, `newsletter_watches`, and the
reshaped `email_digest_payloads` (drop `subject`/`html`/`text`, add
`watch_id`, `publication_id`, `slug`, `context_md`; unique on
`(watch_id, slug)`; composite FK `(publication_id, slug) → publication_issues`
`ON DELETE RESTRICT`; indexed on `watch_id` **and** `(publication_id, slug)`).

**Teardown order is load-bearing**: delete legacy `email_digest:%` receipt
jobs and their payload rows → delete each `newsletter_subscriptions` row's
backing `spaces` row (cascading `space_urls`, `context_blobs`,
`digest_candidates`, the subscription) → `DROP TABLE
newsletter_subscriptions`. Dropping first orphans every space and candidate,
because the cascade runs spaces→subscription, not the reverse.

Tests: migration teardown leaves no orphaned spaces/candidates/legacy jobs;
fresh-`SCHEMA_SQL` and fully-migrated databases produce identical
`sqlite_master` output; composite FK rejects a payload whose issue row is
gone.

### Slice 2 — shared streaming Jina fetch helper (§4 step 2)

One byte-counted streaming helper that aborts at 4 MB + 1 and never
materialises the body, used by **every** Jina fetch in this feature — archive,
feed and issue alike. Streaming is the requirement, not the cap:
`fetch_markdown`'s current read-everything shape would take the memory hit
before any size check could reject it. Add `X-Return-Format: html` support
without breaking `fetch_markdown`'s existing Markdown callers.

Tests: fetch aborts at 4 MB + 1 without materialising the body; existing
`fetch_markdown` callers keep working.

### Slice 3 — archive resolver (§2)

`src/services/newsletter_archive.py`, new. Pure resolution, no writes:
returns `(archive_url, feed_url | None, issue_path_prefix, fetched_title,
recent_issues)`. URL input → strip query + trailing issue path. Email input →
probe `[f"{local}.{root}", root, domain]`. Prefer a feed (inline
`<link rel="alternate">`, then `/feed.xml`, `/atom.xml`, `/feed`, `/rss`),
else scrape the archive and learn `issue_path_prefix` by grouping same-origin
links. Accept either only on ≥2 distinct issue links — that is what correctly
rejects beehiiv's `/feed`, which returns its HTML app shell with a 200 (Jina
renders 404s as 200, so status proves nothing). Canonicalize via
`<link rel="canonical">` / `og:url` from one issue page.

**Abuse controls**: a pure public-URL validator (scheme in `http`/`https`,
hostname resolves to a public address) applied to the *target* URL **before**
the `r.jina.ai/<url>` string is built. This is deliberately separate from
`public_html._fetch_pinned`, which pins direct httpx connections and does not
protect a fetch made through a third-party proxy. Plus max 4 probe fetches per
request and a per-`chat_id` rate limit. Cache by **normalized** query with a
short TTL; **re-validate every cache hit** against the public-URL check.

Tests: resolver abuse limits (scheme, private host, probe cap, rate limit);
cache re-validation; feed-vs-scrape selection including beehiiv's "200 but an
HTML app shell" `/feed`; `issue_path_prefix` discovery against captured `/p/`
and `/news/` fixtures.

### Slice 4 — poll scheduler + poll worker (§3, §4)

Scheduler: a 15-minute `AsyncIOScheduler` job in `src/main.py` beside
`_drain_purge_outbox` / `_reap_intake_state`, selecting publications that are
due, unleased **and watched**. `IS NULL` on both time clauses matters — a new
publication has neither, and `<` alone would never claim it. Spreading is by
per-tick cap plus `ORDER BY`, not delayed delivery: the queue is a plain Redis
list with no scheduled-task support.

Worker: `src/processors/newsletter_poll.py`, envelope
`{"task": "newsletter_poll", "job_id": <publication_id>}`. `newsletter_poll`
joins `_ROWLESS_TASKS`, **and** `_TASK_HANDLERS` gains a dedicated
`_handle_newsletter_poll(task)` that reads `task["job_id"]` as a publication
id and does not go through `_make_handler()`'s job-load path. Carrying the
id in `job_id` satisfies `job_queue.enqueue()`'s hard check without touching
the shared envelope contract — mirror how `job_purge` and `bookmarks_enrich`
already do this.

Lease → fetch → `INSERT OR IGNORE` issues (the **seen-set, not the work
list**) → compute outstanding work as **missing deliveries** (all issues ×
live watches, minus existing payload rows), **not** as newly-inserted issues:
"rows that just inserted" loses an issue permanently whenever a run crashes
after insert but before fan-out. **No recency window** — a bounded scan
silently gives up on any outage longer than the window. The same scan
re-enqueues payloads whose job has been `pending` past a threshold, which is
what makes an outbox unnecessary.

Per issue, oldest first: fetch once, generate Gemini context once
**best-effort** (failure ⇒ `context_md = NULL`, fan-out continues), then per
watcher create the `jobs` row **and** its payload row in one transaction — a
`UNIQUE(watch_id, slug)` violation rolls back both, so no orphan job survives.
Oversized issues get `skip_reason = 'oversize'` and are terminal: fan-out
continues with the rest.

Success: clear lease, set `last_successful_poll_at`, `next_poll_after = now +
4h`, reset `poll_failures`. Failure: clear lease, increment `poll_failures`,
`next_poll_after = now + min(4h × 2^poll_failures, 24h)`.

Tests: queue-envelope contract and `_handle_newsletter_poll` dispatch;
first-poll claim on `NULL` columns; idempotency across a replayed envelope;
multi-watcher fan-out (N jobs, 1 fetch, 1 Gemini call); lease contention
between two workers; lease refusing a not-yet-due publication; failure backoff
advancing `next_poll_after`; **crash-recovery: issue rows inserted but fan-out
never ran → next poll still delivers**; **job committed but never enqueued →
next poll re-enqueues**; delivery repair after an outage longer than any
recency window; issue ordering with missing/malformed `published_at`,
including the newest-first reversal; oversized issue terminal-skipped without
aborting the run; duplicate fan-out rolling back job **and** payload.

### Slice 5 — digest processor reuse + first watch (§5, §6)

`src/processors/email_digest.py` keeps `extract_digest_links`,
`canonicalize_candidate_url`, `_resolve_links`, `_insert_candidates`,
`_create_context_blob`, `run`. Two changes only: `run()` reads
`email_digest_payloads.context_md` and **skips `_create_context_blob` when
present** (read from the payload row, since the worker calls processors with
only the job dict); and `latest_retryable_email_digest_job(watch_id)` is
**rewritten** against the new schema — its current `edp.subject/html/text`
filter references dropped columns.

First watch: `POST /api/newsletter-digest` re-resolves server-side, seeds
`publication_issues`, and inserts the watch with `watched_from` already set —
all in one transaction, so no window exists where a watch is poll-visible but
unseeded. The newest issue is then delivered as an **explicit
`(watch_id, slug)` delivery**, not via the `watched_from` filter: both
timestamps are written in the same transaction, so `watched_from <
first_seen_at` can collapse at clock precision and skip the very issue meant
to prove the feature works. That delivery uses the **same skip-aware path** as
the poller — an issue carrying `skip_reason` is passed over for the
next-newest.

Tests: retry reading persisted `context_md` without a second Gemini call;
**Gemini failure still produces candidates with `context_md` NULL** and **no
per-watcher fallback**; first-watch explicit delivery when `watched_from`
equals the issue's `first_seen_at`; watch-creation/poll race; first-watch
delivery skipping a `skip_reason` issue; `body_html` surviving until every
live delivery is terminal and an errored digest still retryable afterwards;
**`body_html` NOT cleared while a live watch still lacks a payload row**,
including the zero-payload-rows case after a crash.

### Slice 6 — delete the email path + reaper fix (§7)

Delete: `ops/email-worker/` (whole directory), `src/api/email_webhook.py`,
`src/main.py:15` import + `:178` `include_router`, `/webhook/email-digest`
from `src/auth/middleware.py:17` `_OPEN_PATHS`, `EMAIL_WEBHOOK_SECRET` from
`src/config.py:23`, and the webhook-path tests in `tests/test_email_digest.py`
and `tests/test_config.py`. Note in your summary that the Cloudflare
catch-all rule and its docs also need removing (human action, outside the
tree).

One **fix**, not a deletion: `reap_stale_jobs()` (`src/worker.py:352`) still
offers a generic `reprocess:{job_id}` button for stale `processing` rows, so a
stalled digest job gets a button that would re-drive it as a plain link job
against a non-fetchable sentinel URL. Suppress generic reprocess notifications
for `email_digest:%` and defer to the digest retry path — mirror what
`job_recovery.py:27,229` already do; do not invent a new pattern.

Tests: `reap_stale_jobs()` suppressing generic reprocess for `email_digest:%`.

### Slice 7 — API + web (§8)

- `POST /api/newsletter-digest/resolve` → `{query}` ⇒ resolver result.
  **Read-only, creates nothing**, rate-limited per chat.
- `POST /api/newsletter-digest` → `{archive_url, name}` ⇒ re-resolves
  server-side (the resolve response is **not** carried in the request and must
  not be trusted from the client), creates or reuses the `publications` row
  via an **atomic upsert-or-select helper** (two users adding the same
  newsletter race on `archive_url UNIQUE`), then creates the watch per slice 5.
  Metadata is reconciled, not frozen: a missing `feed_url` /
  `issue_path_prefix` / `fetched_title` is always filled; an existing one is
  replaced when the resolver returns a validated value **and**
  `last_resolved_at` is older than a cooldown (stamp `last_resolved_at` on
  write). Fill-only-if-missing would preserve a wrong `feed_url` forever; the
  cooldown stops two concurrent adds ping-ponging metadata.
- `PUT` edits the watch's `name` only. Candidate list/promote/dismiss and
  `/retry` unchanged; ownership gate keeps its `(id, chat_id)` shape
  (`_get_owned_subscription` → `_get_owned_watch`).
- Subscribe form: one field → resolve → confirmation card listing recent issue
  titles → confirm.
- **`Dismiss rest (N)`** on the candidate list: loops the existing
  per-candidate `DELETE`, using a **pending-only** variant of
  `dismiss_digest_candidate` (`status = 'pending'`, exposed as a flag on the
  existing endpoint) so a bulk loop over a UI snapshot cannot dismiss a
  candidate that turned `promoting` meanwhile. Single-card dismiss keeps
  today's behaviour. The count goes **in the label** as the guard; no confirm
  modal.

Web components follow `web/CLAUDE.md`: `web/components/<area>/<kebab-name>.tsx`
with a colocated `.test.tsx`, no barrel files.

Tests: concurrent `POST` for the same `archive_url` yielding one publication
row; publication metadata refreshed after the cooldown but not ping-ponged by
two concurrent adds; `Dismiss rest` clearing only `pending` candidates —
explicitly **not** one that turned `promoting` after the UI snapshot — and
surviving a partial failure mid-loop.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- **No new Python or npm dependencies. No XML parser** — feeds are fetched
  through the same Jina HTML path as archives.
- **Do not rename** the `email_digest` task discriminator or the
  `email_digest:` job-URL sentinel.
- Scope fence: do not touch anything outside the paths named above, and do not
  refactor unrelated code in a file you opened for one change. In particular,
  `digest_candidates` is otherwise untouched — its `UNIQUE(space_id,
  canonical_url)` dedup and `pending/promoting/promoted/dismissed` claim lock
  stand as-is.
- Follow existing repo idioms: `_MIGRATIONS` entries with `# rollback:`
  comments, aiosqlite access patterns, structlog logging, ruff line-length
  100 / py311, kebab-case web components with colocated tests.
- Tests must not hit real external APIs unless gated behind
  `RUN_INTEGRATION`.
- Proof: `python -m pytest tests -q --timeout=120` — **the suite hangs
  without `--timeout`**; with it, it takes ~4–5 minutes. Known-good baseline
  before your changes is **1409 passed, 0 failed**; treat any failure as a
  real regression, not known noise. Lint: `ruff check src/` (that is the
  documented lint scope and passes clean; `tests/` carries pre-existing ruff
  findings that are out of scope — do not "fix" them).
- Frontend, from `web/`: `npm run test:run`, `npm run lint`, `npm run build`.

## Out of scope (do not build)

- Gmail OAuth ingestion for email-only newsletters.
- Back-catalogue import; adaptive per-newsletter poll cadence.
- Per-card multi-select checkboxes; batch promotion; a batch dismiss endpoint.
- A `publication_aliases` table; a durable enqueue outbox.
- Deleting orphaned `publications` rows when their last watch goes.
- Fixing the pre-existing `bookmarks` mis-retry exposure.

## Deliverable

Uncommitted working-tree changes implementing slices 1–7, with the tests each
slice names, plus a short summary of what was done per slice and anything that
blocked you. **Report every deviation from `PLAN.md` explicitly, with the
reason** — a silent deviation is the one thing that makes review fail.
