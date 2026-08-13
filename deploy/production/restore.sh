#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
BACKUP_PATH="${1:-}"
CONFIRM="${2:-}"

cd "$DEPLOY_DIR"

if [[ -z "$BACKUP_PATH" || "$CONFIRM" != "--confirm" ]]; then
  echo "用法：$0 <备份数据库路径> --confirm" >&2
  exit 2
fi

if [[ ! -f "$BACKUP_PATH" ]]; then
  echo "备份不存在：$BACKUP_PATH" >&2
  exit 1
fi

python3 - "$BACKUP_PATH" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    result = conn.execute("PRAGMA integrity_check").fetchone()[0]
finally:
    conn.close()
if result != "ok":
    raise SystemExit(f"backup integrity_check failed: {result}")
PY

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

if compose ps --status running --services | grep -qx backend; then
  "$DEPLOY_DIR/backup.sh"
fi

compose stop backend
install -m 600 "$BACKUP_PATH" data/spotify_stats.db.restore
mv data/spotify_stats.db.restore data/spotify_stats.db
rm -f data/spotify_stats.db-wal data/spotify_stats.db-shm

mode="$(sed -n 's/^DEPLOYMENT_MODE=//p' "$ENV_FILE" | tail -n 1)"
case "$mode" in
  full) services=(backend web) ;;
  showcase) services=(backend public-web) ;;
  dual) services=(backend web public-web) ;;
  *)
    echo "DEPLOYMENT_MODE 无效：$mode" >&2
    exit 1
    ;;
esac

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile "$mode" \
  up -d "${services[@]}"

if "$DEPLOY_DIR/verify.sh"; then
  echo "数据库恢复并按 $mode 模式重新启动完成：$BACKUP_PATH"
  exit 0
fi

echo "恢复后健康检查失败，需要人工检查。" >&2
exit 1
