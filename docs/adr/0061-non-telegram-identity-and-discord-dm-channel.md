---
adr: "0061"
title: Non-Telegram identity (GitHub/Google/email) and Discord as a DM-only, pairing-only channel
status: accepted
date: 2026-09-10
---

## Context

ADR-0031 made vig invite-only but never gave anyone a way *in* except the
Telegram Login Widget/Mini App — `users` keyed by `tg_id`, `chat_id == tg_id`
for private chats. Real feedback from a prospective user: he is not a
Telegram user and won't become one, and named GitHub and Google (in that
order) as what he actually uses to log in.
`docs/plans/2026-08-03-ownix-intake-channels-extension-share.md` already
sketched the target shape (`users` + `user_identities` + `intake_channels`,
provider-based) as its Phase 9/10, but left open which providers ship first
(its Open Question #6) and never resolved Phase 9's depth.

Separately, that plan's own submission-channel work — dashboard `/intake`,
PWA share target, Chrome extension with pairing-code auth — had already
shipped by the time of this grill, so "give my friend an alternative
submission channel" turned out to already be solved for anyone who can get
*into* a session, with one exception: iOS. Apple's Safari does not let an
installed PWA register as a system share-sheet target, and a native wrapper
app is an explicit Non-Goal of that plan. Telegram's native app is the only
thing today that shows up in iOS's share sheet. Discord's native app does
too — which is why it re-enters scope here, not as a login method, but
specifically to replicate that one capability.

## Decision

**Identity ships as a narrow slice of the plan's Phase 9, not the full
cutover.** Add one small additive table recording `(provider, subject,
owner_id, verified)` — no migration of `jobs`/`tags`/`spaces`/etc. off
`chat_id`. A Tenant onboarded through a non-Telegram provider gets a
synthetic negative-range integer minted at signup, stored in `users.tg_id`
alongside real Telegram tg_ids — every existing `chat_id`-scoped feature
keeps working unmodified. v1 providers: GitHub OAuth, Google OAuth
(**login-only** — see below), and an email magic-link reusing
`src/auth/session.py`'s existing single-use `mint_handoff`/`redeem_handoff`
token pattern, sent via the SMTP infra `src/services/email.py` already has.
The session dict keeps its existing Telegram-shaped field names
(`first_name`/`username`/`photo_url`); each provider maps its own fields
into them rather than growing new ones. The invite gate (ADR-0031) applies
identically regardless of provider; a provider-verified email auto-fills
`users.email`, skipping the one-time in-app ask.

**Cross-provider accounts auto-merge on verified email only.** If a new
login's email exactly matches an existing Tenant's `users.email` *and* the
provider marks it verified (GitHub `verified:true`, Google
`email_verified:true`; magic-link is verified by construction — receiving
the link proves the address), the new identity link attaches to that
existing owner id instead of minting a second account. An unverified email
never merges — it becomes a new Tenant instead. A merge inherits the
existing account's `status`; it never re-fires Operator approval, since no
new Tenant was created. Concurrent signups are race-guarded by a
case-insensitive unique constraint on `users.email` plus an
upsert-in-one-transaction lookup — the same shape the plan doc already
prescribes for channel resolution — reusing `normalize_email()`.

**Discord ships as a DM-only, pairing-only submission channel — not an
identity provider.** Verified against Discord's own API docs
(`discord-api-docs`, via context7): Discord has no webhook for incoming
messages; `MESSAGE_CREATE` (including DMs) only arrives over a persistent
Gateway WebSocket connection. DM content is delivered without the privileged
`MESSAGE_CONTENT` intent (the docs carve out "DMs it receives" as always
populated), so staying DM-only sidesteps Discord's app-verification review
entirely. One Gateway connection serves the whole bot — not one per user —
and is held open inside the existing `worker.py` process, which already
runs the one other permanent loop in the system (Redis BRPOP + reapers),
rather than a fourth `docker-compose` service. Because Discord's API never
discloses a DM sender's email, a bare DM can never clear the verified-email
bar every other provider clears, so it can never create a Tenant on its own:
an already-signed-up Tenant requests a one-time pairing code from the
dashboard (reusing the Chrome extension's existing pairing-code pattern) and
DMs it to the bot to link their Discord snowflake to their owner id. A
paired DM is routed through the exact same `IntakeMessage`/`IntakeResponse`
contract Telegram already uses (`src/channels/discord/adapter.py`, mirroring
`src/channels/telegram/adapter.py`), so a paired Tenant gets full command
parity, not just URL forwarding. No server/guild channels in v1.

## Considered and rejected

- **Full Phase 9 cutover now** (new `users.id` PK, dual-write, backfill every
  `chat_id`-owned table): rejected for this round — it blocks the actual ask
  (a friend can sign in without Telegram) behind a repo-wide ownership
  migration nobody needs yet.
- **Renaming session fields to the plan's `display_name` shape now**:
  rejected — scope creep on a slice that deliberately isn't doing the real
  migration; the rename belongs with the eventual real Phase 9.
- **Auto-merge on any email match, verified or not**: rejected — an
  unverified email is only as trustworthy as "did the provider let anyone
  type this in," which is an account-takeover vector (attacker adds a
  victim's email to their own GitHub profile, then "merges" into the
  victim's Ownix data).
- **A DM to the bot creating a new Tenant outright**, matching how Telegram
  works today: rejected — Discord discloses no email at DM time, so this
  would let an unverifiable channel create trusted accounts under a
  strictly weaker bar than GitHub/Google/magic-link have to clear.
- **A standalone fourth service for the Discord Gateway connection**:
  rejected as disproportionate infrastructure — `worker.py` already holds
  one permanent connection-shaped loop; one more socket belongs there, not
  in a new deploy target.
- **Guild/server Discord support**: rejected for v1 — nobody asked for it,
  and it's the one thing that would force the privileged `MESSAGE_CONTENT`
  review the DM-only path currently avoids.

## Consequences

- `users.tg_id` now means "owner id," not "Telegram id" — a historical
  column name that no longer promises what it says. Real Phase 9b is what
  finally removes the ambiguity; until then this is a documented misnomer
  (see CONTEXT.md's [[Owner id]]).
- ADR-0030's "Identity first, Google second" ordering was always scoped to
  the Drive/Sheets **export** grant, not to Google interactions in general —
  a future Google **login** is a fully separate OAuth client/scope/callback.
  ADR-0030 gets a clarifying addendum to that effect.
- ADR-0031's "Email verification (confirm link): rejected — no SMTP infra"
  rationale is stale — `src/services/email.py` already sends transactional
  mail. The invite-gate *policy* decision in that ADR (default-deny,
  Operator approval) is unaffected; only the infra premise behind that one
  rejected alternative changed. ADR-0031 gets a clarifying addendum.
- `docs/plans/2026-08-03-ownix-intake-channels-extension-share.md`'s Phase
  9/10 sections, Non-Goals, and Open Question #6 are updated to point at
  this ADR instead of staying open.
