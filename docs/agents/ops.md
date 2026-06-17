# Ops Runbook

Operational checklist for deploying and maintaining **vig** (Video Intelligence Gateway).
This supplements the step-by-step commands in `docs/seed/PRD.md §5.1` (local dev) and `§5.2` (VPS).

---

## 1. Google Drive — folder permissions

For each Drive folder, share it with the **service account email** (found in `service_account.json` under the `client_email` key) and grant **Editor** access.

| Env var                      | Purpose                                 |
|------------------------------|-----------------------------------------|
| `GOOGLE_DRIVE_FOLDER_SHORT`  | Short-video enrichment outputs          |
| `GOOGLE_DRIVE_FOLDER_LONG`   | Long-video enrichment outputs           |
| `GOOGLE_DRIVE_FOLDER_BRAIN`  | Second Brain graph files                |
| `GOOGLE_DRIVE_FOLDER_PRD`    | Mini-PRD documents                      |

**How to share:** open the folder in Google Drive → Share → paste the service account email → set role to **Editor** → Send.

**How to verify:** the `init_db` pre-flight check writes a sentinel file to each configured folder on startup; watch the startup logs for `drive.preflight.ok` / `drive.preflight.fail`.

---

## 2. Google Sheets — service account access

Share each sheet with the service account email (**Editor** role).

| Env var                   | Purpose                         |
|---------------------------|---------------------------------|
| `GOOGLE_SHEETS_ID_SHORT`  | Short-video job log             |
| `GOOGLE_SHEETS_ID_LONG`   | Long-video job log              |
| `GOOGLE_SHEETS_ID_PRD`    | Mini-PRD job log                |

Obtain the sheet ID from the URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`.

---

## 3. Telegram webhook URL

### Local dev (Cloudflare Tunnel)
```bash
cloudflared tunnel --url http://localhost:8000
# copy the assigned HTTPS hostname, e.g. https://abc-def-123.trycloudflare.com

curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=https://abc-def-123.trycloudflare.com/webhook" \
     -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

### Production (VPS)
```bash
curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook" \
     -d "url=https://your-domain.com/webhook" \
     -d "secret_token=$TELEGRAM_WEBHOOK_SECRET"
```

Confirm registration:
```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getWebhookInfo"
```

---

## 4. Telegram secret token rotation

The `TELEGRAM_WEBHOOK_SECRET` is sent by Telegram as the `X-Telegram-Bot-Api-Secret-Token` header and verified by the webhook handler. To rotate:

1. Generate a new secret (≥32 random characters, no whitespace).
2. Update `.env` with the new value.
3. Re-register the webhook with the new secret (see §3 above).
4. Restart the service.

There is a brief window between steps 3 and 4 where the old process is still running with the old secret — keep the rotation window short, or schedule a maintenance window.

---

## 5. Telegram sticker file_ids

Two stickers signal failure states to the user. To obtain their `file_id`:

1. Forward the sticker to **@userinfobot** in Telegram.
2. The bot replies with metadata including `file_id`.
3. Copy the `file_id` value into `.env`.

| Env var                          | Trigger                              |
|----------------------------------|--------------------------------------|
| `TELEGRAM_STICKER_GEMINI_FAIL`   | Gemini enrichment fails all retries  |
| `TELEGRAM_STICKER_DRIVE_FAIL`    | Google Drive upload fails            |

If either var is empty, the bot falls back to a plain-text error message — no sticker is required for the service to function.

---

## 6. BotFather — command registration

Register slash commands once so Telegram clients show autocomplete. Open a chat with **@BotFather**, run `/setcommands`, select your bot, then paste exactly:

```
spec - Generate PRD for a long video (last 4 chars of job ID, optional intent text)
cancel - Cancel pending intent capture
find - Search Second Brain links by query
rebuild-graph - Rebuild Second Brain graph from scratch
```

Commands work without this step; registration only adds the autocomplete UI.

---

## 7. GEMINI_BRAIN_API_KEY provisioning

The Second Brain uses a **separate** Gemini API key (`GEMINI_BRAIN_API_KEY`) to isolate its embedding and generation quota from the pipeline keys (`GEMINI_FREE_API_KEY`, `GEMINI_PAID_API_KEY`).

Obtain a dedicated key from [aistudio.google.com](https://aistudio.google.com) → API keys → Create API key, then set it in `.env`. If left empty, the brain module falls back to `GEMINI_FREE_API_KEY` (not recommended in production).

---

## 8. Keep-warm — eliminating cold-start latency

See **[`docs/ops/keep-warm.md`](../ops/keep-warm.md)** for the full runbook.

**Summary:** the first request after a long idle period (~5.9 s) is caused
by the Cloudflare tunnel / container sleeping — not query latency. A
`GET /health` ping every couple of minutes keeps it warm. The mechanism is
an **external uptime monitor** (cron-job.org, every 2 min) hitting
`https://api.leondev.xyz/health` — an in-repo GitHub Actions cron was
considered and rejected (5-min floor, unreliable timing, auto-disables
after 60 days idle). See the runbook for the exact cron-job.org config.
