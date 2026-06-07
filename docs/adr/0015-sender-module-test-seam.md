---
adr: '0015'
title: Telegram sender module is the canonical test seam for the telegram package
status: rejected
date: 2026-05-29
---

## Context

`src/telegram/webhook.py` grew to 1133 lines and is being split into
sibling modules — `dispatch.py` (the `CallbackCtx` / `SlashCtx` contract),
`callbacks.py` (the 12 `_cb_*` handlers + `_CALLBACK_TABLE`),
`domain_cmds.py` (the `/ignore` · `/allowlist` family), and `photo.py`
(the photo batch state machine) — while `webhook.py` keeps the router and
its resident slash commands.

The blocker surfaced in the tests. `tests/test_webhook.py` has **72**
`monkeypatch.setattr("src.telegram.webhook.send_message", …)` lines. Those
work today only because the handlers live in `webhook.py` and reference the
`send_message` name imported into that module. Python binds `from … import
send_message` to a _local_ name at import time, so the moment a handler
moves to `callbacks.py` it references `callbacks.send_message` and a patch
of `webhook.send_message` silently stops affecting it — the test passes a
stale mock and asserts nothing. The extraction therefore _forces_ a
test-seam decision; it cannot be deferred.

Three options were considered (see below). `sender.py` is already the sole
adapter to the Telegram Bot API (`send_message`, `send_inline_keyboard`,
`answer_callback_query`, …) — the genuine seam to the outside world.

## Decision

All modules in the `src/telegram/` package call the sender
**module-qualified** — `sender.send_message(...)`, never a bare imported
`send_message(...)`. Tests patch `src.telegram.sender.*` **once**, at the
adapter. The fake is the second adapter at that seam; production is the
first.

Scope is the telegram package only (`webhook.py`, `callbacks.py`,
`photo.py`, `domain_cmds.py`). `worker.py` and the six processors keep
their existing `from src.telegram.sender import …` style and their own
patch targets — converting them is unrelated churn for this refactor.

## Consequences

- **Pro:** The test seam is independent of file layout. Future moves of a
  handler between telegram modules never re-break a `send_*` assertion —
  the patch target is always `src.telegram.sender.X`.
- **Pro:** ~72 webhook-local patches collapse to ~9 sender-level targets.
- **Pro:** Reading any telegram module, `sender.send_message(...)` names
  the seam explicitly at the call site.
- **Con:** Deliberate intra-repo inconsistency — telegram modules call
  `sender.X(...)` while `worker.py` / processors use `from sender import
X`. Recorded here precisely so a future reader does not "fix" it into
  uniformity and break the webhook test seam.
- **Con:** Module-qualified calls are slightly more verbose than bare names.

## Considered Alternatives

- **Chase the owning module** — keep bare-name imports; update each test to
  patch `src.telegram.callbacks.send_message`, `src.telegram.photo.send_message`,
  etc. Rejected: couples every test to the current file layout, so the next
  handler move re-breaks the same 72 lines.
- **Re-export shim in `webhook.py`** — keep old import paths alive by
  re-exporting moved symbols. Rejected: does not fix patching (name binding
  means a moved handler still uses its own module's binding) and risks a
  `webhook` ↔ `callbacks` import cycle. Lowest churn, highest hidden
  breakage.
- **Convert the whole codebase to `sender.*`** — one uniform seam
  everywhere, including `worker.py` and processors. Rejected for _this_
  refactor as scope creep: it would force rewriting processor/worker test
  patch targets, a concern orthogonal to splitting `webhook.py`.
