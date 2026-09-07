# Plan Review Log: Newsletter digest reads public archives, not email (ADR-0060)

Started 2026-09-07 (session). MAX_ROUNDS=5. Codex CLI 0.142.5, model `gpt-5.5`, read-only
every round (`-s read-only` on the first call, `-c sandbox_mode="read-only"` on every resume,
because `~/.codex/config.toml` defaults to `workspace-write`).

Plan under review: `PLAN.md`. Superseded predecessor and its own review log live at
`docs/plans/2026-09-05-email-digest-inbound-alias-*.md`.

## Round 1 — Codex

Material flaws:

- `newsletter_poll` cannot enter the queue: the plan enqueues `{"task":"newsletter_poll","publication_id":...}`, but [job_queue.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/job_queue.py:57) rejects envelopes without `job_id`, and [worker.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/worker.py:339) indexes `task["job_id"]`. Fix: make rowless tasks first-class in `job_queue`/worker logging/dispatch, or give poll tasks a real DB-backed job/outbox id.

- The payload uniqueness contradicts fan-out: `email_digest_payloads UNIQUE(publication_id, slug)` allows only one job per issue, but the plan creates one job per watcher. Fix: use `watch_id + slug` uniqueness, or split shared `publication_issues` from per-watch payload/job rows.

- Fresh installs will keep the old schema because the plan only mentions `_MIGRATIONS.append`; this repo also has `SCHEMA_SQL` creating `newsletter_subscriptions`/old payloads in [database.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/database.py:301). Fix: update `SCHEMA_SQL` and add a fresh-DB schema test.

- Dropping `newsletter_subscriptions` leaves backing `spaces` and `digest_candidates` behind, because cascade runs from `spaces` to subscriptions, not the reverse. Fix: delete or migrate each subscription’s backing space/candidates before dropping the table.

- The plan says “API process never fetches,” but `POST /api/newsletter-digest` resolves archives and recent issues, which necessarily calls Jina. Fix: either explicitly allow bounded resolver fetches in API, or split resolution into an async job with status polling.

- User-provided archive URLs become server-paid remote fetches with no validation, rate limit, or cache; the current Jina service blindly fetches a quoted URL in [jina.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/services/jina.py:78). Fix: enforce http/https public-host validation, per-chat rate limits, probe caps, and cached resolver results.

- Current Jina integration returns Markdown only (`Accept: text/plain` in [jina.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/services/jina.py:85)), while `email_digest.run` primarily parses HTML links in [email_digest.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/processors/email_digest.py:314). Fix: decide now: implement Markdown link extraction with tests, or add a real HTML Jina fetch path and prove it works.

- `last_polled_at < ?` does not claim new `NULL` rows, so new publications may never poll. Fix: claim with `(last_polled_at IS NULL OR last_polled_at < ?)` and test first-poll behavior.

- Updating `last_polled_at` at claim time makes “next tick retries” false after fetch failure or worker crash; the row is hidden for four hours. Fix: use a poll lease/status column and separate `last_successful_polled_at`, with failure backoff.

- “Update `latest_slug` once at the end” is not idempotent after partial fan-out: a crash before the update can recreate already-created watcher jobs. Fix: insert per-watch issue rows with `INSERT OR IGNORE` and enqueue only newly claimed rows.

- A single `latest_slug` is a weak watermark: if the slug falls off the visible archive page, is edited, or is reused, the poller can silently miss or replay issues. Fix: store seen issue slugs/URLs in a `publication_issues` table and diff by set with pagination limits.

- Shared `publications.name` is user-visible shared state, despite the plan claiming shared rows contain only fetch bookkeeping. Fix: keep user-facing display name on `newsletter_watches`/`spaces`; treat publication name as fetched metadata only.

- Mirror handling is acknowledged but unresolved, so `archive_url UNIQUE` still double-ingests `custom-domain` and `*.beehiiv.com` archives for the same publication. Fix: add `publication_aliases` and canonicalize from issue canonical URLs/provider IDs before creating a publication.

- Enqueueing digest jobs “in the same transaction” as SQLite inserts is impossible with Redis; current code already has compensating error handling around enqueue. Fix: introduce a durable outbox for digest tasks or explicitly mark committed-but-not-enqueued jobs retryable.

- The replacement API contract is under-specified: `POST` both “returns resolved publication” and seems to create the watch, while the UI wants confirmation before commit. Fix: split `POST /resolve` from `POST /api/newsletter-digest` create-watch, with exact request/response schemas.

- Test scope is materially too thin: deleting webhook tests and “repointing extraction tests” misses migration, queue contract, poll idempotency, multi-watcher fan-out, resolver abuse limits, and fresh install. Fix: add focused tests for each of those before implementation is considered complete.

VERDICT: REVISE
### Claude's response

Accepted and fixed in PLAN.md (round 1 → round 2), nearly all of it:

- **Queue contract.** Verified: `job_queue.enqueue()` (`src/job_queue.py:57`) hard-raises
  without `job_id`. But Codex missed that `_ROWLESS_TASKS` already exists
  (`src/worker.py:333` — `job_purge`, `bookmarks_enrich`), and the established convention is
  that a rowless task still carries the id it operates on in the `job_id` field. So the fix
  is two lines following precedent — add `newsletter_poll` to `_ROWLESS_TASKS`, envelope
  carries `job_id: publication_id` — not a change to the shared envelope contract.
- **`SCHEMA_SQL` vs migrations.** Correct and important: `src/database.py:301` creates
  `newsletter_subscriptions` for fresh installs independently of `_MIGRATIONS`. Both paths
  now specified, plus a fresh-DB schema-parity test.
- **`UNIQUE(publication_id, slug)` contradicts per-watcher fan-out.** A real self-
  contradiction in round 0. Resolved by splitting shared issue rows from per-watch job rows.
- **Jina returns Markdown.** Confirmed at `src/services/jina.py:85` (`Accept: text/plain`).
  Resolved rather than left open: fetch with `X-Return-Format: html` so
  `extract_digest_links` works unchanged on both archive roots and issue bodies.
- **`last_polled_at < ?` never claims NULL rows**; **claim-time stamping hides a failed row
  for 4h**; **end-of-run `latest_slug` update is not idempotent after partial fan-out**;
  **single-slug watermark is weak**. All correct. Replaced wholesale by a
  `publication_issues` table + a lease/`last_successful_poll_at` split — one table that
  closes four findings at once.
- **Orphaned spaces/candidates on `DROP TABLE`**, **`publications.name` is user-visible
  shared state** (a genuine hit against my own ADR-0043 argument), **resolver SSRF/abuse**,
  **API contract under-specified**, **test scope too thin** — all accepted as written.
- **"API never fetches" contradiction.** Accepted as a wording fix: the invariant is that
  the *poll loop* never runs in the API process. A bounded, rate-limited, user-initiated
  resolver fetch is explicitly allowed and now stated as such.

Rejected, with reasons:

- **`publication_aliases` table for mirrors.** Over-built for a problem with no observed
  instance. Cheaper: canonicalize at resolve time from the issue page's
  `<link rel="canonical">` / `og:url`, which is what actually identifies the publication.
  Add the table when a real collision appears, not before.
- **Durable outbox for digest enqueue.** Codex is right that "same transaction" was wrong
  wording for a Redis push, but its own alternative — mark committed-but-unenqueued jobs
  retryable — is already this codebase's documented posture (`email_webhook.py:143-147`
  marks the job `error` on enqueue failure, and a dedicated `/retry` endpoint exists). Reuse
  it; don't add an outbox for one task.

## Round 2 — Codex

Material flaws still remain:

- The plan says `email_digest.py` stays untouched, but current `email_digest.run()` calls `_create_context_blob()` per job, so “1 Gemini call per issue” is false when fan-out creates N jobs. Fix: change the processor contract to accept precomputed context / skip context generation, or move all context creation out of `email_digest.run()`.

- Failure backoff is impossible with the proposed schema: `poll_failures` increments, but there is no `last_failed_poll_at` or `next_poll_after`, and the scheduler query only checks `last_successful_poll_at`/lease. Fix: add `next_poll_after TIMESTAMP` and filter on it.

- “Enqueue with a small random delay” is not supported by the current Redis list queue, which only `LPUSH`es immediate tasks. Fix: implement jitter as scheduler-side spacing/date jobs, add a delayed queue, or drop the claim and rely on per-tick caps.

- Watch creation can race with polling: if a `newsletter_watches` row exists before its watermark/latest-issue seed is complete, a concurrent poll can fan out older issues to the new watcher. Fix: create the watch with watermark in the same transaction before it is poll-visible, or add an `active` flag flipped after seeding.

- “Skip watchers whose `watermark_slug` post-dates the issue” assumes slugs are chronologically comparable; they are publisher strings. Fix: store `watermark_issue_first_seen_at` or an archive-order sequence and compare that, not slug text.

- The legacy payload story is contradictory: the plan says existing `email_digest:` receipt rows are not dropped, but drops subscriptions/spaces and reshapes `email_digest_payloads` to `watch_id + slug`, leaving old rows unmigratable or unretryable. Fix: explicitly delete/cancel legacy receipt jobs and clear payload bodies, or define a real compatibility migration.

- Adding `newsletter_poll` to `_ROWLESS_TASKS` is necessary but not sufficient; `_TASK_HANDLERS` also needs a handler that treats `job_id` as `publication_id` and does not use `_make_handler()`’s job load path. Fix: specify `_handle_newsletter_poll(task)` and worker tests for dispatch.

- The `/p/<slug>` extractor makes the resolver beehiiv-shaped while the goal says public archives generally, including AlphaSignal. Fix: either declare provider support narrowly or add provider-agnostic/adapted issue extraction with fixtures per supported archive.

- Jina HTML mode is still an unverified core dependency, not an implementation detail; the plan’s own risk says the main reuse claim collapses if it fails. Fix: make a pre-implementation spike/gate the first step, with the Markdown extractor fallback already planned.

- The resolver’s “reuse SSRF-pinning helper in `public_html.py`” is imprecise: that helper pins direct `httpx` requests, but Jina fetches through `r.jina.ai`, so target URL validation must be separate and explicit. Fix: expose/use a pure public-URL validator before constructing the Jina URL.

VERDICT: REVISE
### Claude's response

Two findings were empirically settled rather than argued, and one of them exposed a factual
error in my own evidence:

- **Jina HTML mode — verified, risk closed.** `X-Return-Format: html` against
  `r.jina.ai/https://slothbytes.beehiiv.com/` returns **200, 666 KB of real HTML** with intact
  `<a href="/p/…">` anchors. `extract_digest_links` works unchanged. New detail found while
  verifying: archive hrefs are **relative** (`/p/debian-voting`), so extraction must resolve
  against the base URL. Promoted from "unverified core dependency" to specified behaviour.
- **Provider-shaped extractor — confirmed, and worse than Codex knew.** AlphaSignal uses
  `/news/<slug>`, not `/p/<slug>`. While checking, its `/archive` page advertised
  `alphasignal.ai/feed.xml` and `atom.xml` — **both live**. My "RSS 0 of 4" claim was a false
  negative caused by AlphaSignal's 403 to raw curl. Re-checked the beehiiv pair through Jina:
  they return the beehiiv HTML app shell, not XML, so their 404s were genuine. Corrected
  standing: **1 of 3 publications has a feed.** ADR-0060's evidence table and its rejected-
  alternatives entry have been fixed. Consequences for the plan: feeds become the *preferred*
  path where present, archive scrape the fallback, and the issue-URL prefix is **discovered at
  resolve time and stored per publication**, never hardcoded.

Accepted and fixed:

- **`_create_context_blob` is per-job, so "1 Gemini call per issue" was false.** Correct — it
  contradicted my own "processor untouched" claim. `run()` now takes an optional precomputed
  context and skips generation when supplied; the poll worker generates once per issue.
- **Backoff impossible with the proposed columns.** Correct. Added `next_poll_after
  TIMESTAMP`; the scheduler filters on it instead of hand-waving "skip N ticks".
- **Jitter isn't supported by a plain `LPUSH` list queue.** Correct — dropped. Replaced with
  scheduler-side per-tick caps, which need no queue change.
- **Watch creation races the poller.** Correct. The watch row is now inserted with its
  watermark already set, in one transaction, using the issue list the resolve step already
  fetched — so there is no window in which it is poll-visible but unseeded.
- **Slugs aren't chronologically comparable.** Correct. Watches store `watched_from`; the
  comparison is against `publication_issues.first_seen_at`, not slug text.
- **Legacy receipt rows were left contradictory.** Correct. The teardown migration now
  explicitly deletes legacy `email_digest:%` jobs and their payloads along with the
  subscriptions and spaces they belong to. This also weakens one leg of the keep-the-sentinel
  argument (no data migration needed any more); the other two — 8 production call sites plus
  test assertions — still stand, and the rationale has been trimmed to say so honestly.
- **`_ROWLESS_TASKS` alone is insufficient.** Correct. `_handle_newsletter_poll(task)` is now
  specified explicitly as not using `_make_handler()`'s job-load path.
- **SSRF helper imprecision.** Correct — `_fetch_pinned` pins direct httpx requests, but the
  fetch goes through `r.jina.ai`. A pure public-URL validator is now applied to the target URL
  *before* the Jina URL is constructed.

Nothing rejected this round.

## Round 3 — Codex

Material flaws:

- `POST /api/newsletter-digest` takes only `{archive_url, name}` but step 6 says it uses the issue list, `feed_url`, and `issue_path_prefix` from the prior resolve call; that data is neither in the request nor guaranteed server-side. Fix: return a short-lived resolver token/cache key from `/resolve` and require it on create, or re-resolve `archive_url` server-side during create.

- The fan-out claim is backwards: `email_digest_payloads.job_id` is a non-null PK/FK, so “`INSERT OR IGNORE` payload first, then create job only if inserted” cannot work unless the job row already exists. Fix: add a separate `(watch_id, slug)` delivery/claim table, or create job + payload in one transaction and roll back/delete the job on uniqueness conflict.

- The publication lease can poll too early: the lease `UPDATE` only checks `poll_lease_until`, so a duplicate queued task after a successful poll can reacquire the lease before `next_poll_after`. Fix: include `(next_poll_after IS NULL OR next_poll_after < :now)` in the lease claim itself.

- `watched_from < issue.first_seen_at` can skip the immediate latest issue if both timestamps are generated in the same transaction or clock precision collapses them. Fix: make the first-watch latest issue an explicit delivery by slug/watch_id, independent of the `watched_from` filter.

- Reusing `email_digest.run(job, precomputed_context=...)` is underspecified at the queue boundary: current worker calls processor modules with only the job dict, so queued `email_digest` jobs cannot receive the precomputed blob unless it is persisted or carried in the task and passed through. Fix: store precomputed context on `email_digest_payloads` or extend `_handle_email_digest` to pass task payload fields into `run()`.

- Retry semantics break for jobs whose original enqueue failed after poll fan-out: retry currently finds the latest failed digest by subscription/watch, but the plan does not say the reshaped query returns enough task context to pass the precomputed context or avoid regenerating it. Fix: define `latest_retryable_email_digest_job(watch_id)` against the new schema and persist everything retry needs.

- `publication_issues` has `published_at TEXT` but no stable ordering fallback from feeds vs scraped archives; “oldest first” is ambiguous when `published_at` is missing or malformed. Fix: store `discovered_order`/`source_order` per poll batch and sort by parsed `published_at`, then source order, then `first_seen_at`.

- The feed path is still transport-vague: feeds must parse as XML, but the project’s current Jina wrapper returns stripped Markdown, and HTML mode is for archive pages, not RSS/Atom. Fix: add explicit `fetch_feed_xml_via_jina()` behavior and fixtures proving Jina returns parseable XML for AlphaSignal.

VERDICT: REVISE
### Claude's response

- **Fan-out ordering was a real bug.** Correct: `email_digest_payloads.job_id` is a non-null
  PK/FK, so "INSERT OR IGNORE the payload, then create the job only if it inserted" is
  impossible. Fixed using the superseded plan's own precedent: create job + payload in **one
  transaction**, and let a `UNIQUE(watch_id, slug)` violation roll the whole thing back — which
  disposes of the just-created job row too, leaving no orphan — then skip that watcher. No new
  delivery table needed.
- **Feed transport — deleted rather than fixed.** Codex asked for `fetch_feed_xml_via_jina()`
  plus XML fixtures. Verified instead what Jina actually returns for `alphasignal.ai/feed.xml`
  under `X-Return-Format: html`: **clean HTML with 100 distinct `/news/` permalinks**, titles in
  `<h3><a>`. So a feed needs no XML parsing at all — it is simply a better-structured page on
  the *same* fetch-and-extract path as an archive root. The "must parse as XML with ≥1 entry"
  rule is gone; validation is now identical for both sources (≥2 distinct issue links). This
  also materially reduces the pagination risk where a feed exists: 100 entries vs the archive
  page's 6.
- **Precomputed context at the queue boundary.** Correct — the worker calls processors with only
  the job dict. Fixed by persisting the context on `email_digest_payloads.context_md`, which
  `run()` reads. This also closes the retry finding in the same stroke: a retried job re-reads
  the stored context instead of regenerating it, and `latest_retryable_email_digest_job(watch_id)`
  is now defined against the new schema.
- **Lease can reacquire before `next_poll_after`.** Correct; the claim `UPDATE` now tests both.
- **First-watch issue can be skipped by timestamp collision.** Correct. The first-watch ingest is
  now an **explicit delivery by `(watch_id, slug)`**, not a consequence of the `watched_from`
  filter.
- **Ordering ambiguity when `published_at` is missing or malformed.** Correct. Added
  `publication_issues.source_order`; sort is parsed `published_at` → `source_order` →
  `first_seen_at`.
- **Create lacks the resolve output.** Correct. Rather than a short-lived resolver token with its
  own expiry semantics, `POST /api/newsletter-digest` **re-resolves `archive_url` server-side**
  during create. It costs one extra fetch on a rare action, is authoritative, and adds no cache
  to invalidate.

Nothing rejected this round.

## Round 4 — Codex

Material flaws:

- `publication_issues` as the “new work” source loses deliveries on partial failure: if the poller inserts issue rows, then crashes/fails before fetching issue pages or fanning out every watcher, the next run sees those slugs as already inserted and skips them forever. Fix: make per-watch delivery rows the idempotent work source, or reprocess discovered recent issues by selecting missing `(watch_id, slug)` payloads, not only newly inserted `publication_issues`.

- The commit-then-enqueue posture still strands pending digest jobs if the process crashes after committing `jobs` + `email_digest_payloads` but before enqueue/mark-error; generic recovery excludes `email_digest:%`, and `latest_retryable_email_digest_job()` only handles errors. Fix: add a digest outbox, or make `/retry`/scheduler detect stale pending digest payloads and enqueue them.

- Poll failure semantics are too broad: a Gemini context failure before fan-out would make the whole issue delivery fail, even though current `_create_context_blob()` is best-effort and candidate extraction should still proceed. Fix: treat context generation as best-effort and fan out with `context_md = NULL` or a generated-empty marker on Gemini failure.

- “Sort by parsed `published_at`, then `source_order`, then `first_seen_at`” does not specify direction, and feed/archive source order is often newest-first. Fix: define `source_order_oldest_first` explicitly, or sort source order descending when the fetched source is newest-first.

- `context_md` is added to `email_digest_payloads` while also claiming “null-content-on-success behaviour”; it is unclear whether context is retained indefinitely after success. Fix: explicitly clear `context_md` together with `subject/html/text` on success, while retaining it only for retryable error rows.

- Resolver cache keyed only by raw input string can serve cross-user stale or poisoned resolution if canonicalization behavior changes or a user resolves a mirror before canonical collapse fixes. Fix: cache by normalized query plus resolved canonical archive URL with a short TTL, and never trust cache entries that fail current public-URL validation.

VERDICT: REVISE
### Claude's response

All six accepted; nothing rejected. The first is the significant one and it invalidated a
design idea I had been leaning on since round 2.

- **"Newly inserted `publication_issues` rows are the new work" is wrong.** Correct: insert the
  issue rows, crash before fan-out, and the next poll sees those slugs as already known and skips
  them permanently. The seen-set is the wrong work source. Replaced: the work source is now
  **missing `(watch_id, slug)` payload rows**, computed each poll across a recent window of
  `publication_issues` × live watches. That is idempotent *and* self-healing — a crashed run is
  repaired by the next tick rather than silently losing an issue.
- **Stranded pending jobs after a crash between commit and enqueue.** Correct, and generic
  recovery deliberately excludes `email_digest:%`. Folded into the same query: the poll also
  re-enqueues payloads whose job is still `pending` beyond a threshold. This reuses the
  superseded plan's "re-push on pending" idiom rather than adding the outbox rejected in round 1
  — the difference from round 1 is that there is now a periodic scan in which to do it.
- **Gemini failure shouldn't sink the delivery.** Correct — `_create_context_blob` is best-effort
  today and the plan silently made it fatal. Context is now explicitly best-effort:
  `context_md = NULL` on failure and fan-out proceeds.
- **Sort direction unspecified.** Correct, and feeds/archives are newest-first, so the naive
  reading was backwards. Now stated explicitly.
- **`context_md` retention.** Correct ambiguity against the inherited null-on-success rule.
  Cleared with `subject`/`html`/`text` on success; retained only on error rows, which is exactly
  what makes retry cheap.
- **Resolver cache.** Correct. Short TTL, keyed by normalized query, and cache entries are
  re-validated against the public-URL check on read rather than trusted.

## Round 5 — Codex (MAX_ROUNDS)

Material flaws:

- The “missing deliveries” repair only scans “current fetch plus last N days,” but `N` is undefined and any outage longer than that permanently skips already-seen, never-delivered issues. Fix: scan all `publication_issues` missing `(watch_id, slug)` deliveries, or store explicit delivery status rows and page through them.

- Issue bodies are stored per watcher in `email_digest_payloads`; a 666 KB Jina HTML issue × 500 watchers is hundreds of MB transiently, and failed/stale rows retain it. Fix: store fetched issue HTML once per `publication_issue` and have per-watch payloads reference it, or enforce a strict size cap plus compression.

- The new Jina HTML fetch path has no stated response-size cap; the existing Jina wrapper reads the full response body, so a malicious/huge archive can cause memory and SQLite bloat. Fix: stream and cap Jina archive/issue responses before parsing or storing, mirroring the old webhook payload cap.

- Startup recovery still appears broken for digest jobs: [worker.py](/C:/Users/leone/Desktop/codeKitchen/ownix/src/worker.py:352) reaps stale processing jobs and sends generic `reprocess:{job_id}` buttons, while only dashboard recovery special-cases `email_digest:`. Fix: update `worker.reap_stale_jobs()` to suppress generic reprocess notifications for `email_digest:%` and rely on the digest retry path.

- `context_md = NULL` means two different states: Gemini failed before context generation, or there was intentionally no context; `email_digest.run()` may then fall back to generating per watcher unless guarded carefully. Fix: add an explicit `context_status`/`context_attempted` flag or define that archive digest jobs never call `_create_context_blob()` when `context_md` is null.

- Concurrent `POST /api/newsletter-digest` for the same `archive_url` can race on `publications.archive_url UNIQUE`; the plan says “creates or reuses” but does not define the conflict path or metadata merge. Fix: use an atomic upsert/select helper that returns the existing publication and updates missing `feed_url`/`issue_path_prefix` safely.

VERDICT: REVISE
### Claude's response

All six accepted and applied; none disputed. **These fixes were made after the final round, so
Codex has not reviewed them.** The plan carries no `APPROVED` verdict.

- **Undefined recency window.** Correct — "last N days" silently abandons any outage longer than
  N. Window removed entirely; the repair join now covers all `publication_issues` for the
  publication. It is issues × watches for one publication, both small and indexed.
- **Issue body duplicated per watcher.** The most substantive find of the round. A fetched page
  is hundreds of KB; × 500 watchers is hundreds of MB through SQLite per issue, retained on
  failure. Body moved to `publication_issues.body_html`, stored once and cleared when every
  delivery succeeds; `email_digest_payloads` drops its `subject`/`html`/`text` columns and
  references the issue. This forced an honest amendment to the ADR-0043 reconciliation, now
  recorded in the plan: shared rows hold transient publisher content, not merely bookkeeping.
- **No response-size cap on Jina fetches.** Correct; the deleted webhook had a 2 MB cap and the
  replacement had none. 4 MB cap, rejected before parsing or storage.
- **`reap_stale_jobs()` offers generic reprocess for digest jobs.** Correct and verified at
  `src/worker.py:352` — only the dashboard path special-cases the sentinel. Added as an explicit
  fix rather than a deletion.
- **Ambiguous null `context_md`.** Correct. Resolved with the cheaper of the two options: context
  generation is unconditionally the poller's job, and `run()` never falls back to
  `_create_context_blob()`. No status flag needed.
- **Concurrent create races `archive_url UNIQUE`.** Correct. Atomic upsert-or-select that fills
  only missing metadata rather than overwriting a concurrent writer.

### Outcome

Deadlock at the round cap, not convergence. Severity fell monotonically — round 1 surfaced 16
findings including three showstoppers (queue contract, `SCHEMA_SQL`, payload/fan-out
contradiction); round 5 surfaced 6, all hardening. Two rounds produced empirical corrections
that changed the design rather than just the plan: Jina HTML mode, and the discovery that
AlphaSignal publishes a feed after all — which had been recorded as fact in ADR-0060 and was
wrong.

## Round 6 — Codex (cap extended by user)

_The user extended MAX_ROUNDS specifically to review the round-5 fixes and the `Dismiss rest` addition, which had been applied after the final round. Every finding below is a consequence of exactly those changes — the extension was warranted._

Findings:

- `Dismiss rest (N)` cannot be safely frontend-only: the existing dismiss path allows `pending` and `promoting`, so a candidate that becomes `promoting` after the UI snapshot can still be dismissed. Fix: add a backend pending-only dismiss mode or endpoint and have the UI call that for bulk dismiss.

- `email_digest_payloads(publication_id, slug)` is used as a hard dependency on `publication_issues`, but the plan only declares the FK to `newsletter_watches`; orphan payloads can point at missing issue bodies. Fix: add a composite FK from `(publication_id, slug)` to `publication_issues(publication_id, slug)` with the intended delete behavior.

- Shared `publication_issues.body_html` cleanup is still underspecified now that payload rows no longer carry bodies; clearing at enqueue/fanout completion would break pending jobs and retries. Fix: clear only after a DB predicate proves every live watch delivery for that issue is terminal-success or intentionally dismissed/cancelled, never merely created/enqueued.

- The missing-delivery repair and body cleanup paths need efficient issue-scoped lookup, but the schema only adds an index on `email_digest_payloads.watch_id`. Fix: add an index on `email_digest_payloads(publication_id, slug)` and use it for repair, cleanup, and retry/body joins.

- Atomic publication upsert “only fills missing fields” preserves bad non-null `feed_url` / `issue_path_prefix` forever after resolver mistakes or publisher changes. Fix: update existing publication metadata when the resolver returns a validated replacement, with `last_resolved_at`/confidence rules to avoid churn.

- The 4MB Jina cap says reject before parsing/storing, but does not define how oversize individual issues affect fanout state; a permanently oversize issue could be retried every poll and block body cleanup logic. Fix: mark oversized issues as terminal skipped with an observable reason, then continue later issues/watch fanout.

VERDICT: REVISE
### Claude's response

All six accepted and applied; none disputed. One of them corrects a claim I had made to the user.

- **`Dismiss rest` is not frontend-only.** Verified: `dismiss_digest_candidate` accepts
  `status IN ('pending','promoting')` (`src/database.py:3448`), so a bulk loop over a UI snapshot
  could dismiss a candidate that turned `promoting` in between — flipping it to `dismissed` while
  its job is being created. Bulk dismiss now uses a **pending-only** variant behind a flag on the
  existing endpoint; single-card dismiss is unchanged. My "zero backend work" advice was wrong.
- **Missing composite FK.** Correct — moving the body to `publication_issues` made
  `(publication_id, slug)` a hard dependency that nothing enforced. Added as a composite FK with
  `ON DELETE RESTRICT`.
- **`body_html` cleanup was underspecified.** Correct, and the naive reading was actively
  harmful: clearing at fan-out/enqueue completion would strip the body from jobs that are merely
  created, and make every errored digest permanently unretryable — precisely the outcome the
  superseded plan refused. Now gated on a predicate proving every live delivery for the issue is
  terminal.
- **Index gap.** Correct — `watch_id` serves none of the three new `(publication_id, slug)`
  access paths (repair join, cleanup predicate, retry body lookup). Index added.
- **Upsert froze bad metadata forever.** Correct. `last_resolved_at` added; validated resolver
  values replace existing ones after a cooldown, which also prevents two concurrent adds from
  ping-ponging the row.
- **Oversized issues retry forever and block cleanup.** Correct. `publication_issues.skip_reason`
  marks them terminal so fan-out continues past them.

### Outcome

Six rounds. Findings per round: **16 → 10 → 8 → 6 → 6 → 6**. Still `REVISE`, and the round-6
fixes are themselves unreviewed — the loop's steady state is that an adversarial reviewer keeps
finding smaller things, not that the plan is unsound. Severity has fallen from "this cannot be
enqueued at all" to "index this join" and "define this cleanup predicate". Two rounds produced
empirical corrections that changed the design (Jina HTML mode; AlphaSignal's feed existing), and
this round caught a real race in advice already given to the user.

## Round 7 — Codex

Findings:

- `body_html` cleanup is still race-prone: the predicate only checks existing `email_digest_payloads` rows, but fanout creates payloads per watcher and may enqueue early, so a fast digest job can finish and clear `body_html` before later watchers’ payload rows exist. Fix: create all payload rows for an issue before enqueueing any of their jobs, or make cleanup also assert there are no missing deliveries for live watches.

- The cleanup predicate ignores the same “missing deliveries” definition that powers repair; a crash after fetching/storing `body_html` but before payload creation could make the issue look clean if cleanup is invoked with zero payload rows. Fix: define cleanup as `no live watch needing this issue lacks a payload row AND all existing live-watch payload jobs are terminal`.

- The 4MB Jina cap still needs an implementation requirement to stream and abort at `4MB + 1`; otherwise a naive `response.text`/`aread()` implementation still takes the memory hit the plan says it avoids. Fix: specify a streaming byte-counted fetch helper shared by archive, feed, and issue fetches.

- `skip_reason='oversize'` must be excluded from both periodic outstanding work and first-watch explicit latest delivery; the plan states the former but not the latter. Fix: route explicit latest delivery through the same skip-aware issue ingestion path.

VERDICT: REVISE
### Claude's response

Four findings, down from six. All accepted; none disputed. Two are the same race seen from
different angles.

- **`body_html` cleanup race (findings 1 and 2).** Correct, and my round-6 predicate was
  half-written. Checking only "existing payload rows are terminal" passes **vacuously** when the
  rows do not exist yet: a fast first watcher can finish and clear the body before later
  watchers' rows are created, and a crash after storing the body but before any payload creation
  looks clean with zero rows. The predicate now has two halves — *no live watch is still missing
  a payload row* (reusing §4 step 4's missing-delivery definition) **and** *every existing
  live-watch payload job is terminal*. Structurally reinforced too: **all payload rows for an
  issue are created before any of their jobs is enqueued**, which removes the window rather than
  just detecting it.
- **Streaming is the requirement, not the cap.** Correct — a 4 MB check bolted onto
  `fetch_markdown`'s read-everything shape prevents the SQLite row but not the memory spike it
  was supposed to prevent. Now specified as one shared byte-counted streaming helper aborting at
  4 MB + 1, used by archive, feed and issue fetches alike.
- **`skip_reason` unhandled on the first-watch path.** Correct — I specified skip-awareness for
  periodic outstanding work but the first-watch explicit delivery is a separate path, so a new
  watcher would have been handed the one issue the system had already given up on. Both now
  route through the same skip-aware ingestion.

### Outcome

Findings per round: **16 → 10 → 8 → 6 → 6 → 6 → 4**. The plateau broke. Severity is now entirely
in implementation-requirement territory — "stream, don't buffer", "reuse this predicate in that
other path" — with no design questions left open and no standing disagreements beyond the two
recorded in round 1 (`publication_aliases`, durable outbox).
