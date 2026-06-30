---
adr: "0030"
title: Export gate now, per-user drive.file OAuth later — the multi-tenancy credential model
status: accepted
date: 2026-06-21
---

## Context

Issue #201 framed multi-tenancy as a `user_config` table (per-user Sheets ID +
Drive folder IDs) plus rewiring every `append_*_row`/`upload_file` call site to
resolve a per-user destination, leaning toward a "shared service account writing
into user-granted folders" credential model as "far lighter and probably enough."

Two facts reshaped that:

1. **ADR-0022 already decided** centralized [[Platform storage]] (GCS + DB,
   `chat_id`-isolated) is the primary record and Drive/Sheets are *opt-in OAuth
   exports*. The DB is already tenant-isolated; GCS is sha-keyed/shared by design
   (safe). The only place a second user's data pools into the Operator's account
   is the **unconditional Drive/Sheets writes**. So #201's real bug is narrow.

2. **The "lighter" service-account model does not work for the user base.**
   Service accounts have no storage quota and cannot own files; creating a file
   in a *consumer Gmail* user's shared folder fails with `Service Accounts do not
   have storage quota` — SAs can only create files in a Workspace Shared Drive or
   via OAuth delegation. vig's users are Telegram consumers on personal Gmail, so
   SA-into-shared-folders is non-functional for the Drive half (every
   `upload_file` *creates* a file) and would force a two-credential split.

## Decision

**Now (the #201 fix): an Operator gate, not a config store.** Add one
`OPERATOR_CHAT_ID` setting. Each Drive/Sheets export early-returns unless
`job.chat_id == settings.OPERATOR_CHAT_ID`. Non-[[Operator]] tenants get
[[Platform storage]] + Telegram + the (already `chat_id`-scoped, ADR-0026)
dashboard. No `user_config` table, no `/config` command, no per-folder routing —
that is speculative scaffolding for a feature that does not exist yet.

**Later (only when a user asks): per-user OAuth, narrowly scoped.** When
"connect your own Google account" is built, it is per-user OAuth scoped to
`drive.file` + `spreadsheets`, writing results into a vig-created `/vig` folder.
The shared-SA model is rejected outright.

## Consequences

- **Zero CASA.** Full `drive`/`drive.readonly` are *restricted* scopes that
  trigger a Google CASA security assessment (paid, Google-approved lab, yearly
  re-audit). `drive.file` is non-sensitive and `spreadsheets` is sensitive-only
  (manual justification, no audit). Scoping to `drive.file` + `spreadsheets`
  avoids the entire security-assessment burden.
- **Trade-off accepted:** `drive.file` lets vig touch only files *it* created, so
  results land in a vig-made `/vig` folder rather than an arbitrary pre-existing
  folder the user names. Pointing at a user-chosen existing folder would need the
  Drive Picker or a restricted scope (CASA) — deliberately out of scope.
- The `user_config` table from #201 is dropped; if per-user OAuth ships it brings
  its own per-user token store, which is where any per-user destination config
  would live.
- #201's scope shrinks to ~a dozen lines (the gate). It supersedes nothing in
  ADR-0022 — it implements 0022's "opt-in export" stance and pins the scope.

## Onboarding & token lifecycle (the OAuth feature, when built)

- **Two entry surfaces, one backend.** Web users connect via the existing
  Telegram Login Widget + dashboard (ADR-0016); Telegram users via a Mini App
  whose signed `initData` carries the verified `chat_id` for free. Both verify a
  `chat_id` (different HMAC keys) and converge on a single OAuth callback + single
  encrypted per-`chat_id` token store. No second token store or callback.
- **Identity first, Google second.** The `chat_id` is the tenant; the Google
  token hangs off it. Telegram identity is always established before the Google
  grant — never the reverse (a Google token with no tenant is an orphan).
- **"Connected" is derived at use, not a trusted flag.** Google sends no
  revocation signal; the only indicator is a `RefreshError`/`invalid_grant` on the
  next refresh. One `try/except` at the export boundary uniformly catches
  user-revoke, 6-month idle, and 50-token eviction. On failure: delete the token,
  **notify the user once** with a `/connect` deep-link, and — exports being
  fire-and-forget — never fail the job. `/disconnect` = best-effort revoke
  (`oauth2.googleapis.com/revoke`) then local delete. Reconnect uses
  `prompt=consent` (Google only re-issues a refresh token on forced consent).
- **No Gmail scopes ⇒ password changes don't revoke.** A real payoff of the
  `drive.file` + `spreadsheets` choice.

These lifecycle mechanics are reversible implementation choices recorded for the
implementer; the irreversible decisions are the gate and the scope model above.

## References

- [SA have no storage quota / can't own files](https://github.com/n8n-io/n8n/issues/26050),
  [Google Drive usage limits](https://developers.google.com/workspace/drive/api/guides/limits)
- [Drive API scope choice](https://developers.google.com/workspace/drive/api/guides/api-specific-auth),
  [Restricted-scope verification / CASA](https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification)
- ADR-0022 (centralized storage), ADR-0013 (shared workbook), ADR-0026 (tenant-scoped dashboard)
