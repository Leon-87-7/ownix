---
adr: "0019"
title: User templates trigger with a "-name" dash sigil, separate from built-in "/name" slash commands
status: accepted
date: 2026-05-31
---

## Context

The dashboard lets users create enrichment [[User template]]s in the DB.
The plan said these should "live in the bot" — implying a triggerable
command per template. But the bot's [[Webhook dispatch table]] (`_SLASH_TABLE`)
is **assembled at import time**, merging the built-in template commands
generated from the in-code `PROMPT_TEMPLATES`. DB-backed templates aren't
known until an async read at startup, and new ones are created at runtime —
so they cannot be registered into a frozen, import-time slash table without
making it mutable and refreshable across processes.

Built-ins are also immutable by product rule (undeletable, uneditable).

## Decision

Built-in templates keep their **immutable `/name` slash commands**,
registered at import from `PROMPT_TEMPLATES` (unchanged). User templates
fire by a **separate `-name <url>` dash sigil**, resolved by an **async DB
lookup in the webhook text handler** at job-creation time — a new branch,
not an entry in `_SLASH_TABLE`. Built-ins stay in code (the single source of
truth for slash dispatch and auto-routing); they are **not** seeded into the
DB. User-template names may **not** collide with built-in names, so
`jobs.template = "<name>"` resolves unambiguously. A resolved user template
copies its `extra_instructions` into the job's `freestyle_prompt`, riding the
existing [[Freestyle prompt]] enrichment seam — no processor change.

## Consequences

- **Pro:** The import-time dispatch contract that four telegram modules
  depend on is never touched; no mutable `_SLASH_TABLE`, no cross-process
  cache invalidation. A new template works the instant it's saved.
- **Pro:** The sigil is self-documenting UX — `/` = official/immutable,
  `-` = your custom — and matches Telegram's reality, where the `/`
  autocomplete menu only serves `setMyCommands`-registered commands anyway.
- **Pro:** Reusing the freestyle seam means zero enrichment-processor change;
  a user template is just "saved extra_instructions."
- **Con:** User templates do not appear in Telegram's `/` autocomplete (they
  aren't slash commands) — acceptable, since dynamic churn of
  `setMyCommands` per user template is worse.
- **Con:** MVP honors only `extra_instructions`; `brave_search` and
  `content_type_scope` are stored-but-unenforced. Extensible later via the
  retained `jobs.template` name (re-resolve the row) with no migration.

## Considered Alternatives

- **Dynamic slash registration** — rebuild `_SLASH_TABLE` from the DB at
  startup and on every template create/edit. Rejected: turns a frozen,
  import-time structure into mutable shared state needing refresh hooks and
  cross-process invalidation, for a marginal autocomplete gain.
- **Web-only templates (no bot trigger)** — usable in the dashboard and
  auto-routing only. Rejected: the user wants to fire custom templates from
  the bot, and the dash sigil delivers that cheaply.
