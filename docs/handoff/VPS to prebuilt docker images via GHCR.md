## Future Improvement: Move VPS Deployments to Prebuilt Docker Images via GHCR

### Goal

Replace the current VPS deployment flow:

```text
GitHub Action
  → SSH into VPS
  → git fetch/reset
  → docker compose up -d --build
```

with an image-based deployment flow:

```text
GitHub Action
  → build Docker images
  → push images to GitHub Container Registry
  → SSH into VPS
  → docker compose pull
  → docker compose up -d
```

### Why

The current setup works, but it builds Docker images directly on the VPS. That is acceptable for now, but it has downsides:

- Uses CPU/RAM on the small VPS during deploys.
- Slower deployments.
- Harder rollback.
- Deployment depends on the VPS being able to build successfully.
- Every deploy rebuilds locally instead of using immutable versioned artifacts.

### Desired End State

GitHub Actions should build and publish images to GHCR:

- `ghcr.io/leon-87-7/vig-api:<sha>`
- `ghcr.io/leon-87-7/vig-transcript:<sha>`
- optionally `ghcr.io/leon-87-7/vig-api:latest`
- optionally `ghcr.io/leon-87-7/vig-transcript:latest`

The VPS should only pull and restart containers.

### Required Changes

#### 1. Update `docker-compose.yml`

Replace local builds:

```yaml
build: .
image: vig-app
```

with GHCR images:

```yaml
image: ghcr.io/leon-87-7/vig-api:latest
```

For `transcript-service`, replace:

```yaml
build:
  context: .
  dockerfile: Dockerfile.transcript
```

with:

```yaml
image: ghcr.io/leon-87-7/vig-transcript:latest
```

#### 2. Update VPS deploy script

Current deploy script builds locally.

Replace with something like:

```bash
#!/usr/bin/env bash
set -euo pipefail

cd /opt/vig

echo "==> Fetching latest compose/config"
git fetch origin main
git reset --hard origin/main

echo "==> Pulling latest images"
docker compose pull

echo "==> Restarting containers"
docker compose up -d

echo "==> Cleaning unused Docker images"
docker image prune -f

echo "==> Current status"
docker compose ps
```

#### 3. Update GitHub Actions workflow

Workflow should:

1. Checkout repo.
2. Login to GHCR.
3. Build API image from `Dockerfile`.
4. Build transcript image from `Dockerfile.transcript`.
5. Push both images.
6. SSH into VPS and run `/opt/deploy-vig.sh`.

Use commit SHA tags for traceability and optionally `latest` for simple deploys.

#### 4. VPS GHCR Access

If the repository/package is public, the VPS may be able to pull without auth.

If GHCR requires auth, configure Docker login on the VPS:

```bash
echo "<GITHUB_PAT>" | docker login ghcr.io -u Leon-87-7 --password-stdin
```

Use a minimal PAT with package read access.

### Acceptance Criteria

- Pushing to `main` builds Docker images in GitHub Actions.
- Images are pushed successfully to GHCR.
- VPS deploy does not run `docker compose up -d --build`.
- VPS deploy uses `docker compose pull` followed by `docker compose up -d`.
- `docker compose ps` shows all services healthy/running after deploy.
- `curl https://api.leondev.xyz/health` returns `{"status":"ok"}`.
- Telegram bot still responds after deployment.
- Rollback is possible by changing image tag to a previous commit SHA.

### Not Needed Yet

Do not migrate SQLite to Postgres as part of this issue.

Do not replace Redis with Upstash as part of this issue.

Do not add Kubernetes, Docker Swarm, or any orchestration layer.
