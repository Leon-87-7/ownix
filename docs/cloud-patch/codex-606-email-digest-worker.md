# Codex prompt — implement issue #606 (email digest pipeline, batch 4: Cloudflare Worker + runbook)

> Working-tree changes only. **Do not commit, do not push, do not open PRs.**
> Leave all changes uncommitted for human review.

This is **batch 4 of 4** implementing the email-digest feature (#600–#606),
and is independent of the Python backend batches — it's a standalone
TypeScript project (`ops/email-worker/`) that talks to the webhook contract
from #601 over HTTP. If #601 has already landed in this working tree, you
may confirm the webhook path/header name against the actual code; if not,
`PLAN.md` §3 and the issue body fully specify the contract and are
sufficient to build against.

This issue is marked **HITL**: the Cloudflare dashboard catch-all
Email-Routing rule and a live email round-trip verification require the
human's own Cloudflare account/DNS access and cannot be done or verified by
you. Your part is the Worker code and the runbook documenting the manual
steps — nothing more.

## Required context — read these first, in this order

1. `docs/research/2026-09-05-email-digest-claudex-research.md` — primary-source
   research on Cloudflare Email Routing/Workers mechanics (`§1` — the
   `ForwardableEmailMessage` API, `§2` — catch-all-to-Worker addressing,
   `§3` — why SPF/DKIM verdicts aren't usable from a Worker, `§4` — ESP
   tracking-link conventions, relevant background even though link
   resolution happens Python-side).
2. `PLAN.md` (repo root) — §2 ("Inbound transport") is what this batch
   implements; read the rest for context on why the shared-secret webhook
   trust boundary was chosen over SPF/DKIM inspection.
3. `PLAN-REVIEW-LOG.md` (repo root) — Round 2 (envelope-recipient sourcing,
   sender-address normalization), Round 4 (the exact `from` normalization
   fix: `parsedEmail.from.address.toLowerCase()`).
4. If it exists yet in this working tree: whatever `src/api/email_webhook.py`
   /`src/config.py` #601 produced — confirm the exact secret header name and
   webhook path against the real code. Otherwise, use
   `X-Ownix-Email-Secret` and `POST /webhook/email-digest` as specified in
   `PLAN.md`/the issue body.
5. GitHub issue #606 (`gh issue view 606 --repo Leon-87-7/ownix`) — its
   acceptance criteria are the definition of done.

## Key decisions already made (do not relitigate)

- **`from` is forwarded as the normalized lowercase addr-spec only**:
  `parsedEmail.from.address.toLowerCase()` — never the raw structured
  `{name, address}` object or a raw header string. This is required so the
  Python side's case-insensitive sender compare can't false-negative on a
  display-name-inclusive or differently-encoded string.
- **`envelopeTo` is read directly off the Workers runtime object**
  (`message.to` on the `ForwardableEmailMessage`), never off postal-mime's
  parsed `To:` header — a parsed header is unreliable for catch-all/BCC/
  forwarded mail per the research doc §2.
- **MIME parsing happens once, entirely inside the Worker**, via
  `postal-mime`. The Python webhook never touches raw MIME — it receives
  already-clean `{from, to/envelopeTo, subject, html, text, messageId}` JSON.
- **Trust boundary is a shared secret header, not SPF/DKIM inspection** —
  per the research doc §3, Cloudflare doesn't reliably expose a usable
  authentication verdict to a Worker. The secret is provisioned as a Worker
  secret via `wrangler secret put`, never hardcoded in `wrangler.toml` or
  committed source.
- **Plus-addressing is not usable for per-user routing** — Cloudflare
  collapses `user+detail@` to the `user@` rule (research doc §2), so the
  opaque `alias_local_part` from #600 must be the *entire* local-part, read
  out of `envelopeTo` server-side, not derived from a `+detail` suffix.
- **This is a new, small, standalone project** at `ops/email-worker/`,
  Wrangler-deployed, explicitly **not** part of Docker Compose and not wired
  into this repo's `npm`/`pytest` scripts — it has its own
  `package.json`/`wrangler.toml`.

## Work order

### #606 — ops(email-worker): Cloudflare Worker + catch-all Email Routing runbook

1. New `ops/email-worker/` TS project:
   - `src/index.ts` (or equivalent) exporting the `email(message, env, ctx)`
     handler (a `ForwardableEmailMessage`), using `postal-mime` to parse
     `message.raw` into `{subject, html, text, messageId}` (`postal-mime`
     accepts the `ReadableStream` directly — no manual buffering).
   - Build the outbound payload: `from` = normalized lowercase addr-spec,
     `envelopeTo` = `message.to` (verbatim, from the runtime object, a
     distinct field from anything postal-mime parsed), plus `subject`,
     `html`, `text`, `messageId`.
   - `fetch()` that JSON to `https://api.leondev.xyz/webhook/email-digest`
     (or the confirmed actual path from #601) with header
     `X-Ownix-Email-Secret: <env binding>` (or the confirmed actual header
     name) — the secret read from `env` (a Worker secret binding), never a
     literal string in source.
   - Handle a malformed/unparseable email gracefully (postal-mime parse
     errors are common enough to expect, per the research doc §1) — log and
     return rather than throwing unhandled.
   - `package.json` with `postal-mime` as a dependency; `tsconfig.json` if
     needed for Workers types (`@cloudflare/workers-types`).
2. `wrangler.toml`: name, compatibility date, the `email` handler entry
   point. Document (in the runbook, not in `wrangler.toml` itself) that the
   shared secret is set via `wrangler secret put EMAIL_WEBHOOK_SECRET` (or
   whatever binding name you choose — name it clearly).
3. `docs/ops/` runbook (new file, e.g.
   `docs/ops/email-digest-cloudflare-setup.md`) covering, for a human to
   execute:
   - Deploying the Worker (`wrangler deploy`).
   - Setting the shared secret (`wrangler secret put`).
   - Creating the catch-all Email Routing rule on `leondev.xyz` in the
     Cloudflare dashboard, pointed at this Worker.
   - How to verify: send a test email to a real
     `u_<token>@leondev.xyz` alias and confirm a receipt job appears (what
     to check, where — the Feed exclusion means this needs checking via the
     newsletter-digest page or the jobs table directly, say so explicitly).
4. State plainly, in your final summary, that the Cloudflare dashboard
   wiring and the live email round-trip are deferred to the human via this
   runbook — do not claim end-to-end verification happened.

## Hard constraints

- No commits, no pushes, no PRs, no branch creation — working tree only.
- Don't touch anything under `src/`, `web/`, or `docker-compose.yml` — this
  batch is scoped entirely to `ops/email-worker/` and `docs/ops/`.
- No attempt to configure the actual Cloudflare catch-all rule or request
  Cloudflare credentials — that's the human's part per the runbook.
- If a Worker-side unit test setup is trivial to add (e.g. a pure function
  test for payload normalization), add one; don't invent a full test
  harness/CI pipeline for a small ops project that has none today.

## Deliverable

Uncommitted working-tree changes: `ops/email-worker/` (Worker code,
`wrangler.toml`, `package.json`) and a runbook under `docs/ops/`. A short
summary stating exactly what remains for the human (Cloudflare dashboard
rule, secret provisioning, live verification) per the runbook.
