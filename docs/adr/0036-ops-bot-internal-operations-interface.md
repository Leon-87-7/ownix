---
adr: "0036"
title: Ops bot as the internal operations interface
status: accepted
date: 2026-07-16
---

## Context

Ownix currently uses one Telegram bot for two different jobs:

1. User-facing product interaction: login identity, URL/photo submission, job
   status, and result delivery.
2. Internal operations: invite approvals, user inspection, production alerts,
   and later deploy notifications.

That coupling creates noise and risk. During local full-stack testing, fake
`Dev login` users produced real approval cards in the same Telegram surface used
for normal Ownix work. In production, invite approval is also an operations
decision, not a user-facing product interaction.

Leon already has a separate Telegram bot, `TTTask_bot` / `@photo2urlBot`, that
can own internal operations. We need a clear boundary so user interactions stay
on the Ownix bot while operational control moves to the Ops bot.

## Decision

### 1. `TTTask_bot` is the Ops bot

`TTTask_bot` / `@photo2urlBot` becomes the internal Ops bot.

The Ownix bot remains user-facing:

- Telegram Login Widget identity.
- Telegram HMAC validation.
- User URL/photo submissions.
- Job status and result delivery.
- User-facing approval or block outcome messages.

The Ops bot owns internal operations:

- Invite approval/block cards.
- Pending-user inspection.
- User and email lists.
- Domain-scoped batch approval.
- Future production alerts.
- Future deploy notifications.

The Ops bot must never become visible as a user-facing product surface. If an
admin action needs to tell a user something, the Ownix bot sends that external
message.

### 2. The two bots use separate credentials and webhook paths

The user-facing bot keeps the existing credentials and webhook path:

```txt
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
/webhook
```

The Ops bot uses separate credentials and its own webhook path:

```txt
OPS_BOT_TOKEN
OPS_WEBHOOK_SECRET
/webhook/ops
```

Production uses:

```txt
OPS_WEBHOOK_URL=https://api.leondev.xyz/webhook/ops
```

The backend registers the Ops webhook at startup only when all required Ops
webhook settings are present:

- `OPS_BOT_TOKEN`
- `OPS_WEBHOOK_SECRET`
- `OPS_WEBHOOK_URL`

Startup logs either `ops_webhook_registered` or a clear missing-config warning.
The Ownix webhook registration behavior remains independent.

### 3. Ops access is allowlist based and split by authority

Ops access is controlled by explicit chat-id allowlists:

```txt
OPS_CHAT_IDS
OPS_ADMIN_CHAT_IDS
OPS_DEV_CHAT_IDS
```

`OPS_CHAT_IDS` grants read-only operations:

- Receive non-mutating operational notices.
- Run read-only commands such as `/pending`, `/users`, and `/status`.

`OPS_ADMIN_CHAT_IDS` grants mutating operations:

- Approve or block users.
- Confirm domain-scoped batch approval.
- Future production-control actions such as retries, queue cleanup, or deploy
  triggers.

Invite approval/block keyboards are sent only to `OPS_ADMIN_CHAT_IDS`. A user in
`OPS_CHAT_IDS` may inspect pending users but does not receive decision buttons.

`OPS_DEV_CHAT_IDS` is for local end-to-end testing noise. If unset, dev
notifications fall back to `OPS_ADMIN_CHAT_IDS`.

Both production allowlists can initially contain only Leon's chat id, but the
split keeps "can see ops" separate from "can change production."

### 4. Invite approval moves through the Ops bot

When a user signs in and provides an approval email, the backend creates or
updates that user as `pending` and sends approval/block cards through the Ops
bot.

The approval card includes enough context for an admin decision:

- name
- email
- username when known
- callback buttons for approve and block

When an admin taps a decision button:

1. `/webhook/ops` validates `OPS_WEBHOOK_SECRET`.
2. The acting chat id is checked against `OPS_ADMIN_CHAT_IDS`.
3. The existing `users.status` row moves to `approved` or `blocked`.
4. The Ops bot confirms the internal action.
5. The Ownix bot sends the affected user any external outcome message, such as
   an approval notice and app link.

Unauthorized callback taps never change status.

### 5. First Ops command slice

The first Ops bot implementation includes these read-only commands:

```txt
/pending
/users
/users pending
/users approved
/users blocked
/users email <domain>
/users email all
```

`/users` defaults to the 20 most recent users, newest first.

`/users email <domain>` lists captured emails for one domain.

`/users email all` lists every captured email regardless of domain so
custom-domain users are not missed.

User-list results render directly in chat for 20 or fewer rows. Larger result
sets are sent as a CSV document.

### 6. Batch approval is domain scoped and confirmed

The Ops bot supports a batch approval command:

```txt
/approve_pending <email-domain>
```

The command:

1. Matches pending users whose email ends with the requested domain.
2. Previews the count and matching users.
3. Requires an inline confirmation from `OPS_ADMIN_CHAT_IDS`.
4. Updates statuses only after confirmation.

There is no naked `/approve_all` or equivalent production command.

### 7. Dev login stays quiet by default

`DEV_LOGIN_ENABLED=true` remains a local-only dashboard auth shortcut. It creates
a fake pending session identity for testing the invite flow without the Telegram
Login Widget.

By default, Dev login stays local and quiet:

- no real Ops bot notification
- no public tunnel
- no production webhook mutation

Full local end-to-end Ops bot testing is opt-in:

```txt
OPS_DEV_NOTIFICATIONS=true
OPS_DEV_CHAT_IDS=<chat ids>
```

When enabled, dev approval cards are sent through the Ops bot and clearly marked
as local/dev so they cannot be confused with production approvals.

Local dev also keeps a backend-only approval fallback, enabled only with
`DEV_LOGIN_ENABLED=true`, so pending-to-approved dashboard testing does not
require exposing localhost to Telegram.

### 8. Ngrok is explicit for local callback testing

Telegram cannot call a local `/webhook/ops` URL unless the local API is publicly
reachable. For true callback testing, developers use an explicit ngrok dev-e2e
helper.

The helper may:

- expose local port `8000`
- discover the public ngrok HTTPS URL
- write or update only the backend `.env.local` override:

```txt
OPS_WEBHOOK_URL=https://<ngrok-host>/webhook/ops
OPS_DEV_NOTIFICATIONS=true
```

`uvicorn src.main:app --reload` must never open a public tunnel as a side
effect. Opening a public webhook tunnel is an intentional developer action.

## Consequences

- User-facing Ownix Telegram usage no longer collides with internal operational
  approval traffic.
- Invite approvals become a real production operations workflow instead of a
  side effect of the user bot.
- Ops read visibility and production mutation authority can diverge safely.
- The system can add production alerts, deploy notifications, and richer Ops
  commands without expanding the user-facing bot surface.
- Local development has a safe quiet path by default and a deliberate full
  end-to-end path when needed.
- The deployment now has more Telegram configuration to manage. Startup logging
  and `.env.example` must make missing Ops settings obvious.
- Tests should cover allowlist parsing, Ops webhook secret validation,
  authorized and unauthorized callbacks, command authorization, CSV threshold
  behavior, quiet Dev login, and explicit dev notification mode.

## Considered alternatives

- **Keep using the Ownix bot for approvals.** Rejected: operational decisions
  collide with normal product usage, and local Dev login can generate noisy fake
  production-looking cards.
- **Send approval cards with the Ops bot but keep callbacks on `/webhook`.**
  Rejected: Telegram sends callback queries to the bot that owns the message, so
  Ops bot cards need an Ops bot webhook path.
- **Use one shared webhook secret for both bots.** Rejected: leaked or
  misconfigured Ops webhook credentials should not authorize the user-facing
  bot path, and vice versa.
- **Use only one ops allowlist.** Rejected: alert visibility and production
  mutation authority are different privileges.
- **Add `/approve_all`.** Rejected: invite approval is intentionally default
  deny, and batch mutation needs a narrow explicit selector plus confirmation.
- **Start ngrok automatically with uvicorn.** Rejected: a public tunnel into a
  local backend should be an intentional development action, not an incidental
  backend startup side effect.

