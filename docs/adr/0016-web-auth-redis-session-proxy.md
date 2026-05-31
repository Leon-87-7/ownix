---
adr: "0016"
title: Web dashboard auth — Telegram Login Widget, Redis session (no JWT), frontend-proxied
status: accepted
date: 2026-05-31
---

## Context

The web dashboard (`app.leondev.xyz`, Next.js) needs to authenticate users
against the existing FastAPI service (`api.leondev.xyz`) and scope every
request to a [[Tenant]] (`chat_id`). Three coupled questions had to be
answered together: how users prove identity, how the session is carried,
and how the browser reaches the API across (eventually) two hosts.

Identity is settled by the product: **Telegram Login Widget**, HMAC-verified
with the bot token. The open questions were the session mechanism (JWT vs
server-side session) and the network path (direct cross-origin vs proxy).

## Decision

**1. Server-side Redis session, not JWT.** On login we verify the widget
HMAC, upsert the `users` row, mint a random opaque `session_id`, and store
`session:{id} → {chat_id, telegram_user_id}` in Redis with a 30-day TTL.
The id rides in an httpOnly `SameSite=Lax` cookie. Middleware on `/api/*`
does a Redis lookup and attaches `chat_id`, else 401.

**2. Option A — production proxies browser → frontend → API.** The browser
only ever calls relative `/api/*` (same origin as the frontend); Next.js
rewrites those server-side to the API container via a non-public
`API_INTERNAL_URL`. Dev and prod behave identically (the dev
`next.config.js` rewrite is the same mechanism). No `NEXT_PUBLIC_*` API
origin is exposed to the browser.

**3. `/api/*` is the only protected prefix.** `/webhook` (Telegram
secret-token auth) and `/health` stay open; the Second Brain endpoints move
from `/links` under `/api/brain` so the single prefix rule covers them.

## Consequences

- **Pro:** Revocation is a one-line `DEL session:{id}` ("log out
  everywhere"); no JWT blocklist, no signing-secret rotation, no
  expiry/refresh machinery.
- **Pro:** Cookie stays first-party `SameSite=Lax` even after the host split
  (`app.`/`api.` are subdomains of one site), keeping httpOnly XSS
  protection without `SameSite=None` third-party-cookie breakage (Safari ITP
  etc.).
- **Pro:** Reuses Redis, already in the request path — the per-request
  lookup is microseconds.
- **Con:** Auth is now stateful — every request hits Redis, and a Redis
  outage logs everyone out. Acceptable: Redis is already a hard dependency
  of the queue.
- **Con:** The proxy adds one server-side hop per call. Negligible at this
  traffic; revisited only if the dashboard ever serves heavy direct load.

## Considered Alternatives

- **JWT in an httpOnly cookie** (the original plan). Rejected: its only real
  advantage — stateless validation across many instances — is moot at
  single-user/single-instance scale, *and* even multi-instance is already
  covered by shared Redis. In exchange it costs a signing secret, an
  expiry/refresh flow, and a blocklist for revocation (which re-introduces
  the very state JWT was meant to avoid).
- **Direct cross-origin browser → API with a Bearer token.** Rejected:
  loses httpOnly XSS protection (token readable by scripts) and needs
  `SameSite=None` / CORS once the hosts split — fragile against
  third-party-cookie blocking.
