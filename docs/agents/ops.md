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

---

## 9. Database backup & rollback

Startup creates one WAL-consistent snapshot in `data/backups/` before any pending
migration can mutate an existing database. The ten newest migration snapshots are
retained. **Rolling back an image tag does not revert an applied schema; restoring
the SQLite file is the database rollback lever.**

From the deployment directory on the single VPS:

1. Stop every database writer before touching the file:
   ```bash
   docker compose stop api worker
   ```
2. Inspect the versioned snapshots and select the intended pre-migration file:
   ```bash
   ls -lt data/backups/jobs_v*_to_v*.db
   ```
3. Restore it (the command validates the backup before replacing `DB_PATH` and
   removes stale `jobs.db-wal` / `jobs.db-shm` sidecars):
   ```bash
   docker compose run --rm --no-deps \
     -e DB_PATH=/app/data/jobs.db api \
     python -m scripts.db_restore /app/data/backups/<backup-file>.db
   ```
4. Treat the script's `integrity_check=ok` and reported `user_version` as the
   required verification. On any non-zero exit, leave the writers stopped and
   investigate; an invalid backup does not clobber the live file.
5. Restart both writers and watch startup logs:
   ```bash
   docker compose up -d api worker
   docker compose logs --tail=100 api worker
   ```

Do not run the restore script while either writer is active.

---

## 10. Cloudflare Email Routing — retiring inbound mail (ADR-0060)

#607 shipped the newsletter digest as an inbound-mail pipeline: an Email
Routing **catch-all** on `leondev.xyz` fed the `ownix-email-digest` Worker,
which POSTed to `/webhook/email-digest`. ADR-0060 replaced that with
public-archive polling, and #612 deleted the repo half — `ops/email-worker/`,
`src/api/email_webhook.py`, the route, and `EMAIL_WEBHOOK_SECRET`.

The Cloudflare half needs dashboard access, so it is a human step. Run:

```bash
bash docs/ops/retire-email-routing.sh
```

Six stages, each opening the right dashboard page and confirming before
anything irreversible:

1. Delete the catch-all routing rule.
2. Delete the `ownix-email-digest` Worker (disposing of its `OWNIX_EMAIL_SECRET`).
3. Verify the destination inbox.
4. Create `contact.me@leondev.xyz` → destination (a **specific** address).
5. Strip the dead `EMAIL_WEBHOOK_SECRET` from `.env`.
6. Verify delivery and, separately, that the catch-all is really gone.

Two things about this order are deliberate and worth not "improving":

- **Catch-all before Worker.** The API route is already deleted, so every
  message the catch-all currently accepts is handed to a Worker that fails.
  Removing the Worker first leaves a window where mail is accepted and then
  black-holed; removing the rule first makes it bounce, which is honest and
  visible to the sender.
- **The bounce test is the real check.** Confirming `contact.me@` delivers only
  proves the new rule works. Sending to a random address at the domain and
  getting a bounce is what proves the catch-all is gone.

**Keep it a specific address, never a catch-all.** Catch-all domains are
rejected by third-party signup validators — one of the two walls that made
#607 impossible to onboard — and they collect spam for every address anyone
guesses.

`contact.me@leondev.xyz` is the public contact on the privacy, terms and
accessibility pages. Do not publish it until stage 6 passes; an address that
does not deliver is worse than none.
