#!/usr/bin/env bash
#
# Upsert one or more KEY=VALUE pairs from a local .env into the .env on the
# VPS, then restart api + worker so the new values take effect. Only touches
# the keys you name — everything else in the remote .env is left alone.
#
# Usage:
#   scripts/push-env-to-vps.sh KEY [KEY...]
#   scripts/push-env-to-vps.sh GITHUB_OAUTH_CLIENT_ID GITHUB_OAUTH_CLIENT_SECRET
#
# Env vars (all optional):
#   VPS_HOST      ssh target       (default: root@185.162.125.82)
#   VPS_ENV_PATH  remote directory (default: /opt/vig)
#   ENV_FILE      local .env path  (default: .env)

set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: $0 KEY [KEY...]" >&2
  exit 1
fi

VPS_HOST="${VPS_HOST:-root@185.162.125.82}"
VPS_DIR="${VPS_ENV_PATH:-/opt/vig}"
ENV_FILE="${ENV_FILE:-.env}"

[[ -f "$ENV_FILE" ]] || { echo "no $ENV_FILE here" >&2; exit 1; }

payload=""
for key in "$@"; do
  line=$(grep -E "^${key}=" "$ENV_FILE" | tail -n1) || { echo "skip $key — not set in $ENV_FILE" >&2; continue; }
  payload+="$line"$'\n'
done

[[ -n "$payload" ]] || { echo "nothing to push" >&2; exit 1; }

printf '%s' "$payload" | ssh "$VPS_HOST" "
    set -e
    remote_env='${VPS_DIR}/.env'
    touch \"\$remote_env\"
    while IFS= read -r line; do
      [[ -z \"\$line\" ]] && continue
      key=\${line%%=*}
      grep -vE \"^\${key}=\" \"\$remote_env\" > \"\$remote_env.tmp\" || true
      printf '%s\n' \"\$line\" >> \"\$remote_env.tmp\"
      mv \"\$remote_env.tmp\" \"\$remote_env\"
    done
    cd '${VPS_DIR}' && docker compose up -d api worker
  "

echo "✓ pushed $# value(s) → ${VPS_HOST}:${VPS_DIR}/.env, restarted api + worker"
