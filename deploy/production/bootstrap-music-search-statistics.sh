#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$DEPLOY_DIR/.env"
COMPOSE_FILE="$DEPLOY_DIR/compose.yml"
PREPARE_HELPER="$DEPLOY_DIR/prepare-music-search-bootstrap-resume.py"
VALIDATOR="$DEPLOY_DIR/validate-music-search-preflight.py"
CAPACITY_PROBE="$DEPLOY_DIR/music_search_preflight_capacity.py"
revision=""
json_report_input=""

usage() {
  cat >&2 <<'EOF'
用法：bootstrap-music-search-statistics.sh --revision <40位commit SHA> \
  --json-report <全新报告路径>

只对 SQLite Online Backup 副本执行一次性六变体统计构建，可从同源的部分成果续建。
脚本不会停止/重启生产容器、修改 .env、替换生产数据库或执行部署。
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --revision)
      revision="${2:-}"
      shift 2
      ;;
    --json-report)
      json_report_input="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

if [[ ! "$revision" =~ ^[0-9a-f]{40}$ || -z "$json_report_input" ]]; then
  usage
  exit 2
fi
if [[ ! -f "$ENV_FILE" || ! -f "$PREPARE_HELPER" || ! -f "$VALIDATOR" || \
      ! -f "$CAPACITY_PROBE" ]]; then
  echo "缺少生产环境或搜索 bootstrap 辅助文件。" >&2
  exit 1
fi

resolve_output_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).expanduser()
parent = raw.parent.resolve(strict=True)
if not raw.name or raw.name in {".", ".."}:
    raise SystemExit(1)
print(parent / raw.name)
PY
}

if ! json_report_path="$(resolve_output_path "$json_report_input")"; then
  echo "JSON 报告父目录不存在或路径无法解析。" >&2
  exit 2
fi
if [[ -e "$json_report_path" ]]; then
  echo "JSON 报告已存在，拒绝覆盖。" >&2
  exit 2
fi

get_env() {
  sed -n "s/^${1}=//p" "$ENV_FILE" | tail -n 1
}

registry="$(get_env TCR_REGISTRY)"
registry="${registry:-ccr.ccs.tencentyun.com}"
namespace="$(get_env TCR_NAMESPACE)"
namespace="${namespace:-teacher-honor}"
repository="$(get_env API_REPOSITORY)"
repository="${repository:-spotify-stats-api}"
image="$registry/$namespace/$repository:$revision"
if [[ ! "$image" =~ ^[A-Za-z0-9._/@:-]+$ ]]; then
  echo "目标 API 镜像引用无效。" >&2
  exit 2
fi

cd "$DEPLOY_DIR"
umask 077
mkdir -p backups
chmod 700 backups
lock_dir="$DEPLOY_DIR/backups/.music-search-bootstrap.lock"
if ! mkdir "$lock_dir"; then
  echo "已有音乐搜索统计 bootstrap 正在运行，拒绝并发。" >&2
  exit 1
fi

work_dir="$(mktemp -d "$DEPLOY_DIR/backups/.music-search-bootstrap.XXXXXX")"
container_name="spotify-stats-search-bootstrap"
rebuild_pid=""
cleanup() {
  if [[ -n "$rebuild_pid" ]]; then
    kill "$rebuild_pid" >/dev/null 2>&1 || true
  fi
  docker rm -f "$container_name" >/dev/null 2>&1 || true
  if [[ -d "$work_dir" ]]; then
    find "$work_dir" -depth -mindepth 1 -delete
    rmdir -- "$work_dir"
  fi
  rmdir -- "$lock_dir" >/dev/null 2>&1 || true
}
terminate() {
  trap - EXIT HUP INT TERM
  cleanup
  exit 130
}
trap cleanup EXIT
trap terminate HUP INT TERM

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

if ! compose ps --status running --services | grep -qx backend; then
  echo "Backend 未运行，无法创建不中断服务的 Online Backup。" >&2
  exit 1
fi
if docker container inspect "$container_name" >/dev/null 2>&1; then
  echo "检测到未清理的搜索 bootstrap 容器。" >&2
  exit 1
fi

docker pull "$image" >/dev/null
platform="$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$image")"
image_revision="$(docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image")"
if [[ "$platform" != "linux/amd64" || "$image_revision" != "$revision" ]]; then
  echo "目标 API 镜像平台或 revision label 不匹配。" >&2
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
baseline_name="spotify-stats-search-bootstrap-${revision:0:12}-$stamp.db"
baseline_path="$DEPLOY_DIR/backups/$baseline_name"
resume_path="$DEPLOY_DIR/backups/music-search-resume.db"
host_uid="$(id -u)"
host_gid="$(id -g)"
if [[ -e "$baseline_path" ]]; then
  echo "Online Backup 目标已存在，拒绝覆盖。" >&2
  exit 1
fi

echo "创建生产 SQLite Online Backup；现网继续在线。" >&2
compose exec -T backend python - "/var/backups/spotify-stats/$baseline_name" <<'PY'
import sqlite3
import sys

source = sqlite3.connect("/app/data/spotify_stats.db", timeout=30)
target = sqlite3.connect(sys.argv[1])
with target:
    source.backup(target)
integrity = str(target.execute("PRAGMA integrity_check").fetchone()[0])
target.close()
source.close()
if integrity != "ok":
    raise SystemExit("bootstrap backup integrity_check failed")
PY
sudo chown -- "$host_uid:$host_gid" "$baseline_path"
if [[ -e "$resume_path" ]]; then
  sudo chown -- "$host_uid:$host_gid" "$resume_path"
fi

minimum_available_mib="${SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB:-$(get_env SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB)}"
minimum_available_mib="${minimum_available_mib:-1280}"
if [[ ! "$minimum_available_mib" =~ ^[1-9][0-9]*$ ]]; then
  echo "SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB 必须是正整数。" >&2
  exit 2
fi
capacity_report="$work_dir/capacity.json"
python3 "$CAPACITY_PROBE" \
  --db-path "$baseline_path" --min-available-mib "$minimum_available_mib" \
  --phase before --json-output "$capacity_report"

baseline_dir="$(dirname -- "$baseline_path")"
baseline_file="$(basename -- "$baseline_path")"
resume_dir="$(dirname -- "$resume_path")"
resume_file="$(basename -- "$resume_path")"
docker run --rm --init --user "$host_uid:$host_gid" \
  -e SPOTIFY_STATS_WARMUP=0 -e SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0 \
  --mount "type=bind,src=$baseline_dir,dst=/baseline,readonly" \
  --mount "type=bind,src=$resume_dir,dst=/resume" \
  --mount "type=bind,src=$PREPARE_HELPER,dst=/prepare-music-search-bootstrap-resume.py,readonly" \
  --mount "type=bind,src=$work_dir,dst=/work" \
  "$image" python /prepare-music-search-bootstrap-resume.py \
    --baseline-db "/baseline/$baseline_file" \
    --resume-db "/resume/$resume_file" \
    --json-output /work/resume.json

python3 - "$work_dir/resume.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
validation = payload.get("validation") or {}
print(
    "搜索统计 bootstrap 续建："
    f"reused={str(bool(payload.get('resume_reused'))).lower()} "
    f"reason={payload.get('reason', 'unknown')} "
    f"ready_rows={int(validation.get('ready_snapshot_rows') or 0)}",
    file=sys.stderr,
)
PY

echo "一次性六变体统计构建开始；失败或超时会保留同源部分成果供下次续建。" >&2
rebuild_started="$SECONDS"
docker run --name "$container_name" --rm --init --user "$host_uid:$host_gid" \
  -e SPOTIFY_STATS_WARMUP=0 -e SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0 \
  --mount "type=bind,src=$resume_dir,dst=/resume" \
  "$image" python scripts/rebuild_music_search_derived_data.py \
    --db-path "/resume/$resume_file" --json --require-all-ready \
    > "$work_dir/rebuild.json" &
rebuild_pid="$!"
while kill -0 "$rebuild_pid" >/dev/null 2>&1; do
  for _heartbeat_second in {1..60}; do
    sleep 1 &
    wait "$!" || true
    if ! kill -0 "$rebuild_pid" >/dev/null 2>&1; then
      break
    fi
  done
  if kill -0 "$rebuild_pid" >/dev/null 2>&1; then
    echo "一次性搜索统计构建仍在运行：elapsed=$((SECONDS - rebuild_started))s" >&2
  fi
done
if wait "$rebuild_pid"; then
  rebuild_status=0
else
  rebuild_status="$?"
  rebuild_pid=""
  echo "一次性搜索统计构建失败；续建数据库已保留：exit=$rebuild_status" >&2
  exit "$rebuild_status"
fi
rebuild_pid=""
container_name=""
echo "一次性搜索统计构建完成：elapsed=$((SECONDS - rebuild_started))s" >&2

python3 - "$work_dir/rebuild.json" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8"))
if not isinstance(payload, dict):
    raise SystemExit("bootstrap rebuild stdout is not one JSON object")
PY
python3 - "$resume_path" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.execute("PRAGMA journal_mode=DELETE")
conn.close()
PY
python3 "$CAPACITY_PROBE" \
  --db-path "$resume_path" --min-available-mib "$minimum_available_mib" \
  --phase after --previous-report "$capacity_report" --json-output "$capacity_report"
python3 "$VALIDATOR" \
  --db-path "$resume_path" --rebuild-report "$work_dir/rebuild.json" \
  --resume-report "$work_dir/resume.json" --capacity-report "$capacity_report" \
  --json-output "$json_report_path"
chmod 600 "$json_report_path" "$resume_path" "$baseline_path"

trap - EXIT
cleanup
echo "一次性搜索统计 bootstrap 通过；现网未切换，续建成果已准备供常规发布复用。"
