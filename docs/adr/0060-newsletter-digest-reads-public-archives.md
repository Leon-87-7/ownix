---
adr: "0060"
title: Newsletter digest reads public archives, not email
status: accepted
date: 2026-09-06
---

## Context

#607 shipped the newsletter digest as an **inbound-mail** pipeline: each subscription
generates a unique alias (`newsletter_subscriptions.alias_local_part TEXT NOT NULL UNIQUE`,
`src/database.py:307`), Cloudflare Email Routing catch-alls `leondev.xyz` into a Worker
(`ops/email-worker/src/index.ts`), and the Worker posts to `/webhook/email-digest`
(`src/api/email_webhook.py`), which drops any message whose `from` does not match the
subscription's registered `sender_email` (`:83`).

It could not be onboarded. Getting a newsletter's mail to an alias requires either:

1. **Mail-client forwarding.** Gmail sends its verification code *to the alias*, from
   `forwarding-noreply@google.com` — which fails the sender check at `:89` and is silently
   dropped (`{"ok": true}`, no candidate, no visibility). The user cannot see the code, so
   forwarding can never be verified.
2. **Signing up with the alias directly.** Rejected by the newsletter's signup validator —
   `leondev.xyz` is a catch-all domain, which third-party email-verification services
   routinely refuse.

Every proposed workaround required a **human operating the Cloudflare zone per alias**
(temporarily routing one alias to a real mailbox to catch the confirmation), which does not
survive a second user, let alone 500. Aliases are also **per subscription**, not per user,
so the bootstrap cost multiplies by users × subscriptions.

Investigating the four newsletters actually read produced the decisive evidence:

| Newsletter   | Sender                        | Public archive                         | Issue URL shape | RSS | Jina |
| ------------ | ----------------------------- | -------------------------------------- | --------------- | --- | ---- |
| AlphaSignal  | `news@alphasignal.ai`         | `alphasignal.ai` (403s a server fetch) | `/news/<slug>`  | ✅ `feed.xml` + `atom.xml` | ✅ |
| Sloth Bytes  | `slothbytes@tx2.beehiiv.com`  | `www.slothbytes.dev` + beehiiv mirror  | `/p/<slug>`     | ✗ | ✅ |
| Import React | `importreact@mail.beehiiv.com`| `importreact.beehiiv.com`              | `/p/<slug>`     | ✗ | ✅ |

Every issue is public and **complete** — a fetched Sloth Bytes issue carried all sections
and every outbound link with UTM params intact, i.e. exactly the payload
`src/processors/email_digest.py` extracts from an email body.

**Feed coverage is partial, not absent.** An initial reading recorded no feeds anywhere; that
was a false negative caused by AlphaSignal's 403 to raw server fetches, which masked the
`feed.xml`/`atom.xml` links its own pages advertise. Corrected 2026-09-07 during Codex plan
review: AlphaSignal publishes a working feed, while both beehiiv publications genuinely have
none (raw `404`, and via Jina the beehiiv HTML app shell rather than XML — beehiiv makes feeds
opt-in and neither publisher enabled it). So a feed is the **preferred** ingestion path where
one exists and the archive scrape is the fallback, rather than feeds being useless.

Raw HTTP is insufficient either way — AlphaSignal 403s any server fetch and beehiiv archives
render client-side, so raw HTML lists no issues at all — but [[Jina Reader]]
(`src/services/jina.py`, already a dependency) reads all of them, including with
`X-Return-Format: html`, which returns real parseable HTML (verified: 666 KB with intact
`<a href="/p/…">` anchors).

**Issue URL shape is publisher-specific** (`/p/` vs `/news/`), so it is discovered at resolve
time and stored per publication, never hardcoded.

## Decision

The newsletter digest **follows a newsletter's public web presence** — its feed where one
exists, its archive page otherwise — and polls it. Ownix is not a subscriber and needs no
mailbox, alias, forwarding, or inbound mail. See [[Watched newsletter]], [[Issue]] and
[[Issue watermark]] in `CONTEXT.md`.

- **Identity is the archive URL**, replacing `sender_email` + `alias_local_part`. The
  subscribe field accepts whatever the user already has — sender address, archive root, or
  the "view in browser" link off any issue (`strip query → strip issue path → root`) — and
  resolution is confirmed by rendering the latest issue titles back, so a mistake is visible
  at once instead of as mail that never arrives.
- **An [[Issue]] is identified by its slug, not its URL.** beehiiv serves the same issue
  from both the publisher's custom domain and the `*.beehiiv.com` mirror
  (`www.slothbytes.dev/p/next-js-16-3` and `slothbytes.beehiiv.com/p/next-js-16-3` both
  200), so a URL key double-ingests. `receipt_key()`'s email-shaped identity
  (`alias_local_part` + `messageId`, `email_webhook.py:52`) becomes
  `(publication, slug)`; the dedup mechanism itself is unchanged. Mirrors are collapsed
  before a publication row exists, using the publisher's own `<link rel="canonical">`.
- **Polling is fixed at 4 hours**, no adaptive per-newsletter cadence.
- **The poll unit is the publication, not the subscriber.** Three tables:
  - `publications (id, archive_url UNIQUE, feed_url, issue_path_prefix, fetched_title,
    last_successful_poll_at, next_poll_after, poll_lease_until, poll_failures)` — shared
    across tenants. The lease serialises concurrent polls; `next_poll_after` carries the
    schedule and the failure backoff.
  - `publication_issues (publication_id, slug, url, title, published_at, source_order,
    first_seen_at, body_html, PK(publication_id, slug))` — shared. The seen-set, **and the
    single copy of each fetched issue body**, cleared once every watcher has been served.
  - `newsletter_watches (id, chat_id, publication_id, space_id, name, watched_from,
    UNIQUE(chat_id, publication_id))` — per tenant. `watched_from` is a timestamp, not a
    slug: slugs are publisher strings with no chronological order.

  A 15-minute scheduler tick in `src/main.py` enqueues one `newsletter_poll` task per due
  publication. The worker fetches once, records issues, then computes outstanding work as
  **missing `(watch_id, slug)` deliveries** — not as newly-discovered issues, which would
  lose an issue permanently if a run crashed between recording and fan-out — and fans out to
  each watcher's space. The per-issue Gemini editorial blob is generated **once** and
  persisted, never once per watcher.
- **First watch records an [[Issue watermark]] and ingests only the latest issue**, as an
  explicit delivery rather than a consequence of the `watched_from` filter. The back
  catalogue is not imported.

## Considered options

- **Gmail API via the existing per-tenant OAuth** (`build_google_credentials(scopes,
  chat_id=…)`, `src/services/google_auth.py:74`). Genuinely seamless — the user consents
  once during a Google connect they already perform for Drive, and subscribing becomes
  typing a sender address. Rejected because `gmail.readonly` is a **restricted** scope
  requiring Google app verification plus an annual third-party CASA security assessment
  before exceeding the 100-user testing cap, and it locks the feature to Gmail. This is not
  a fresh judgement: `docs/ops/oauth-verification.md` already records the standing decision
  to carry "only two [scopes], deliberately no restricted scope (would trigger a paid CASA
  assessment)", and the superseded #607 plan rejected Gmail polling on the same grounds
  (`docs/plans/2026-09-05-email-digest-inbound-alias-superseded.md`, assumption 2). Remains
  the fallback if email-only newsletters (no public archive, or subscriber-gated issues)
  turn out to matter — but taking it means reversing that standing decision.
- **RSS as the *sole* mechanism.** Rejected on coverage: only 1 of the 3 real publications
  publishes a feed, so a feed-only design leaves the beehiiv majority unreachable. Feeds are
  **preferred where present** — cheaper, stable, and they carry titles, dates and permalinks
  without HTML parsing or per-publisher URL guessing — with the archive scrape as the
  fallback. (An earlier draft rejected feeds outright on a "0 of 4" reading that was a false
  negative; see the evidence note above.)
- **Adaptive per-newsletter poll cadence**, learned from observed publication gaps.
  Rejected: Sloth Bytes' real gaps run 2–14 days with no rhythm, so a learned interval
  either floors near the baseline and saves nothing, or spaces toward the median and misses
  the fast issues — while adding a stored per-newsletter model and a staleness bug that only
  appears when a publisher changes schedule.
- **One table keyed `(chat_id, archive_url)`**, polled per row. Rejected: 500 users × 5
  newsletters is 2,500 fetches per cycle against perhaps 300 distinct publications, so load
  would scale with the user table — the exact property this ADR exists to avoid.
- **A short "any sender accepted" grace window** after subscription creation, to let the
  first forwarding-confirmation email through. Moot once inbound mail leaves the system.

## Consequences

- `ops/email-worker/`, `src/api/email_webhook.py`, the Cloudflare catch-all rule, the
  generated alias, and the sender check are all deleted. Email leaves the trust boundary
  entirely: there is no inbound-mail attack surface and no shared secret to rotate.
- The product changes shape. "Digest my inbox" becomes "follow these publications" — a user
  can watch a newsletter they never subscribed to, and conversely, anything with no public
  archive or with subscriber-gated issues becomes invisible. This is the accepted cost.
- An issue is visible only after the next poll, so up to 4 hours after publication. Email
  was instant.
- **Shared `publications` / `publication_issues` rows are not a reversal of ADR-0043.** That
  ADR rejected "one canonical row + membership table" for `links` because the shared row held
  **user-visible content a tenant's own action could mutate** under another tenant. These
  rows are not that: they are written **only by the poller**, never by a tenant, and
  everything a user sees stays per-tenant — display name, watch, space, candidates — with
  ingested links still landing under `(chat_id, url)` as the [[Second Brain]] requires.
  ADR-0043 already reuses a first tenant's scraped fields and embedding to avoid duplicate
  *work*, which is the same instinct.

  One honest qualification: `publication_issues.body_html` means a shared row holds
  **transient publisher content**, not purely bookkeeping as an earlier draft of this ADR
  claimed. It still clears the bar — the body is publisher-authored, byte-identical for every
  viewer, poller-written, tenant-immutable, and cleared once delivered — but the distinction
  being relied on is *immutability by tenants*, not *absence of content*. The alternative,
  copying a several-hundred-KB body into each watcher's payload row, was rejected on cost:
  one issue × 500 watchers would push hundreds of MB through SQLite, retained on failure.
- Existing `newsletter_subscriptions` rows are **dropped, not migrated**. None ever
  successfully ingested an issue — that failure is why this ADR exists — so a migration that
  probes the network to rescue rows with no data behind them costs more than re-adding a
  handful of newsletters by hand. The inbound path is deleted rather than left dormant
  behind a flag: an untested webhook with a live shared secret is attack surface, and the
  Gmail-OAuth option above is a better fallback than resurrecting aliases.
- **Reusing the inbound channel for other work was considered and rejected.** The reusable
  asset is the channel itself — authenticated inbound email → parsed JSON → HTTP with
  per-address routing, dedup and size/rate caps, 204 lines across
  `ops/email-worker/src/index.ts` (55) and `src/api/email_webhook.py` (149). The one real
  candidate was **email as a fourth intake channel** into the already channel-neutral
  `src/intake/router.py` (Telegram, dashboard, extension today): forward an article or PDF
  to an Ownix address and it becomes a job. That use case notably does *not* hit the walls
  above — the verification wall applies only to Gmail's *automatic forwarding rule*, while
  manually forwarding a message reaches any address instantly, and no signup validator is
  ever involved. It was still rejected: Telegram already serves "send me a thing from
  anywhere" more easily, nobody has requested email intake, and keeping it means carrying a
  live public webhook, a Cloudflare catch-all and a rotating shared secret for a path no
  test exercises. **Recovery point: commit `e0df28f`** — reviving those 204 lines is
  cheaper than maintaining them unused. If email intake is ever wanted, repoint the webhook
  at the intake router and drop the alias/subscription lookup.
- Each [[Issue]] remains a `jobs` row, reusing the existing [[Status FSM]], task envelope,
  retry endpoint and candidate flow. The dashboard route and `web/lib/newsletter-digest.ts`
  are largely unchanged; the subscribe form and the ingestion source are what move.
