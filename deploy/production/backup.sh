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

mkdir -p backups
chmod 700 backups
if [[ "${1:-}" == "--scheduled" ]]; then
  # The daily maintenance timer makes one backup per Sunday-to-Saturday week.
  # A missed Sunday is caught up on the next daily run.
  due="$(python3 - "$DEPLOY_DIR/backups" <<'PY'
import datetime as dt
import re
import sys
from pathlib import Path

now = dt.datetime.now()
start = (now - dt.timedelta(days=(now.weekday() + 1) % 7)).replace(
    hour=0, minute=0, second=0, microsecond=0
).timestamp()
recent = any(
    p.is_file() and not p.is_symlink() and p.stat().st_mtime >= start
    for p in Path(sys.argv[1]).iterdir()
    if re.fullmatch(r"spotify-stats-[0-9]{8}T[0-9]{6}Z\.db(?:\.gz)?", p.name)
)
print("skip" if recent else "due")
PY
)"
  if [[ "$due" == "skip" ]]; then
    echo "本周已有普通备份，跳过备份生成。"
    exit 0
  fi
elif [[ $# -ne 0 ]]; then
  echo "用法：backup.sh [--scheduled]" >&2
  exit 2
fi

if ! compose ps --status running --services | grep -qx backend; then
  echo "Backend 容器未运行，无法执行 SQLite 在线备份。" >&2
  exit 1
fi

backup_name="${SPOTIFY_STATS_BACKUP_NAME:-spotify-stats-$(date -u +%Y%m%dT%H%M%SZ).db}"
if [[ ! "$backup_name" =~ ^spotify-stats-[A-Za-z0-9._-]+\.db$ ]]; then
  echo "SPOTIFY_STATS_BACKUP_NAME 必须是安全的 spotify-stats-*.db 文件名。" >&2
  exit 2
fi
if [[ -e "backups/$backup_name" || -e "backups/$backup_name.gz" ]]; then
  echo "备份目标已存在，拒绝覆盖：$DEPLOY_DIR/backups/$backup_name" >&2
  exit 1
fi

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

# Ordinary weekly snapshots are self-contained; compress only after validation.
# Named release/import snapshots keep their paths for the existing restore flow.
if [[ "$backup_name" =~ ^spotify-stats-[0-9]{8}T[0-9]{6}Z\.db$ ]]; then
  gzip -n -- "backups/$backup_name"
  backup_name="$backup_name.gz"
fi

# Rotate only ordinary snapshots, and only after the new backup succeeded.
python3 - "$DEPLOY_DIR/backups" <<'PY'
import re
import sys
from pathlib import Path

ordinary = [
    p for p in Path(sys.argv[1]).iterdir()
    if p.is_file() and not p.is_symlink()
    and re.fullmatch(r"spotify-stats-[0-9]{8}T[0-9]{6}Z\.db(?:\.gz)?", p.name)
]
for path in sorted(ordinary, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)[2:]:
    path.unlink()
PY
echo "SQLite 备份完成：$DEPLOY_DIR/backups/$backup_name"
