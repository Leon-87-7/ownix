---
adr: "0047"
title: Intake follow-ups ride the action envelope, not a pending chat_state row
status: accepted
date: 2026-08-06
---

## Context

The intake makeover (grill, 2026-08-06) added the first intake interaction that
needs a *second* step from the user. A [[Tag token]] naming a tag that does not
exist — `<url> #GoTo` where no `GoTo` tag is in the caller's vocabulary — creates
the job immediately and then has to ask: create the tag? The agreed flow is
reject-and-offer → confirm → an inline `TagForm` rendered in the thread → Save →
the console confirms.

The obvious way to hold "we are waiting on an answer about tag `GoTo` for job
`X`" is the mechanism this codebase already has for waiting on user input:
`chat_state`, wrapped by `src/intake/state.py`. Three properties make it the
wrong tool here.

1. **It is one slot per owner, deliberately.** `state.py`'s module docstring
   states the semantic outright — `chat_state` is keyed by `chat_id` alone, not
   by channel, so "one user, two channels" is "one owner key, two transports for
   a single pending flow," and a second arm from either channel intentionally
   replaces the first. That is correct for the flows it was built for
   ([[PRD intent slot]] and freestyle) which are deliberate, minutes-long,
   one-at-a-time windows. It is wrong for a yes/no confirmation: arming a
   tag-confirm would silently destroy a pending PRD intent window, and a
   `/freestyle` fired from Telegram would silently destroy the tag offer sitting
   on the user's screen. Both are common actions on this page.
2. **It has nowhere to put the payload.** `database.set_chat_state` takes
   `(chat_id, mode, job_id, expires_minutes)`. A tag confirmation needs the tag
   *name*, which has no column. Adding one widens a table shared with Telegram
   for a dashboard-shaped need.
3. **It expires.** `PENDING_MODES` (`src/intake/state.py:30`) is a closed tuple
   and `set_state` raises `ValueError` outside it, so a third mode is a code
   change; and every mode carries a TTL (default 10 minutes) reaped by
   `reap_expired()`. A ten-minute clock on "do you want this tag?" means the
   offer dies while still rendered as live.

Meanwhile `IntakeAction` already carries everything the flow needs, and the
`POST /api/intake/action` endpoint already makes it safe.

## Decision

**Interactive follow-ups on the [[Intake console]] are carried by
`IntakeResponse.actions`, and the action's `payload` is the flow state. No
pending `chat_state` mode is added for them.**

- `IntakeAction.payload` is `dict[str, Any]` (`src/intake/models.py:59`), so the
  offer round-trips its own context — `{"job_id": ..., "tag_name": "GoTo"}` —
  with no server-side row.
- `src/api/intake.py` builds the action message with a deterministic
  `idempotency_key` of `f"action:{action_id}"`, so the router's existing
  per-`(actor, idempotency_key)` cache suppresses most double-fires for free.
  The correctness guarantee itself is the handler's own normalized lookup
  (e.g. `_create_tag`'s tag-name normalization before create, documented in
  `src/intake/actions.py`) — the cache is duplicate suppression on top, not
  the thing a follow-up handler may rely on for data safety, since cache
  entries are not retained indefinitely.
- New follow-up kinds are one branch each in `actions.apply()`, beside the
  existing `cancel_pending` and `retry_job`.
- Because `IntakeAction` is the channel-neutral replacement for a Telegram
  inline keyboard, the same follow-up renders as a button in Telegram and as an
  inline component on the dashboard, with no per-channel state.

A typed confirmation (`y`) is still offered as a **client-side keybinding that
fires the newest pending action** — presentation over the same envelope, never
a server round-trip that arms a mode.

`chat_state` remains the right mechanism for what it already holds: deliberate,
long-lived, cross-channel flows that genuinely should be single-slot and should
expire.

## Consequences

- The offer stays valid exactly as long as its card is on screen. Since the
  intake thread persists in `sessionStorage` and not on the server, "how long is
  the offer good for" needs no answer — it is the lifetime of the tab.
- Nothing about a follow-up is visible to another channel. A tag offer raised on
  the dashboard cannot be answered from Telegram, because there is no shared row
  to observe. Accepted: cross-channel resumption of a yes/no is not a real need,
  and buying it costs the collision described above.
- The [[PRD intent slot]] / freestyle single-slot semantic is preserved
  untouched — no new mode competes for it.
- The `IntakeAction.payload` contract becomes load-bearing. It is already
  covered by the models' stability rules (fields are added, never repurposed;
  every message carries `schema_version`), and it must stay small enough to
  survive a Telegram `callback_data` round-trip if a follow-up is ever offered
  there. `InlineKeyboardButton.callback_data` is capped at 64 **bytes**, not
  characters — at the MTProto layer `keyboardButtonCallback` is
  `text:string data:bytes` — so a tag name in Cyrillic or CJK consumes 2–4 bytes
  per character and a payload that looks short can still overflow. The
  established escape hatch is to send a short opaque key and hold the real
  payload server-side; note that doing so reintroduces exactly the server state
  this ADR avoids, so it is a Telegram-adapter concern, not a change to the
  contract. Verified against the Bot API docs 2026-08-06.

## Alternatives considered

- **A third `awaiting_*` mode.** Rejected for the three reasons above. The
  collision with PRD intent is the disqualifying one.
- **Per-flow pending state** (`chat_state` keyed by `(chat_id, mode)` rather
  than `chat_id`). This is the honest version of the pending-row approach and
  would fix the collision, but it changes a table Telegram depends on and
  re-opens the last-write-wins semantic that `state.py` deliberately chose. If a
  future flow genuinely needs server-side resumability across channels, that
  migration deserves its own ADR rather than arriving as a side effect of tag
  creation.
- **Silent auto-create, no follow-up at all.** Cheapest, and rejected on domain
  grounds: [[Link tag]] records that tags render as name-less color dots, so
  every silently created tag taking the schema default `#8b5cf6`
  (`src/database.py:202`) yields visually identical pills and defeats the tag
  UI's identification scheme.
