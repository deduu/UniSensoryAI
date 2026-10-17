# Deployment — Self-managed VPS + Cloudflare Pages

This folder bundles the production overlay for hosting UniSensoryAI on a
single small VPS. The frontend ships separately to Cloudflare Pages.

For the local four-service development stack, use `docker compose up --build`;
see the root README. The production overlay requires Docker Compose 2.24.4+
for explicit port/mount replacement. It excludes the local Vite service and
source/data bind mounts, keeps the production uploads volume, and builds the
`runtime` image target. Apply migrations with the command below before initial
API startup can complete. Cloudflare Pages still hosts the production frontend.

**Target cost:** ~$5/mo VPS + ~$10/yr domain + variable VLM token spend.

## Architecture
- **Frontend** (`frontend/`) — Vite SPA built to `dist/`, deployed to
  Cloudflare Pages (free, global CDN, automatic TLS).
- **Backend** — FastAPI on `api.<your-domain>`, running via
  `docker-compose.prod.yml` on a single Hetzner CX22 (or similar). Caddy
  terminates TLS and reverse-proxies to the API. Postgres and Redis run
  alongside; uploads land on a docker volume.

## Files in this folder
- `Caddyfile` — reverse-proxy config. SSE-safe (`flush_interval -1`).
- `backup.sh` — nightly `pg_dump` → rclone remote (R2 / B2 / S3).

## First-time deployment

### 1. VPS prep (one-time)
```bash
ssh root@<vps-ip>
adduser deploy && usermod -aG sudo deploy
apt-get update && apt-get install -y docker.io docker-compose-plugin ufw rclone
ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
systemctl enable --now docker
usermod -aG docker deploy
```

### 2. DNS
Point `api.example.com` (A record) at the VPS IP. **Disable Cloudflare's
orange-cloud proxy** for this record — CF's free plan does not reliably
pass through SSE streams. The frontend record (`app.example.com`)
goes to Cloudflare Pages, proxied is fine there.

### 3. Clone and configure
```bash
sudo mkdir -p /opt/unisensory && sudo chown deploy:deploy /opt/unisensory
git clone <repo-url> /opt/unisensory
cd /opt/unisensory
cp .env.example .env
# Then edit .env — at minimum set:
#   POSTGRES_PASSWORD, JWT_SECRET_KEY, SESSION_SECRET,
#   AUTH_ENABLED=true, COOKIE_SECURE=true,
#   FRONTEND_URL=https://app.example.com,
#   OAUTH_REDIRECT_BASE_URL=https://api.example.com,
#   CORS_ALLOW_ORIGINS=https://app.example.com,
#   API_DOMAIN=api.example.com, ACME_EMAIL=you@example.com,
#   OAUTH_GOOGLE_CLIENT_ID/SECRET (and/or GITHUB), OPENAI_API_KEY
```

> **Lockfile note** — `pyproject.toml` moved heavy ML libs to a
> `local-vlm` extra. If the build complains the lockfile is stale,
> regenerate it locally with `uv lock` and commit the new `uv.lock`.

### 4. Bring it up
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# Run migrations once the DB is healthy:
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    alembic upgrade head
```

Caddy will fetch a Let's Encrypt cert for `$API_DOMAIN` on first request.

### 5. Frontend on Cloudflare Pages
1. CF Pages → Create project → connect this GitHub repo.
2. Build settings:
   - Root directory: `frontend`
   - Build command: `npm ci && npm run build`
   - Build output: `dist`
3. Environment variables (Production):
   - `VITE_API_BASE=https://api.example.com`
4. After first build, add the custom domain `app.example.com`.

The `frontend/public/_redirects` file handles SPA fallback.

### 6. Nightly backups
```bash
rclone config         # configure a remote, e.g. "r2:unisensory-backups"
sudo cp deploy/backup.sh /etc/cron.daily/unisensory-backup
sudo chmod +x /etc/cron.daily/unisensory-backup
# Test it once by hand:
sudo BACKUP_REMOTE=r2:unisensory-backups /etc/cron.daily/unisensory-backup
```

## Verification checklist
- `curl https://api.example.com/` returns 200 with valid TLS.
- `curl -N https://api.example.com/v1/jobs/<id>/stream` shows tokens
  arriving **incrementally** (proves SSE isn't buffered).
- Visit `https://app.example.com`, log in via Google, upload a small
  PDF, stream a chat completion — UI updates token-by-token.
- `sudo reboot` the VPS; after it comes back the app, DB rows, and
  uploaded files are all still present.
- Run `backup.sh` manually, then restore the dump into a throwaway
  container to confirm the backup is valid:
  ```bash
  gunzip < unisensory-*.sql.gz | docker run --rm -i -e POSTGRES_PASSWORD=x \
      -v $PWD:/dump postgres:17-alpine psql -U postgres -d postgres
  ```

## Upgrading
```bash
cd /opt/unisensory
git pull
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    alembic upgrade head
```

## When to outgrow this setup
- Sustained CPU above ~80% on the VPS → vertical bump to CPX21 ($7/mo)
  before splitting services.
- Frequent multi-GB uploads → move `data/uploads` writes behind an
  S3-compatible store (Cloudflare R2). The change is local to
  `src/api/server.py` upload handler; introduce a `BaseObjectStore`
  abstraction and swap implementations.
- Need horizontal scaling → set `QUEUE_BACKEND=redis`, run a second
  `api` replica, put Caddy in front of both.
