---
adr: "0064"
title: Per-user spending guardrails supersede "the paid key is a sufficient backstop"
status: accepted
date: 2026-09-22
supersedes: "0006"
---

## Context

ADR-0006 decided Gemini's fallback order (free → paid, never Anthropic) and, in its
Rationale, treated **cost control** as settled: "the paid Gemini key is a sufficient
backstop." That was true for a single-operator tool where the Operator was the only
account that could ever reach the paid key. It stopped being true once the product
became multi-user (ADR-0043): any approved account's traffic can drive paid Gemini
spend, and nothing before this ADR could answer "may this user spend another $0.20
today," account for a retry's partial cost, or survive a process restart.

Independently re-verified 2026-09-22 against `HEAD`: `src/intake/rate_limit.py` and
`src/intake/quota.py` are in-process, per-worker-process request-rate limiters — they
bound *how fast*, not *how much money*, reset on restart, and are not shared across the
API and worker processes. No `usage_ledger`, `spend_limit`, or `PAID_AI_ENABLED`-style
kill switch existed anywhere in the repo before this ADR's implementation.

## Decision

- **SQLite is the authoritative financial ledger** (`usage_ledger`, `user_spend_limits` —
  migration v53), the same way it already is for `jobs`. Redis remains for burst/
  concurrency limits, not accounting.
- **Reserve before work, settle after work.** `src/services/spending.py` /
  `src/db/spending.py` implement an atomic (`BEGIN IMMEDIATE`) reserve → settle/release
  lifecycle keyed by an idempotency key, so a hard limit accounts for in-flight paid
  calls, not just completed ones.
- **Paid Gemini is opt-in per user**, off by default (`user_spend_limits.allow_paid_gemini
  = 0`); a missing row means no paid access, never unlimited access. A global
  `PAID_AI_ENABLED` env kill switch is checked in addition to per-user policy.
- **The provider boundary is the single enforcement point.** `src/services/gemini.py`'s
  `_call_with_fallback` — the one fallback loop every public Gemini function already
  funneled through — now requires an explicit `CostContext` and gates only the *paid*
  attempt on a reservation; the free attempt is unmetered and untouched by this ADR.
- **Every system-initiated call (newsletter issue context, scheduled Brain refresh) is
  charged to an explicit owner** — the subscribing tenant for tenant-specific work, or
  `OPERATOR_CHAT_ID` for genuinely shared/global work — never to an arbitrary user.

## Rationale

ADR-0006's free→paid fallback order is unchanged and not superseded — only its cost-control
rationale is. "The paid key is a sufficient backstop" assumed one biller; it is not a
statement that holds once other accounts can reach that key. This ADR does not reopen
the model-choice question (still Gemini-only, no Anthropic).

## Consequences

- Every public Gemini call (`generate`, `call_gemini_vision`, `call_gemini_photo_links`,
  `select_informative_screenshots`, `resolve_tool_urls`, `brain._embed`) now takes a
  required `cost: CostContext` keyword argument. Callers with no natural per-request
  owner (a scheduled sweep) must pick an explicit one rather than omitting it.
- A caller-supplied `attempt` does not yet collapse a crash-and-redelivery onto one
  reservation — the queue envelope's `attempt`/`depth`/`root_task_id` lineage (also
  added by this ADR, `src/job_queue.py`) is threaded through `_dispatch`'s bounds
  check, but `spending._idempotency_key` currently mints a fresh key per call rather
  than keying off `attempt`, because no automatic crash-redelivery exists yet for that
  collapsing to protect anything — see the docstring on `_idempotency_key` for the
  full reasoning and the revisit condition.
- `docs/seed/CAPABILITY_MAP.md`, `docs/seed/FUNCTION_INDEX.md`, and
  `docs/seed/GLUE_INDEX_BACKEND.md` describe the spending ledger and the gated
  provider boundary.
- Default daily/monthly caps, decided 2026-09-22: **$0.50/day, $3/month**
  (`db.spending.DEFAULT_DAILY_LIMIT_MICROS`/`DEFAULT_MONTHLY_LIMIT_MICROS`).
  These are the caps a user *would* have if paid Gemini were enabled for them —
  `allow_paid_gemini` staying `False` by default is still the actual access
  gate; an Operator opts an account in per the §6 rollout, and an
  `SpendLimitsIn` PUT that omits the limit fields inherits these same
  defaults rather than silently meaning unlimited (pass `null` explicitly to
  remove a cap).
- Still deferred (values live with the product owner, per the original
  handoff's §7): whether newsletter automation should ever be charged
  per-subscriber instead of to the Operator, and the exact reservation
  envelope per pipeline/model. Safe defaults (paid disabled, UTC windows,
  Operator-only limit writes) apply until those are set.
