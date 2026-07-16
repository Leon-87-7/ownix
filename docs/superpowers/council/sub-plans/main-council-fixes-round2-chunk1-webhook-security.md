# Round 2 Chunk 1 - Webhook Security

> **Worker note:** This chunk owns `src/telegram/webhook.py` only. Do not edit tests here unless the implementation cannot be expressed without a tiny helper exposure. Do not stage or commit.
>
> **Pinned context:** reviewed commit `c3b04e3`; diff is the staged/worktree Ops bot patch on `main`.

## Global Constraints

- Do not touch production secrets, `.env`, or `.env.local`.
- Run tests directly with `python -m pytest ...`, never through `rtk`.
- Do not merge or push to `main`.
- Do not revert edits made by other agents.

## Parallel Task Map

- Task 1: `src/telegram/webhook.py`
- Task 2: `src/telegram/webhook.py`

These tasks intentionally share one file and must be handled by one worker sequentially.

## Task 1: Fail Closed When `OPS_WEBHOOK_SECRET` Is Unset

**Files:**
- Modify: `src/telegram/webhook.py`

**Finding:** `compare_digest(x_telegram_bot_api_secret_token or "", settings.OPS_WEBHOOK_SECRET)` accepts empty secret plus missing header.

Steps:

- [ ] Add an explicit guard before `compare_digest` in `ops_webhook`:

```python
    if not settings.OPS_WEBHOOK_SECRET:
        log.warning("ops_webhook_secret_unset")
        raise HTTPException(status_code=403, detail="invalid secret")
```

- [ ] Keep the existing invalid-secret response for non-matching headers.
- [ ] Do not register or accept any special local bypass here.

## Task 2: Authorize Mutating Ops Callbacks By Sender User Id

**Files:**
- Modify: `src/telegram/webhook.py`

**Finding:** `_handle_ops_callback` checks the message delivery chat id. In a group chat, any member can click the admin button.

Steps:

- [ ] Read the callback sender id from `callback.get("from", {}).get("id")`.
- [ ] For mutating prefixes `ops_invite_approve`, `ops_invite_block`, `ops_approve_pending`, and `ops_approve_pending_cancel`, require `ops_bot.can_admin(sender_id)`.
- [ ] Keep `chat_id` as the message chat id for editing the Ops message markup.
- [ ] For non-mutating `ops_invite_status` and `ops_batch_status`, answer without mutation.
- [ ] If the callback has no sender id or sender is not admin, call `ops_bot.answer_ops_callback(cq_id, "Not authorized.")`, log `sender_id`, `chat_id`, and `data`, and return before mutating any user status.

Verification command:

```powershell
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m py_compile src/telegram/webhook.py
```
