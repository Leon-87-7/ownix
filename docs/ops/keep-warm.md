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

## Mechanism: external uptime monitor (cron-job.org)

The keep-warm ping is an **external uptime monitor**, not an in-repo job.
A purpose-built pinger delivers a reliable sub-5-min cadence; an in-repo
GitHub Actions `schedule` does **not** (5-min floor, runs routinely delayed
5–15+ min or dropped under load, and GitHub auto-disables scheduled
workflows after 60 days of repo inactivity — the opposite of what an
always-on warmer needs). So this lives outside the repo, by design.

### Live setup — [cron-job.org](https://cron-job.org)

Free, 1-min minimum interval, with failure/recovery email alerts.

1. Create a free account and add a cron job:
   - **Title:** `vig-api keep-warm`
   - **URL:** `https://api.leondev.xyz/health`
   - **HTTP method:** GET · **Expected status:** 200
   - **Interval:** every **2 minutes** (`*/2 * * * *`)
   - **Schedule expires:** off · **Save responses in job history:** on
     (handy for eyeballing per-ping latency)
2. Under **Notify me when…** enable:
   - **execution fails** — *Notify after **3** subsequent failures* (a single
     failed ping is usually a transient blip; 3 in a row means real downtime).
   - **succeeds after it failed before** — the "recovered" alert.
   - **the cronjob will be disabled because of too many failures** — **the
     important one**: it warns you before cron-job.org auto-disables the job,
     so a dead warmer can't silently let cold starts creep back.
   - *(TLS-expiry alert can stay off — the `api.leondev.xyz` cert is
     auto-renewed by Cloudflare.)*

This doubles as a free downtime monitor for `api.leondev.xyz`.

**Alternative:** UptimeRobot also works (HTTP(s) monitor, same URL) but its
free tier floors at a 5-min interval.

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
