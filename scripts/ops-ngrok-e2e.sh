#!/usr/bin/env bash
set -euo pipefail

cat <<'EOF'
Ops bot local callback workflow (manual by design):
1. Run FastAPI locally: uvicorn src.main:app --reload
2. In another shell: ngrok http 8000
3. Copy the HTTPS forwarding URL.
4. Add these overrides to backend .env.local (do not commit secrets):
   OPS_WEBHOOK_URL=https://<ngrok-host>/webhook/ops
   OPS_DEV_NOTIFICATIONS=true
5. Restart uvicorn so startup registers the Ops webhook.

This helper intentionally does not launch ngrok or edit .env.local automatically.
EOF
