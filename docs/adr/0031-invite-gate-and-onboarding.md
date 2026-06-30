---
adr: "0031"
title: Invite-only access gate + one-time email onboarding
status: accepted
date: 2026-06-29
---

## Context

vig has no access control. The Telegram webhook processes a URL from any chat_id
(only article-*domain* allowlists exist, not a *user* allowlist), and the
dashboard mints a session for any HMAC-valid Telegram login (`src/api/auth.py`).
Anyone who finds the bot can run the pipeline today.

Launching to a handful of LinkedIn contacts needs two things the codebase lacks:
control over **who** is in (an allowlist), and a way to **reach** them outside
Telegram (an email). ADR-0030's `OPERATOR_CHAT_ID` introduces an
operator/admin identity this gate reuses as the approver — so this work depends
on the export gate (#208) landing first.

## Decision

**Approve-in (default-deny).** A new chat_id can do nothing until the Operator
approves it. Reuse the existing `users` table (keyed by `tg_id`; for private
chats `tg_id == chat_id`, so it is already the [[Tenant]] identity) plus two new
columns: `email TEXT` and `status TEXT` (`pending` | `approved` | `blocked`).

- **One email, one ask, shared across surfaces.** Email is captured once, keyed
  on `tg_id`. A friend who hits the bot first gives it there (an
  `awaiting_email` `chat_state`); one who hits the dashboard first gives it in a
  one-field modal. The other surface never re-asks.
- **Approval is push, one-tap.** When a `pending` user submits their email, vig
  pushes the Operator (`OPERATOR_CHAT_ID`) a message with inline
  ✅ Approve / 🚫 Block, reusing the existing inline-keyboard + callback
  machinery. One tap flips `status` and notifies the user.
- **Enforcement.** Bot: a non-`approved` chat_id is refused at the **inbound
  message handler**, before any feature dispatch — job creation, the inline
  photo pipeline, `/find`, `/download_md`, and other commands — so "can do
  nothing" holds across every surface, not just job creation. **Ordering:** the
  handler dispatches an `awaiting_email` `chat_state` (the one-time email
  capture) *before* applying the gate, and the Operator's approve/block
  callbacks are always allowed; everything else is refused. Dashboard: the
  session still mints (identity), and `/api/*` returns 403 until `approved` —
  **except** the email-submission endpoint (e.g. `POST /api/onboard`), which is
  exempt from the gate so a `pending` user can complete the one-time-ask. That
  onboarding endpoint authorizes on a valid session alone, never on `status`. The URL in a pre-approval first message is dropped — the friend
  resends after approval (no held-job store).
- **Cutover.** `OPERATOR_CHAT_ID` is auto-approved unconditionally (the Operator
  cannot be locked out of their own bot). The migration grandfathers every
  pre-existing `users` row to `approved`; grandfathered rows keep a null email
  (today that is only the Operator and one personal account — no outreach
  needed).

## Considered and rejected

- **Collect-and-admit (default-allow):** anyone giving any email is in until
  blocked. Rejected — "allowlist" means a real gate, and a stranger who finds
  the bot should not transact before approval.
- **Pre-seed an allowlist by Telegram `@username`** (the Login Widget returns
  `username`): rejected — usernames are optional and mutable, and it forces a
  manual LinkedIn→username mapping per friend. The in-app one-time ask
  auto-binds email↔identity with zero manual mapping.
- **Capture phone:** not possible and not wanted. The Login Widget payload has
  **no** phone field; the phone is Telegram's own account-auth step, never seen
  or stored by vig.
- **Email verification (confirm link):** rejected — no SMTP infra, and email is
  for Operator outreach, not authentication.

## Consequences

- `chat_state.mode` has a `CHECK` constraint; adding `awaiting_email` needs a
  schema migration to that constraint.
- The new `users.status` column must ship with its own
  `CHECK(status IN ('pending', 'approved', 'blocked'))` (same pattern as
  `mode`), so #254 can't leave invalid status values silently writable.
- The gate lands at exactly two enforcement points (bot inbound message handler,
  dashboard `/api/*` middleware) — both must honor `users.status`. The bot point
  is the inbound handler, *before* feature dispatch — not job-creation — so
  `/find`, `/download_md`, the inline photo pipeline, and every other command are
  refused too, not just job creation.
- `OPERATOR_CHAT_ID` (ADR-0030) is load-bearing as the admin identity; this
  track is sequenced **after** #208.
- Orthogonal to per-user export isolation (epic #201): a friend can be
  `approved` and use VIG (Telegram + dashboard) without any Google connection.
  Personal Drive/Sheets exports remain the separate #204+ OAuth feature.
