# Round 2 Chunk 2 - Ops Commands And Cards

> **Worker note:** This chunk owns `src/services/ops_bot.py` only. Do not edit webhook tests here; the follow-up test chunk will align tests after code lands. Do not stage or commit.
>
> **Pinned context:** reviewed commit `c3b04e3`; diff is the staged/worktree Ops bot patch on `main`.

## Global Constraints

- Keep `/approve_pending <domain>`, CSV-over-20 behavior, and the explicit ngrok helper.
- Do not touch production secrets, `.env`, or `.env.local`.
- Run tests directly with `python -m pytest ...`, never through `rtk`.
- Do not revert edits made by other agents.

## Parallel Task Map

- Task 3: `src/services/ops_bot.py`
- Task 4: `src/services/ops_bot.py`
- Task 5: `src/services/ops_bot.py`

These tasks intentionally share one file and must be handled by one worker sequentially.

## Task 3: Send Invite Cards As Plain Text

**Files:**
- Modify: `src/services/ops_bot.py`

**Finding:** `parse_mode="Markdown"` with raw names/emails/usernames can make Telegram reject cards.

Steps:

- [ ] Remove `parse_mode="Markdown"` from the `send_ops_keyboard(...)` call in `notify_invite`.
- [ ] Adjust `invite_card_text` so it does not rely on Markdown formatting. Replace backticked chat id text with plain `chat {tg_id}`.
- [ ] Keep the visible dev marker `LOCAL/DEV INVITE`.

## Task 4: Validate Batch Approval Domains

**Files:**
- Modify: `src/services/ops_bot.py`

**Finding:** Empty domain can approve all pending users.

Steps:

- [ ] Add a helper such as:

```python
def normalize_email_domain(value: str) -> str | None:
    domain = value.strip().lower().lstrip("@")
    if not domain or domain == "all":
        return None
    if "@" in domain or "." not in domain:
        return None
    labels = domain.split(".")
    if any(not label or label.startswith("-") or label.endswith("-") for label in labels):
        return None
    return domain
```

- [ ] Use it in `/approve_pending <domain>` before listing rows. If invalid, send `Usage: /approve_pending <email-domain>` and return.
- [ ] Use it again inside `approve_pending_domain(domain)`. If invalid, return `0` without mutating status.
- [ ] Keep `/users email all` behavior unchanged; that command is read-only and intentionally supports all emails.

## Task 5: Make Batch Preview Scope And Help Clear

**Files:**
- Modify: `src/services/ops_bot.py`

**Findings:** Batch preview only shows first 20 rows; Ops bot has no help/default response.

Steps:

- [ ] In `/approve_pending`, if `len(rows) > MAX_CHAT_ROWS`, include a line like `Showing first 20 of {len(rows)}. Confirm approves all {len(rows)} pending @{domain}.`
- [ ] If `len(rows) == 0`, send `No pending users for @{domain}.` and do not send a confirm button.
- [ ] Add `/start` and `/help` handling for read-allowlisted users:

```text
Ops commands:
/pending
/users [pending|approved|blocked|email <domain|all>]
/approve_pending <domain> (admins only)
```

- [ ] For unknown commands, send the same help text.

Verification command:

```powershell
C:\Users\leone\AppData\Local\Programs\Python\Python313\python.exe -m py_compile src/services/ops_bot.py
```
