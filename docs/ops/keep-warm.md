# Keep-warm: eliminating the cold-start spike

**Issue:** [#176](https://github.com/Leon-87-7/vig/issues/176)  
**Related:** [CONTEXT.md "Feed freshness model"](../../CONTEXT.md) (line 92)

---

## The problem

| Request type              | Observed latency |
|---------------------------|-----------------|
| First request after idle  | ~5.9 s (cold)   |
| Steady-state (warm)       | ~0.25 s         |
| Localhost (no tunnel)     | ~0.23 s         |

The 5.9 s cold-start is **not** query latency — the database is fast (175
rows, `idx_jobs_chat_id`, one Redis GET). The spike is on the
**self-hosted side**: the Cloudflare tunnel reconnecting, the container
resuming from a low-power state, or the process restarting after idle.

As documented in [CONTEXT.md line 92](../../CONTEXT.md), the backend fix is
a **keep-warm ping** (`GET /health` every 3–5 min). The dashboard's own
polling keeps the backend warm while the dashboard tab is open, so cold
start only ever bites the **first load after a long idle**.

---

## Likely root causes

1. **Cloudflare tunnel idle-timeout** — the `cloudflared` daemon may close
   inactive connections after a period of inactivity, adding a TCP/TLS
   reconnect on the next request.
2. **Container or host sleep** — the Docker container (or the underlying
   host machine) may enter a low-power/sleep state after extended idle.
3. **Process restart** — if the container is configured to restart on crash
   or scheduled maintenance, the first request after restart pays startup
   cost (FastAPI lifespan, DB `init_db`, webhook registration).

A keep-warm ping prevents all three by ensuring at least one request
traverses the tunnel every few minutes.

---

## Mechanisms

### (a) GitHub Actions cron — committed, best-effort

`.github/workflows/keep-warm.yml` runs every 5 minutes:

```yaml
on:
  schedule:
    - cron: "*/5 * * * *"
```

Curl command used:

```bash
curl -sS --fail \
  --max-time 15 \
  --retry 2 \
  --retry-delay 3 \
  --retry-connrefused \
  -w "%{http_code}  time_total=%{time_total}s  time_connect=%{time_connect}s" \
  -o /dev/null \
  https://api.leondev.xyz/health
```

**Reliability caveat — read this:** GitHub Actions scheduled workflows have
a **5-minute minimum interval** and are **frequently delayed 5–15+ minutes**
under load. GitHub can also skip a run entirely if the queue is congested.
This means the Actions cron is a **best-effort backup warmer**, not a
guaranteed <5-min keep-warm. Use it as a belt to the external monitor's
suspenders, not as a primary mechanism.

---

### (b) External uptime monitor — RECOMMENDED

An external service pings the endpoint independently of GitHub's scheduler
queue and is far more reliable. Either of these works (both free tiers are
sufficient):

**cron-job.org** (recommended — free, 1-min minimum, no account required for
basic use):

1. Go to <https://cron-job.org> and create a free account.
2. Create a new cron job:
   - **URL:** `https://api.leondev.xyz/health`
   - **Interval:** every **3 minutes**
   - **HTTP method:** GET
   - **Expected HTTP status:** 200
3. Enable notifications on failure (optional but useful).

**UptimeRobot** (alternative — free tier, 5-min minimum on free plan):

1. Go to <https://uptimerobot.com> and sign in.
2. Add a monitor:
   - **Monitor type:** HTTP(s)
   - **URL:** `https://api.leondev.xyz/health`
   - **Monitoring interval:** 5 minutes (free tier limit)

Either service gives you a public status page and email/Telegram alerts if
the health check starts failing — free observability on top of the warm-up.

---

## The `/health` endpoint

Confirmed unauthenticated in `src/main.py` (lines 83-85):

```python
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

No auth middleware applies — it is intentionally open per CONTEXT.md:
> `/webhook` (Telegram secret-token auth) and `/health` stay open

---

## Verifying warmth

After the tunnel has been idle for several minutes, run:

```bash
# Should be ~0.25 s warm, ~5.9 s cold
curl -w "time_total=%{time_total}s\n" -o /dev/null -s https://api.leondev.xyz/health
```

Run it twice in quick succession — the second call should be warm (~0.25 s)
even if the first was cold, confirming the tunnel is now active.

---

## Why the dashboard's own polling helps

Once the dashboard tab is open, the [Feed freshness model](../../CONTEXT.md)
(CONTEXT.md line 92) keeps the backend warm:

- A **10 s in-flight poll** fires while any job is pending/processing.
- A **~2 min backstop poll** runs while idly browsing.
- **Refetch-on-focus** fires when the tab regains visibility.

All of these hit the API, which keeps the tunnel active. The external
keep-warm monitor matters only for the cold start on the _very first_ open
after a long idle period (e.g. waking up in the morning to check new jobs).
