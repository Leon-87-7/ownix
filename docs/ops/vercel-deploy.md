# Deploying the `web` frontend to Vercel

The Next.js frontend (`web/`) can run on Vercel to offload its build/serve cost from
the local machine. The backend (`api`, `worker`, `transcript-service`, `redis`) keeps
running in Docker on the host — Vercel hosts **only** the frontend.

## Why this works without touching auth

The browser only ever talks to **one origin** (`app.leondev.xyz`). Next.js rewrites
`/api/*` server-side to the FastAPI backend (`web/next.config.js`), so the
`vig_session` cookie — set with `httponly; secure; samesite=lax` and **no `domain`**
(`src/api/auth.py`) — is bound to the frontend's own host. Keeping the rewrite proxy
on Vercel preserves this: single origin, no CORS, cookie unchanged.

```
browser ──HTTPS──> app.leondev.xyz (Vercel: Next.js + middleware)
                        │  /api/* rewrite (server-side proxy)
                        ▼
                   api.leondev.xyz (Cloudflare Tunnel) ──> host :8000 (FastAPI)
                                                            + worker + redis + transcript (local, unchanged)
```

## Prerequisite — expose the API publicly

Vercel runs the `/api/*` rewrite in its cloud, so the Docker-internal
`http://api:8000` is unreachable. The API must be reachable over **public HTTPS**.

Recommended: **Cloudflare Tunnel** mapping `api.leondev.xyz → http://localhost:8000`
(no port-forwarding, free TLS, hides the home IP). Any reverse proxy already fronting
`app.leondev.xyz` can host this route instead. See
[Cloudflare Tunnel setup](#cloudflare-tunnel-setup-apileondevxyz) below.

> Until `api.leondev.xyz` resolves and serves the API over HTTPS, the Vercel
> deployment cannot reach the backend. Do this first.

## One-time setup

### 1. Create the Vercel project

- Import the `Leon-87-7/vig` repo.
- **Root Directory = `web`** (repo root is the Python project; Next.js lives in `web/`).
- Framework auto-detects as Next.js (pinned in `web/vercel.json`).

### 2. Environment variables (Vercel → Project → Settings → Environment Variables)

| Variable                            | Value                     | Notes                                                             |
| ----------------------------------- | ------------------------- | ----------------------------------------------------------------- |
| `API_INTERNAL_URL`                  | `https://api.leondev.xyz` | proxy target for `/api/*`                                         |
| `NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` | `photo2urlbot`            | `NEXT_PUBLIC_` → baked at **build** time; set before first deploy |

### 3. DNS

- `app.leondev.xyz` → Vercel (CNAME / Vercel-managed domain).
- `api.leondev.xyz` → Cloudflare Tunnel (the prerequisite above).
- **Do not change the Telegram bot domain.** BotFather `/setdomain` must stay
  `app.leondev.xyz` — the Login Widget validates the page domain.

## Verify after deploy

1. Visit `app.leondev.xyz` → redirected to `/login`.
2. Telegram login → `vig_session` cookie set on `app.leondev.xyz`.
3. Dashboard loads; a few `/api/*` reads (jobs, spaces, prompts) succeed.

## Cut over local Docker (only after Vercel is verified)

Stop running the frontend container locally — see the marked block in
`docker-compose.yml` (the `web` service). Remove that service and the now-unused
`NEXT_PUBLIC_TELEGRAM_BOT_USERNAME` build arg, then:

```sh
docker compose up -d --remove-orphans   # drops vig-web
```

The host no longer builds/serves Next.js; everything else is unchanged.

## Cloudflare Tunnel setup (`api.leondev.xyz`)

Goal: a public HTTPS hostname `api.leondev.xyz` that forwards to the FastAPI
container, with no inbound ports opened on the host. Pick **one** of the two styles.

### Option A — token tunnel as a Docker service (recommended)

Configure the tunnel in the Cloudflare **Zero Trust → Networks → Tunnels** dashboard,
then run the connector as a container joined to `vig-network` so it reaches the API at
`http://api:8000` directly (no host port needed).

1. Dashboard → create a tunnel (named e.g. `vig-api`) → copy the **token**.
2. Add a **Public Hostname**: `api.leondev.xyz` → service `http://api:8000`.
3. Put the token in `.env`:
   ```dotenv
   CLOUDFLARE_TUNNEL_TOKEN=eyJ... # from the dashboard
   ```
4. Add this service to `docker-compose.yml` (gated — add when you're ready to expose):
   ```yaml
   cloudflared:
     image: cloudflare/cloudflared:latest
     container_name: vig-cloudflared
     command: tunnel --no-autoupdate run --token ${CLOUDFLARE_TUNNEL_TOKEN}
     restart: unless-stopped
     depends_on:
       - api
     networks:
       - vig-network
   ```
5. `docker compose up -d cloudflared` → the tunnel registers the DNS automatically.

### Option B — locally-managed (config file)

Run `cloudflared` on the host pointing at the published API port (`localhost:8000`).

```sh
cloudflared tunnel login                       # browser auth, writes cert.pem
cloudflared tunnel create vig-api              # writes <TUNNEL_ID>.json credentials
cloudflared tunnel route dns vig-api api.leondev.xyz
cloudflared tunnel run vig-api                 # uses the config.yml below
```

`config.yml` (default location: `~/.cloudflared/config.yml`, or
`%USERPROFILE%\.cloudflared\config.yml` on Windows):

```yaml
tunnel: vig-api
credentials-file: <path-to>/<TUNNEL_ID>.json

ingress:
  - hostname: api.leondev.xyz
    service: http://localhost:8000
  - service: http_status:404
```

### Security note — do NOT put Cloudflare Access on `api.leondev.xyz`

The API is already gated: `SessionMiddleware` returns 401 on `/api/*` without a valid
`vig_session` cookie (`src/auth/middleware.py`); `/api/auth/telegram` is HMAC-verified;
`/webhook` and `/health` are intentionally open. The session gate IS the protection.

If you front `api.leondev.xyz` with Cloudflare **Access**, it will block Vercel's
server-side proxy requests (they carry no Access cookie) and break every `/api/*` call.
Leave Access off this hostname, or use an Access **service token** wired into the proxy.

## Things to watch

- **Vercel proxy timeout** — external rewrites proxy through Vercel with a ~30s
  ceiling. Fine for polling/CRUD; verify the longest `/api/*` call (e.g. any
  streaming/SSE or long enrichment) stays under it, or route that one differently.
- **The host must stay on** — Vercel removes only the frontend load. The
  API/worker/redis still run locally and answer every proxied request.
- `output: "standalone"` in `next.config.js` is for the Docker image; Vercel ignores
  it harmlessly — leave it.

# Your flip-the-switch sequence, when ready

1. Cloudflare Zero Trust → Networks → Tunnels → create vig-api → copy token.
2. Add public hostname api.leondev.xyz → http://api:8000.
3. Put the token in .env (CLOUDFLARE_TUNNEL_TOKEN=…).
4. Uncomment the cloudflared block in docker-compose.yml.
5. docker compose up -d cloudflared → DNS self-registers; verify https://api.leondev.xyz/health.
6. Then do the Vercel project + env vars + app.leondev.xyz DNS, verify, and finally remove the gated web service.
