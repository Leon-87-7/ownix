# Main Council Review Round 2 - Fix Plan

> **Context:** This is round 2 for `main`; round 1 is `docs/superpowers/council/main-council-fixes.md`.
>
> **Pinned context:** reviewed commit `c3b04e3`; diff range is the staged/worktree Ops bot patch on `main` against `c3b04e3`.
>
> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. This plan is chunked. Do not execute this file top-to-bottom; work the sub-plans below.

| Chunk | Sub-plan | Tasks | Theme |
|---|---|---|---|
| 1 | [sub-plans/main-council-fixes-round2-chunk1-webhook-security.md](sub-plans/main-council-fixes-round2-chunk1-webhook-security.md) | 1, 2 | Ops webhook authentication and callback authorization |
| 2 | [sub-plans/main-council-fixes-round2-chunk2-ops-commands.md](sub-plans/main-council-fixes-round2-chunk2-ops-commands.md) | 3, 4, 5 | Ops card reliability, domain validation, help UX |
| 3 | [sub-plans/main-council-fixes-round2-chunk3-tests-and-hygiene.md](sub-plans/main-council-fixes-round2-chunk3-tests-and-hygiene.md) | 6, 7 | Test alignment and Codacy local config hygiene |

**Goal:** Fix the council findings in the landed Ops bot patch before opening a PR.

**Architecture:** Keep the Ops bot feature, including batch approval and the ngrok helper, because those were explicit product requirements. Tighten the safety boundaries: Ops webhook requests must fail closed, mutating callbacks must authorize the sender, batch approval must reject ambiguous domains, and Telegram cards must avoid Markdown parse failures.

**Tech Stack:** Python FastAPI, pytest/pytest-asyncio, SQLite-backed user state, Telegram Bot API helpers in `src/telegram/sender.py`.

## Global Constraints

- Do not touch production secrets, `.env`, or `.env.local`.
- Run tests directly with `python -m pytest ...`, never through `rtk`.
- Do not merge or push to `main` during worker execution.
- Preserve the user's explicit requirements: keep `/approve_pending <domain>`, keep CSV-over-20 behavior, keep the explicit ngrok helper, keep dev E2E support.
- Workers are not alone in the codebase. Do not revert edits made by other agents; adapt to the current file contents.
- Commit only after the orchestrator has reviewed and serialized changes. Parallel workers should not run `git add` or `git commit`.

## Findings To Fix

- Blocker: `src/telegram/webhook.py:1696` accepts empty `OPS_WEBHOOK_SECRET` with a missing Telegram header.
- Blocker: `src/telegram/webhook.py:1630` authorizes mutating callbacks by delivery chat id instead of callback sender id.
- Blocker: `src/services/ops_bot.py:179` lets empty domain batch approval approve every pending user.
- Blocker: `tests/test_webhook.py:522` still expects deprecated Ownix invite callbacks to mutate status.
- Major: `src/services/ops_bot.py:84` sends unescaped user-controlled text with `parse_mode="Markdown"`.
- Major: `src/services/ops_bot.py:219` previews the first 20 users but confirms approval for all matches without making that scope explicit.
- Minor: `src/services/ops_bot.py:181` has no `/start`, `/help`, or unknown-command response.

## Skipped / Needs User Decision

- Ponytail suggested deleting batch approval entirely. Skipped: user explicitly requested batch approval.
- Ponytail suggested deleting `scripts/ops-ngrok-e2e.sh`. Skipped: user explicitly requested a commented/manual ngrok helper.
- Ponytail suggested choosing only one dev shortcut. Skipped: user explicitly wants E2E testing available; keep both dev notification opt-in and local `/dev-approve` unless later product review says otherwise.

## Final Verification

After all chunks land, run:

```powershell
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m py_compile src/config.py src/telegram/sender.py src/telegram/webhook.py src/api/auth.py src/auth/middleware.py src/auth/session.py src/services/invite_notifications.py src/services/ops_bot.py src/main.py
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/test_config.py -q
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/test_auth.py::TestSessionMiddleware::test_dev_approve_fallback_approves_current_dev_session tests/test_auth.py::TestSessionMiddleware::test_dev_login_quiet_by_default tests/test_auth.py::TestSessionMiddleware::test_dev_login_sends_marked_ops_card_when_enabled -q
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/test_webhook.py::test_ops_webhook_rejects_wrong_secret tests/test_webhook.py::test_ops_unauthorized_invite_callback_does_not_mutate_user tests/test_webhook.py::test_ops_authorized_invite_callback_mutates_and_uses_ownix_user_message tests/test_webhook.py::test_ops_pending_command_renders_rows_for_read_allowlist -q
git diff --check
```
