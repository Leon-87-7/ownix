# Round 2 Chunk 3 - Tests And Hygiene

> **Worker note:** Run this after chunks 1 and 2 are integrated. This chunk owns `tests/test_webhook.py`, `.gitignore`, and `.codacy/codacy.yaml` tracking state. Do not stage or commit without the orchestrator.
>
> **Pinned context:** reviewed commit `c3b04e3`; diff is the staged/worktree Ops bot patch on `main`.

## Global Constraints

- Do not touch production secrets, `.env`, or `.env.local`.
- Run tests directly with `python -m pytest ...`, never through `rtk`.
- Do not revert edits made by other agents.

## Parallel Task Map

- Task 6: `tests/test_webhook.py`
- Task 7: `.gitignore`, `.codacy/codacy.yaml`

These tasks are disjoint and can be handled by separate workers if desired.

## Task 6: Align Webhook Tests With Ops-Only Approval Mutations

**Files:**
- Modify: `tests/test_webhook.py`

**Finding:** Legacy Ownix `invite_approve:*` and `invite_block:*` tests still expect status mutation, while the patch deprecates that path.

Steps:

- [ ] Update `test_invite_callback_approve_flips_status_and_notifies_user` to assert the deprecated Ownix callback does not mutate status and answers with the deprecation text.
- [ ] Update `test_invite_callback_block_flips_status_and_notifies_user` the same way.
- [ ] Add/adjust tests for the chunk 1 fixes:
  - Ops webhook rejects requests when `OPS_WEBHOOK_SECRET` is unset.
  - Ops invite callback with admin delivery chat but non-admin callback sender does not mutate status.
  - Ops invite callback with admin callback sender does mutate status and still sends user outcome via Ownix `send_message`.
- [ ] Add/adjust tests for the chunk 2 fixes:
  - `/approve_pending @` and `ops_approve_pending:` do not approve all pending users.
  - Invite cards are sent without `parse_mode="Markdown"`.
  - `/help` or unknown command returns the command list.

Verification command:

```powershell
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m pytest tests/test_webhook.py::test_ops_webhook_rejects_wrong_secret tests/test_webhook.py::test_ops_unauthorized_invite_callback_does_not_mutate_user tests/test_webhook.py::test_ops_authorized_invite_callback_mutates_and_uses_ownix_user_message tests/test_webhook.py::test_ops_pending_command_renders_rows_for_read_allowlist -q
```

## Task 7: Keep Codacy Local Config Ignored

**Files:**
- Modify: `.gitignore`
- Remove from index only: `.codacy/codacy.yaml`

Steps:

- [ ] Ensure `.gitignore` contains exactly one line: `.codacy/codacy.yaml`.
- [ ] Ensure `.codacy/codacy.yaml` remains present locally but is removed from Git tracking with `git rm --cached .codacy/codacy.yaml`.
- [ ] Verify:

```powershell
git check-ignore -v .codacy/codacy.yaml
git status --short --branch --untracked-files=all
```

Expected: `.codacy/codacy.yaml` appears as staged deletion and does not appear as untracked.
