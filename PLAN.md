# Plan: Newsletter digest reads public archives, not email (ADR-0060)

_Round 7 — revised by Claude after Codex round 7. This revision is UNREVIEWED by Codex._

## Goal

#607 shipped the newsletter digest as an inbound-mail pipeline: one generated alias per
subscription, a Cloudflare Email Routing catch-all on `leondev.xyz` into a Worker, and
`POST /webhook/email-digest` which drops any message whose `from` doesn't match the
subscription's registered `sender_email` (`src/api/email_webhook.py:83`). It has never
ingested a single issue, and cannot be onboarded without a human hand-wiring the Cloudflare
zone per alias — Gmail's forwarding-verification code arrives from
`forwarding-noreply@google.com` and is silently dropped by that same sender check, and the
alias is rejected by newsletter signup forms because `leondev.xyz` is a catch-all domain.
That fails the stated requirement: identical behaviour for 1 user and 500, no human
operation.

Replace the transport: **follow each newsletter's public web presence** — its feed where one
exists, its archive page otherwise — poll every 4 hours via Jina Reader, and feed new issues
into the existing candidate pipeline. Delete the email path.
Decision record: `docs/adr/0060-newsletter-digest-reads-public-archives.md`.
Domain terms: `CONTEXT.md` → **Watched newsletter**, **Issue**, **Issue watermark**.
Superseded plan: `docs/plans/2026-09-05-email-digest-inbound-alias-superseded.md`.

### Verified evidence (2026-09-06/07)

| Newsletter   | Sender                         | Archive                               | Issue URLs     | Feed | Jina |
| ------------ | ------------------------------ | ------------------------------------- | -------------- | ---- | ---- |
| AlphaSignal  | `news@alphasignal.ai`          | `alphasignal.ai` (403s raw fetch)     | `/news/<slug>` | ✅ `feed.xml`, `atom.xml` | ✅ |
| Sloth Bytes  | `slothbytes@tx2.beehiiv.com`   | `www.slothbytes.dev` + beehiiv mirror | `/p/<slug>`    | ✗    | ✅   |
| Import React | `importreact@mail.beehiiv.com` | `importreact.beehiiv.com`             | `/p/<slug>`    | ✗    | ✅   |

- A fetched Sloth Bytes issue carried every section and every outbound link with UTM intact —
  the same payload `email_digest.py` extracts from an email body today.
- **Jina `X-Return-Format: html` verified**: 200, 666 KB of real HTML, `<a href="/p/…">`
  anchors intact. Hrefs are **relative**, so extraction resolves against the base URL.
- **Feed coverage is 1 of 3, not 0.** An earlier "no feeds anywhere" reading was a false
  negative from AlphaSignal's 403 to raw curl. Re-checked through Jina: AlphaSignal's feed is
  live; both beehiiv publications return the beehiiv HTML app shell, so their 404s are real.
- **Issue URL shape is publisher-specific** (`/p/` vs `/news/`) — discovered at resolve time,
  stored per publication, never hardcoded.

## Approach

### 1. Schema

Applied in **both** places, because this repo creates fresh databases from `SCHEMA_SQL`
(`src/database.py:301`) independently of `_MIGRATIONS` — a migration alone leaves new installs
on the old schema. Each `_MIGRATIONS.append` entry carries the `# rollback:` comment ADR-0058
requires, and a test asserts fresh-`SCHEMA_SQL` and fully-migrated databases produce identical
`sqlite_master` output.

- `publications` — **shared across tenants, no `chat_id`**:
  `id TEXT PK`, `archive_url TEXT NOT NULL UNIQUE`, `feed_url TEXT`,
  `issue_path_prefix TEXT` (e.g. `/p/`, `/news/` — learned at resolve time),
  `fetched_title TEXT`, `last_resolved_at TIMESTAMP`, `last_successful_poll_at TIMESTAMP`,
  `next_poll_after TIMESTAMP`, `poll_lease_until TIMESTAMP`,
  `poll_failures INTEGER NOT NULL DEFAULT 0`, `created_at`.
  `fetched_title` is **scraped metadata, never user-facing** — the display name lives on the
  watch, so no tenant ever writes a shared row.
- `publication_issues` — shared seen-set, one row per published issue:
  `publication_id TEXT NOT NULL REFERENCES publications(id) ON DELETE CASCADE`,
  `slug TEXT NOT NULL`, `url TEXT NOT NULL`, `title TEXT`, `published_at TEXT`,
  `source_order INTEGER NOT NULL`, `first_seen_at TIMESTAMP NOT NULL`,
  `body_html TEXT`, `body_fetched_at TIMESTAMP`, `skip_reason TEXT`,
  `PRIMARY KEY (publication_id, slug)`.
  Replaces a single `latest_slug` watermark.
  **The issue body is stored once here, not per watcher.** A fetched page is hundreds of KB;
  duplicating it across 500 watchers' payload rows would put hundreds of MB through SQLite for
  one issue, and failed rows would retain it. Per-watch payloads reference the issue instead of
  copying it. **`body_html` is cleared only when a DB predicate proves no live delivery still
  needs it**, and that predicate has *two* halves — checking only the first is a race:
  1. **no live watch is still missing a payload row** for this `(publication_id, slug)` — the
     same missing-delivery definition §4 step 4 uses for repair; and
  2. every existing payload row for it, whose watch still exists, is a `done` job or an
     intentionally cancelled/dismissed one.

  Half 2 alone passes vacuously when payload rows do not exist yet — a fast first watcher could
  finish and clear the body before later watchers' rows are created, and a crash after storing
  `body_html` but before any payload creation would look "clean" with zero rows. Clearing at
  fan-out or enqueue completion is likewise wrong: it strips the body out from under jobs that
  are merely *created*, and makes every errored digest permanently unretryable — the failure
  mode the superseded plan explicitly refused to accept.
  `source_order` is the item's index in the fetched
  document, and **both feeds and archive pages list newest first**, so index 0 is the newest.
  Processing order (oldest first) is therefore
  `ORDER BY parsed published_at ASC NULLS LAST, source_order DESC, first_seen_at ASC` — the
  `DESC` on `source_order` is not a typo, it reverses the source's newest-first ordering.
  `skip_reason` marks an issue **terminally skipped** (e.g. `oversize`) so it stops being
  selected as outstanding work. Without it, an issue that permanently exceeds the fetch cap is
  re-attempted every poll forever and, having no body, blocks body-cleanup accounting.
- `newsletter_watches` — per tenant:
  `id TEXT PK`, `chat_id INTEGER NOT NULL`, `publication_id TEXT NOT NULL REFERENCES
  publications(id) ON DELETE CASCADE`, `space_id TEXT NOT NULL REFERENCES spaces(id) ON DELETE
  CASCADE`, `name TEXT NOT NULL` (the user's own label), `watched_from TIMESTAMP NOT NULL`,
  `created_at`, `UNIQUE(chat_id, publication_id)`, indexed on `publication_id`.
  **`watched_from` is a timestamp, not a slug** — slugs are publisher strings with no
  chronological order, so the fan-out filter compares
  `publication_issues.first_seen_at > watched_from`.
- `email_digest_payloads`: replace `subscription_id` with `watch_id TEXT REFERENCES
  newsletter_watches(id) ON DELETE SET NULL` (nullable, for `ON DELETE SET NULL`) plus
  `publication_id TEXT NOT NULL`, `slug TEXT NOT NULL` and `context_md TEXT`, unique on
  **`(watch_id, slug)`** — per watcher, since fan-out creates one job per watcher per issue. Retains `job_id TEXT PK REFERENCES jobs(id) ON DELETE CASCADE` and
  the null-content-on-success behaviour from the superseded plan. The body columns
  (`subject`/`html`/`text`) are **dropped** — the body is read from
  `publication_issues.body_html` via `(publication_id, slug)` rather than copied per watcher.
  That read is a real dependency, so it gets a real constraint: a **composite
  `FOREIGN KEY (publication_id, slug) REFERENCES publication_issues(publication_id, slug)`**,
  `ON DELETE RESTRICT`, preventing a payload from pointing at an issue body that no longer
  exists. Indexed on `watch_id` **and on `(publication_id, slug)`** — the latter is what the
  missing-delivery repair join, the body-cleanup predicate, and retry's body lookup all key on,
  and none of them are served by the `watch_id` index.
  `context_md` holds the **per-issue Gemini editorial blob, generated once and persisted here**
  — the worker calls processors with only the job dict, so a precomputed value cannot ride the
  task envelope. Persisting it also makes retry cheap: a re-driven job re-reads the stored
  context instead of regenerating it. `context_md` is **cleared on success** and retained only
  on error rows, which is what keeps a failed digest retryable.
  **A null `context_md` never triggers per-job generation.** Context is owned entirely by the
  poll worker; `run()` inserts the stored text when present and inserts nothing when absent. It
  must not fall back to `_create_context_blob()`, or a Gemini failure during polling would
  silently become one Gemini call per watcher — the exact cost this design exists to avoid. No
  `context_status` flag is needed once generation is unconditionally the poller's job.
- **Teardown migration**, in this order: delete legacy `email_digest:%` receipt jobs and their
  `email_digest_payloads` rows; then for every `newsletter_subscriptions` row delete its backing
  `spaces` row (cascading `space_urls`, `context_blobs`, `digest_candidates`, and the
  subscription); then `DROP TABLE newsletter_subscriptions`. Order matters — dropping the table
  first orphans every space and candidate, because the cascade runs spaces→subscription, not the
  reverse. Legacy receipt jobs are deleted rather than carried, because their payload rows
  cannot satisfy the new `(watch_id, slug)` shape.
- `digest_candidates` otherwise **untouched** — `UNIQUE(space_id, canonical_url)` already gives
  cross-issue dedup and the `pending/promoting/promoted/dismissed` claim lock stands.

### 2. Archive resolver (`src/services/newsletter_archive.py`, new)

Pure resolution, no writes. Given whatever the user typed, returns
`(archive_url, feed_url | None, issue_path_prefix, fetched_title, recent_issues)`:

1. Input looks like a URL → strip query string, strip a trailing issue path → root.
   (Real-world observed input is a "view in browser" link:
   `https://www.slothbytes.dev/p/next-js-16-3?utm_source=…`.)
   Input looks like an email → probe `[f"{local}.{root}", root, domain]`, `root` being the
   sender domain minus its leading label. Verified 3/3 against the table above.
2. **Prefer a feed — as a page, not as XML.** Look for
   `<link rel="alternate" type="application/(rss|atom)+xml">` on the root, then try
   `/feed.xml`, `/atom.xml`, `/feed`, `/rss`. Fetch each candidate through the **same** Jina
   `X-Return-Format: html` path as everything else: verified, Jina renders
   `alphasignal.ai/feed.xml` into clean HTML carrying **100 distinct `/news/` permalinks** with
   titles in `<h3><a>`. No XML parser is introduced, and feed and archive share one
   fetch-and-extract code path. Acceptance is the same test used for archives — **≥2 distinct
   issue links** — which is what correctly rejects beehiiv's `/feed`, since a 200 proves nothing
   (Jina renders 404s as 200, and beehiiv returns its HTML app shell there).
3. **Otherwise scrape the archive.** Collect same-origin links, group by first path segment,
   and take the segment with the most distinct dated children as `issue_path_prefix`. This
   yields `/p/` for beehiiv and `/news/` for AlphaSignal with no hardcoded provider list.
   Accept only if ≥2 distinct issue links are found.
4. **Canonicalize** to the host the publisher advertises: read `<link rel="canonical">` /
   `og:url` from one issue page and derive the root from it. This collapses
   `slothbytes.beehiiv.com` onto `www.slothbytes.dev` *before* a `publications` row exists.

**Abuse controls** — this endpoint turns user input into server-paid remote fetches. A **pure
public-URL validator** (scheme in `http`/`https`, hostname resolves to a public address) is
applied to the *target* URL **before** the `r.jina.ai/<url>` string is constructed. This is
deliberately separate from `public_html._fetch_pinned`, which pins *direct* httpx connections
and does not protect a fetch made through a third-party proxy. **Known gap:** that validator
only covers the initial URL — Jina does not re-validate its own redirect hops, and it exposes no
documented header to disable or constrain that. Accepted as residual risk for now; tracked in
issue #615 rather than closed here, since closing it means either dropping Jina for these fetches
(losing JS-rendering/anti-bot coverage some publishers require) or a local rendering fallback.
Plus: max 4 probe fetches per
request and a per-`chat_id` rate limit.

Resolver results are cached by **normalized** query with a **short TTL**, and every cache hit is
re-validated against the public-URL check before use — a cache keyed on raw user input and
trusted blindly would serve one user a stale or mirror-shaped resolution after canonicalization
behaviour changes, across tenants.

### 3. Poll scheduler (`src/main.py`)

A 15-minute `AsyncIOScheduler` job beside `_drain_purge_outbox` / `_reap_intake_state` selects
publications that are **due, unleased, and watched**:

```sql
WHERE (next_poll_after IS NULL OR next_poll_after < :now)
  AND (poll_lease_until IS NULL OR poll_lease_until < :now)
  AND EXISTS (SELECT 1 FROM newsletter_watches w WHERE w.publication_id = publications.id)
ORDER BY next_poll_after LIMIT :per_tick_cap
```

`IS NULL` on both time clauses matters — a newly created publication has neither, and a `<`
comparison alone would never claim it. Spreading is done by the **per-tick cap plus
`ORDER BY`**, not by delayed delivery: the queue is a plain Redis list (`LPUSH`) with no
scheduled-task support, so "enqueue with jitter" is not available. Fixed 4h cadence; no
adaptive per-newsletter cadence (rejected: observed Sloth Bytes gaps run 2–14 days, no rhythm).

### 4. Poll worker (`src/processors/newsletter_poll.py`)

Envelope: `{"task": "newsletter_poll", "job_id": <publication_id>}`. Two worker changes, both
following existing precedent: `newsletter_poll` joins `_ROWLESS_TASKS` (`src/worker.py:333`,
alongside `job_purge` and `bookmarks_enrich`), **and** `_TASK_HANDLERS` gains a dedicated
`_handle_newsletter_poll(task)` that reads `task["job_id"]` as a publication id and does **not**
go through `_make_handler()`'s job-load path. Carrying the operated-on id in `job_id` is the
established convention for rowless tasks and satisfies `job_queue.enqueue()`'s hard check
(`src/job_queue.py:57`) without touching the shared envelope contract.

1. **Lease**: `UPDATE publications SET poll_lease_until = :now_plus_10m WHERE id = ?
   AND (poll_lease_until IS NULL OR poll_lease_until < :now)
   AND (next_poll_after IS NULL OR next_poll_after < :now)`. No match → another worker owns it,
   **or it is not due yet** — the second clause is what stops a duplicate queued envelope from
   re-polling immediately after a successful run.
2. Fetch `feed_url` if set, else the archive root via Jina with `X-Return-Format: html`.
   Extract issue links using `issue_path_prefix`, resolving **relative hrefs against the base
   URL**. Every Jina fetch — archive, feed and issue alike — goes through **one shared
   byte-counted streaming helper that aborts the response at 4 MB + 1** and never materialises
   the body, mirroring the 2 MB cap the deleted webhook enforced (`email_webhook.py:118-125`).
   Streaming is the requirement, not the cap: `fetch_markdown`'s current
   read-the-whole-response shape would take the full memory hit *before* any size check could
   reject it, so a "cap" implemented on top of it would prevent the SQLite row but not the
   memory spike.
   An **issue** that exceeds the cap is marked `skip_reason = 'oversize'` and treated as
   terminal: fan-out continues with the remaining issues rather than aborting the run, and the
   skipped issue stops appearing as outstanding work. Otherwise a single permanently-oversized
   issue would be re-fetched every four hours forever and, having no body, would sit
   indefinitely in the way of that issue's body-cleanup accounting.
3. `INSERT OR IGNORE` every discovered issue into `publication_issues` (recording
   `source_order`). This is the **seen-set, not the work list**.
4. **Compute outstanding work as missing deliveries**, not as newly-inserted issues: join **all**
   `publication_issues` for this publication against live `newsletter_watches` where
   `watched_from < issue.first_seen_at`, and select the `(watch_id, slug)` pairs with **no
   `email_digest_payloads` row**. Using "rows that just inserted" instead would lose an issue
   permanently whenever a run crashes after inserting the issue row but before fanning out — the
   seen-set would already claim it as handled. **No recency window**: a bounded "last N days"
   scan silently gives up on any outage longer than N, and the join is cheap (issues × watches
   for one publication, both small, both indexed). The same scan re-enqueues payloads whose
   `jobs` row has been `pending` past a threshold, repairing a crash between commit and enqueue
   (see §5).
5. For each outstanding issue, oldest first: fetch the issue page **once**; generate the Gemini
   editorial context **once**, **best-effort** — a Gemini failure sets `context_md = NULL` and
   fan-out proceeds, matching `_create_context_blob`'s existing non-fatal posture rather than
   sinking the whole delivery. Then, per watcher, create the `jobs` row **and** its
   `email_digest_payloads` row **in one transaction**. A `UNIQUE(watch_id, slug)` violation
   rolls the whole transaction back — disposing of the just-created job row, so no orphan
   survives — and that watcher is skipped. The payload row cannot be inserted first and checked:
   `job_id` is a non-null PK/FK, so the job must exist before the payload does. This is the same
   commit-or-rollback idiom the superseded plan used for duplicate deliveries.
   **All payload rows for an issue are created before any of their jobs is enqueued.** Enqueuing
   as you go lets a fast job finish, run the cleanup predicate, and clear `body_html` while later
   watchers still have no payload row — the body then vanishes before they are served.
6. On success: clear lease, set `last_successful_poll_at`, `next_poll_after = now + 4h`, reset
   `poll_failures`. On failure: clear lease, increment `poll_failures`, set
   `next_poll_after = now + min(4h × 2^poll_failures, 24h)`. The **lease** prevents concurrent
   polls; `next_poll_after` governs retry — so a failed run is not hidden for four hours.

### 5. Reuse the digest processor

`src/processors/email_digest.py` keeps `extract_digest_links`, `canonicalize_candidate_url`,
`_resolve_links`, `_insert_candidates`, `_create_context_blob`, `run`. Two changes only:

- `run()` reads `email_digest_payloads.context_md` and **skips `_create_context_blob` when it
  is present**, inserting the stored text as the space's `context_blobs` row instead. Without
  this, `run()`'s per-job context generation makes step 4's "one Gemini call per issue" false —
  it would be one per watcher. The value is read from the payload row rather than passed as an
  argument because the worker calls processors with only the job dict.
- `latest_retryable_email_digest_job(watch_id)` is redefined against the new schema, and because
  `context_md` is persisted, a retried job needs no regeneration.
- Its input is an archive-fetched issue body rather than an email body.

Module name and the `email_digest` task discriminator are retained (see decisions).

**Enqueue durability:** a Redis push cannot join a SQLite transaction. No outbox is added. The
plan reuses this codebase's existing posture — commit job + payload, then enqueue, and on
enqueue failure mark the job `error` (`src/api/email_webhook.py:143-147` does exactly this
today) so `POST /api/newsletter-digest/{id}/retry` can re-drive it. The gap that posture leaves
— a **crash** between commit and enqueue, leaving a job stuck `pending` that generic recovery
skips because it excludes `email_digest:%` — is closed by §4 step 4's scan, which re-enqueues
payloads whose job has been `pending` past a threshold. That is why an outbox is unnecessary
here: unlike the webhook, a poller already runs periodically and can repair itself.

### 6. First watch = watermark + latest issue only

`POST /api/newsletter-digest` **re-resolves `archive_url` server-side** (see §8), seeds
`publication_issues` from that result, and inserts the watch row with `watched_from` already
set — all in one transaction. There is therefore no window in which the watch is poll-visible
but unseeded, so a concurrent poll cannot fan out the back catalogue to a half-created watcher.

The newest issue is then ingested as an **explicit delivery keyed by `(watch_id, slug)`**, not
as a consequence of the `watched_from` filter. Both timestamps are written in the same
transaction, so `watched_from < first_seen_at` can collapse at clock precision and silently skip
the very issue that is supposed to prove the feature works.

That explicit delivery goes through the **same skip-aware ingestion path** as the poller: an
issue carrying a `skip_reason` is passed over and the next-newest is used. Bypassing the check
here would hand a brand-new watcher the one issue the system has already given up on.

### 7. Delete the email path

`ops/email-worker/` (5 files, 331 lines) · `src/api/email_webhook.py` (149) ·
`src/main.py:15` import + `:178` `include_router` · `src/auth/middleware.py:17`
(`/webhook/email-digest` out of `_OPEN_PATHS`) · `src/config.py:23` (`EMAIL_WEBHOOK_SECRET`) ·
webhook-path tests in `tests/test_email_digest.py` and `tests/test_config.py` · the Cloudflare
catch-all rule and its docs.

One **fix**, not a deletion: `worker.reap_stale_jobs()` (`src/worker.py:352`) still offers a
generic `reprocess:{job_id}` button for stale `processing` rows. Only the dashboard recovery
path special-cases `email_digest:%`, so a stalled digest job currently gets a reprocess button
that would re-drive it as a plain link job against a non-fetchable sentinel URL. The reaper must
suppress generic reprocess notifications for `email_digest:%` and defer to the digest retry path,
matching what `job_recovery.py:27,229` already do. Recovery point pinned in ADR-0060: commit `e0df28f`. Full revert
was considered and rejected — `e0df28f` is 5,147 insertions of which ~4,500 (the entire `web/`
dashboard, the extraction processor, the schema, the redirect resolver) are kept and built on.

### 8. API + web

- `POST /api/newsletter-digest/resolve` → `{query}` ⇒
  `{archive_url, feed_url, issue_path_prefix, fetched_title, recent_issues[]}`.
  **Read-only, creates nothing**, rate-limited per chat.
- `POST /api/newsletter-digest` → `{archive_url, name}` ⇒ **re-resolves `archive_url`
  server-side** to obtain `feed_url`, `issue_path_prefix` and the current issue list, then
  creates or reuses the `publications` row via an **atomic upsert-or-select helper** and creates
  the watch per step 6. Two users adding the same newsletter simultaneously race on
  `archive_url UNIQUE`, so the helper inserts-or-returns the existing row in one statement.
  Metadata is then reconciled rather than frozen: a *missing* `feed_url` / `issue_path_prefix` /
  `fetched_title` is always filled, and an existing one is **replaced when the resolver returns
  a validated value and `last_resolved_at` is older than a cooldown** (stamping
  `last_resolved_at` on write). Fill-only-if-missing would preserve a wrong `feed_url` or
  `issue_path_prefix` forever after a resolver mistake or a publisher restructuring; the
  cooldown is what stops two users adding the same newsletter from ping-ponging its metadata.
  Re-resolving is
  deliberate: the resolve response is not carried in the request and must not be trusted from
  the client. A short-lived resolver token was considered and rejected — it adds cache-expiry
  semantics to save one fetch on a rare action.
- `PUT` edits the watch's `name` only. Candidate list/promote/dismiss and `/retry` unchanged,
  as is the ownership gate (`_get_owned_subscription` → `_get_owned_watch`, same `(id, chat_id)`
  shape).
- Subscribe form: one field → resolve → confirmation card listing recent issue titles → confirm.
- **`Dismiss rest (N)`** on the candidate list. An issue yields ~15 candidates and the real
  interaction is "promote the two worth keeping, clear the remainder", so the button loops the
  existing per-candidate `DELETE`. It needs **one small backend change**, not zero:
  `dismiss_digest_candidate` currently accepts `status IN ('pending','promoting')`
  (`src/database.py:3448`), so a bulk loop over a UI snapshot could dismiss a candidate that
  turned `promoting` in the meantime — flipping it to `dismissed` while its job is being
  created. Bulk dismiss therefore uses a **pending-only** variant (`status = 'pending'`),
  exposed as a flag on the existing endpoint; single-card dismiss keeps today's behaviour.
  A batch *endpoint* is still deliberately not added: it would impose all-or-nothing semantics
  that are wrong here (one candidate failing must not roll back the others) to save round-trips
  that do not matter at this size. The **count goes in the label** as the guard —
  `CONTEXT.md`'s [[Job delete]] entry records a Bookmark import card where one misclick took
  hundreds of links — but no confirm modal, since dismissal is a soft status flip that leaves
  the row in the dedup set.

The invariant is that **the poll loop never runs in the API process**. A bounded, rate-limited,
user-initiated resolver fetch is explicitly allowed.

### 9. Tests

Migration teardown (no orphaned spaces/candidates/legacy jobs) · fresh-`SCHEMA_SQL` vs migrated
schema parity · `newsletter_poll` queue-envelope contract and `_handle_newsletter_poll` dispatch
· first-poll claim on `NULL` columns · poll idempotency across a replayed envelope ·
multi-watcher fan-out (N jobs, 1 fetch, 1 Gemini call) · lease contention between two workers ·
failure backoff advancing `next_poll_after` · lease refusing a not-yet-due publication ·
watch-creation/poll race · first-watch explicit delivery when `watched_from` equals the issue's
`first_seen_at` · duplicate fan-out rolling back job **and** payload together, leaving no orphan
job · retry reading persisted `context_md` without a second Gemini call · issue ordering when
`published_at` is missing or malformed, including the newest-first source reversal · resolver
abuse limits (scheme, private host, probe cap, rate limit) · resolver cache re-validation ·
feed-vs-scrape selection including beehiiv's "200 but an HTML app shell" `/feed` ·
`issue_path_prefix` discovery against captured `/p/` and `/news/` fixtures ·
**crash-recovery: issue rows inserted but fan-out never ran → next poll still delivers** ·
**job committed but never enqueued → next poll re-enqueues the stale pending payload** ·
**Gemini failure still produces candidates, with `context_md` NULL** and **no per-watcher
Gemini fallback** · concurrent `POST` for the same `archive_url` yielding one publication row ·
oversized Jina response rejected before storage · `reap_stale_jobs()` suppressing generic
reprocess for `email_digest:%` · delivery repair after an outage longer than any recency window ·
`Dismiss rest` clearing only `pending` candidates — explicitly **not** a candidate that turned
`promoting` after the UI snapshot — and surviving a partial failure mid-loop · `body_html`
surviving until every live delivery is terminal, and an errored digest still being retryable
afterwards · **`body_html` NOT cleared while a live watch still lacks a payload row**, including
the zero-payload-rows case after a crash · composite FK rejecting a payload whose issue row is
gone · oversized issue marked terminal-skipped without aborting the rest of the run, **and
skipped by first-watch delivery too** · streaming fetch aborting at 4 MB + 1 without
materialising the body · publication metadata refreshed after the cooldown but not ping-ponged
by two concurrent adds.

## Key decisions & tradeoffs

- **`publications` / `publication_issues` are shared across tenants with no `chat_id`.** The
  entire scale-proof claim: a public archive is byte-identical for every viewer, so one fetch
  serves every watcher and polling load scales with distinct publications (~hundreds), not
  users. ADR-0043 rejected a shared-row design for `links` because that row held
  **user-visible content** a tenant's re-scrape could mutate; these rows hold fetch bookkeeping
  no tenant writes — which is why the display name moved to `newsletter_watches.name` and the
  scraped one is `fetched_title`.
  **Amendment:** `publication_issues.body_html` means a shared row now also holds *transient
  fetched publisher content*, weakening the original "bookkeeping only" phrasing. It still
  clears the ADR-0043 bar for a different reason: the body is publisher-authored, byte-identical
  for every viewer, written only by the poller, never edited by a tenant, and cleared once
  delivered. What ADR-0043 forbade was a shared row a tenant's own action could mutate under
  another tenant — which this is not. The alternative, copying a several-hundred-KB body into
  every watcher's payload row, was rejected on cost.
- **Feed where available, archive scrape otherwise — one code path, no XML parser.** 1 of 3 real
  publications has a feed. Feed-only leaves the beehiiv majority unreachable; scrape-only throws
  away the cheapest and most complete source where it exists. Both are fetched through the same
  Jina HTML path and validated by the same rule (≥2 distinct issue links), because Jina renders
  a feed into clean HTML — verified at 100 permalinks for AlphaSignal.
- **Issue URL prefix is learned, not hardcoded.** `/p/` (beehiiv) vs `/news/` (AlphaSignal) —
  discovered by grouping same-origin links at resolve time and stored per publication.
- **Jina fetched with `X-Return-Format: html`** (verified) so `extract_digest_links` is reused
  unchanged, rather than maintaining a second Markdown parser.
- **The `email_digest:` job-URL sentinel is deliberately kept**, despite email being gone. It
  is load-bearing in 8 production sites — `src/api/jobs.py:82,100,338`,
  `src/services/job_recovery.py:27,229`, `src/database.py:3133,3154,3460` — excluding receipt
  jobs from the Feed and from generic recovery retry (the `content_type='link'` mis-retry trap
  the superseded plan documented). Renaming buys nothing functional and touches 8 call sites plus
  test assertions. (The "and it would need a data migration" leg of this argument no longer
  applies — legacy receipt rows are now deleted outright.) A comment records why the name lies.
- **Issue identity is `(publication_id, slug)`**; mirrors are collapsed by publisher-advertised
  canonical URL at resolve time, not by a `publication_aliases` table. No collision has been
  observed; add the table if a real case appears.
- **No durable outbox.** Reuse the existing commit-then-enqueue-then-mark-error posture plus the
  existing retry endpoint, rather than new infrastructure for one task.

## Risks / open questions

- **Feed and archive granularity differ.** AlphaSignal's feed entries are individual news
  stories (`/news/<slug>`), while Sloth Bytes' are whole issues (`/p/<slug>`) containing ~15
  links. So "one issue → many candidates" holds for beehiiv but degenerates to "one story → one
  candidate" for AlphaSignal. The mechanics work either way; whether the AlphaSignal shape is
  *useful* is unvalidated.
- **Jina rate limits and cost.** ~1,800 fetches/day at 300 publications, flat in user count,
  past the free tier. `poll_failures` now drives backoff, but there is still no user-visible
  "this newsletter stopped updating" signal after repeated failures.
- **Archive pagination.** Archive roots show ~6 issues behind "Load more". `publication_issues`
  makes replay safe but not recovery — a scrape-only publication outpacing its visible window
  between polls still loses issues silently. Largely mitigated where a feed exists: AlphaSignal's
  carries 100 entries against its archive page's 6.
- **Publication orphaning.** Nothing deletes a `publications` row when its last watch goes; the
  poll query skips watchless rows, so they are inert but accumulate.
- **Slug is publisher-controlled** — an edited slug reads as a new issue and re-ingests.
- **Fan-out still runs candidate extraction and OG fetches per watcher per issue.** The archive
  fetch, issue fetch and Gemini call are shared; extraction is not.
- **Canonical-URL collapsing depends on publishers setting it correctly**, which not all do.

## Out of scope

- Gmail OAuth ingestion for email-only newsletters — recorded in ADR-0060 as the fallback, but
  taking it reverses the standing no-restricted-scope decision in `docs/ops/oauth-verification.md`.
- Back-catalogue import; adaptive poll cadence.
- **Per-card multi-select checkboxes, and batch promotion.** `Dismiss rest` covers the observed
  interaction; a selection toolbar is only worth building if dismissing a *subset* rather than
  the remainder turns out to be common. Batch promote is rejected outright rather than deferred:
  each promotion spends real pipeline work, so a "promote all" button is auto-processing with
  one extra click of ceremony — the exact line ADR-0051 and this feature's per-candidate
  judgement rule exist to hold.
- Reusing the inbound-email channel for intake (rejected in ADR-0060; recovery at `e0df28f`).
- Fixing the pre-existing `bookmarks` mis-retry exposure the superseded plan flagged.
