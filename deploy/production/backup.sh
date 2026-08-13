#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"

cd "$DEPLOY_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "缺少 $ENV_FILE，无法执行生产备份。" >&2
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

if ! compose ps --status running --services | grep -qx backend; then
  echo "Backend 容器未运行，无法执行 SQLite 在线备份。" >&2
  exit 1
fi

mkdir -p backups
chmod 700 backups
backup_name="spotify-stats-$(date -u +%Y%m%dT%H%M%SZ).db"

compose exec -T backend python - "/var/backups/spotify-stats/$backup_name" <<'PY'
import sqlite3
import sys

source = sqlite3.connect("/app/data/spotify_stats.db", timeout=30)
target = sqlite3.connect(sys.argv[1])
with target:
    source.backup(target)
integrity = target.execute("PRAGMA integrity_check").fetchone()[0]
target.close()
source.close()
if integrity != "ok":
    raise SystemExit(f"backup integrity_check failed: {integrity}")
PY

retention_days="$(sed -n 's/^BACKUP_RETENTION_DAYS=//p' "$ENV_FILE" | tail -n 1)"
retention_days="${retention_days:-14}"
if [[ ! "$retention_days" =~ ^[0-9]+$ ]]; then
  echo "BACKUP_RETENTION_DAYS 必须是非负整数。" >&2
  exit 1
fi

find backups -maxdepth 1 -type f -name 'spotify-stats-*.db' -mtime "+$retention_days" -delete
echo "SQLite 备份完成：$DEPLOY_DIR/backups/$backup_name"
