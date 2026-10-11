#!/usr/bin/env bash
# Nightly Postgres backup → object storage.
#
# Drop this in /etc/cron.daily/ on the VPS (must be executable, no
# extension, owned by root). It dumps the database from the running
# docker container, compresses it, and ships the file to an rclone
# remote (configured separately with `rclone config`).
#
# Required environment (load from /opt/unisensory/.env or set in cron):
#   POSTGRES_USER, POSTGRES_DB             — match docker-compose.yml
#   BACKUP_REMOTE                          — e.g. "r2:unisensory-backups"
#   BACKUP_RETENTION_DAYS  (default 30)    — older dumps are deleted
#   COMPOSE_DIR            (default /opt/unisensory)

set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/opt/unisensory}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

if [[ -f "$COMPOSE_DIR/.env" ]]; then
  # shellcheck disable=SC1091
  set -a; source "$COMPOSE_DIR/.env"; set +a
fi

: "${POSTGRES_USER:?POSTGRES_USER must be set}"
: "${POSTGRES_DB:?POSTGRES_DB must be set}"
: "${BACKUP_REMOTE:?BACKUP_REMOTE must be set (e.g. r2:unisensory-backups)}"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
tmp_dir="$(mktemp -d)"
dump_file="$tmp_dir/unisensory-$stamp.sql.gz"

trap 'rm -rf "$tmp_dir"' EXIT

cd "$COMPOSE_DIR"

echo "[backup] dumping $POSTGRES_DB → $dump_file"
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec -T db \
  pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" \
  | gzip -9 > "$dump_file"

size="$(stat -c%s "$dump_file" 2>/dev/null || stat -f%z "$dump_file")"
echo "[backup] dump size: ${size} bytes"

echo "[backup] uploading → $BACKUP_REMOTE"
rclone copy "$dump_file" "$BACKUP_REMOTE" --quiet

echo "[backup] pruning dumps older than ${RETENTION_DAYS}d on remote"
rclone delete --min-age "${RETENTION_DAYS}d" "$BACKUP_REMOTE" --quiet || true

echo "[backup] done"
