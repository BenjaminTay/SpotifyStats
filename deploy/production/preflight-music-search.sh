#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$DEPLOY_DIR/validate-music-search-preflight.py"
CAPACITY_PROBE="$DEPLOY_DIR/music_search_preflight_capacity.py"
db_copy_input=""
json_report_input=""
resume_db_input=""
image=""

usage() {
  cat >&2 <<'EOF'
用法：preflight-music-search.sh --db-copy <明确的数据库副本> \
  --json-report <新报告路径> --image <目标 backend 镜像>

脚本拒绝 production data/ 下的数据库和未解析路径。常规发布只允许精确复用
六套统计；若统计语义真实变化则快速失败，必须先执行独立维护。只有临时工作
副本通过复用与数据库契约校验后，才会原子更新传入副本。
EOF
}

while (( $# > 0 )); do
  case "$1" in
    --db-copy)
      db_copy_input="${2:-}"
      shift 2
      ;;
    --json-report)
      json_report_input="${2:-}"
      shift 2
      ;;
    --image)
      image="${2:-}"
      shift 2
      ;;
    --resume-db)
      resume_db_input="${2:-}"
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

if [[ -z "$db_copy_input" || -z "$json_report_input" || -z "$image" ]]; then
  usage
  exit 2
fi
if [[ ! "$image" =~ ^[A-Za-z0-9._/@:-]+$ ]]; then
  echo "目标 backend 镜像引用无效。" >&2
  exit 2
fi

resolve_existing_file() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

try:
    path = Path(sys.argv[1]).expanduser().resolve(strict=True)
except (OSError, RuntimeError):
    raise SystemExit(1)
if not path.is_file():
    raise SystemExit(1)
print(path)
PY
}

resolve_output_path() {
  python3 - "$1" <<'PY'
from pathlib import Path
import sys

raw = Path(sys.argv[1]).expanduser()
try:
    parent = raw.parent.resolve(strict=True)
except (OSError, RuntimeError):
    raise SystemExit(1)
if not raw.name or raw.name in {".", ".."}:
    raise SystemExit(1)
print(parent / raw.name)
PY
}

if ! db_copy_path="$(resolve_existing_file "$db_copy_input")"; then
  echo "数据库副本不存在或路径无法完整解析。" >&2
  exit 2
fi
if ! json_report_path="$(resolve_output_path "$json_report_input")"; then
  echo "JSON 报告父目录不存在或路径无法完整解析。" >&2
  exit 2
fi
if [[ -e "$json_report_path" ]]; then
  echo "JSON 报告已存在，拒绝覆盖：$json_report_path" >&2
  exit 2
fi
if [[ -n "$resume_db_input" ]]; then
  if ! resume_db_path="$(resolve_output_path "$resume_db_input")"; then
    echo "续建数据库父目录不存在或路径无法完整解析。" >&2
    exit 2
  fi
else
  resume_db_path="${db_copy_path}.music-search-resume"
fi

production_data_dir="$(python3 - "$DEPLOY_DIR/data" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve(strict=False))
PY
)"
case "$db_copy_path" in
  "$production_data_dir"|"$production_data_dir"/*)
    echo "拒绝把生产 data/ 中的真实数据库作为预检目标；请先创建明确副本。" >&2
    exit 2
    ;;
esac
case "$resume_db_path" in
  "$production_data_dir"|"$production_data_dir"/*)
    echo "拒绝把生产 data/ 作为续建数据库位置。" >&2
    exit 2
    ;;
esac

minimum_available_mib="${SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB:-1280}"
if [[ ! "$minimum_available_mib" =~ ^[1-9][0-9]*$ ]]; then
  echo "SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB 必须是正整数。" >&2
  exit 2
fi

db_copy_dir="$(dirname -- "$db_copy_path")"
capacity_report="$(mktemp "$db_copy_dir/.music-search-capacity.XXXXXX")"
work_dir=""
rebuild_pid=""
container_name="spotify-stats-search-preflight"
replacement_path="${db_copy_path}.preflight-ready.$$"
report_temporary="$(mktemp "$(dirname -- "$json_report_path")/.music-search-preflight.XXXXXX")"
cleanup() {
  if [[ -n "$container_name" ]]; then
    docker rm -f "$container_name" >/dev/null 2>&1 || true
  fi
  if [[ -n "$rebuild_pid" ]]; then
    kill "$rebuild_pid" >/dev/null 2>&1 || true
  fi
  if [[ -n "$work_dir" && -d "$work_dir" ]]; then
    rm -rf -- "$work_dir"
  fi
  rm -f -- "$replacement_path" "$report_temporary" "$capacity_report"
}
terminate() {
  trap - EXIT HUP INT TERM
  cleanup
  exit 130
}
trap cleanup EXIT
trap terminate HUP INT TERM

python3 "$CAPACITY_PROBE" \
  --db-path "$db_copy_path" \
  --min-available-mib "$minimum_available_mib" \
  --phase before \
  --json-output "$capacity_report"

work_dir="$(mktemp -d "$db_copy_dir/.spotify-stats-search-preflight.XXXXXX")"
resume_db_dir="$(dirname -- "$resume_db_path")"
resume_db_name="$(basename -- "$resume_db_path")"
db_copy_name="$(basename -- "$db_copy_path")"

if docker container inspect "$container_name" >/dev/null 2>&1; then
  echo "检测到未清理的音乐搜索预检容器：$container_name" >&2
  exit 1
fi

docker run --rm --init \
  -e SPOTIFY_STATS_WARMUP=0 \
  -e SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0 \
  --mount "type=bind,src=$db_copy_dir,dst=/baseline,readonly" \
  --mount "type=bind,src=$resume_db_dir,dst=/resume" \
  --mount "type=bind,src=$work_dir,dst=/preflight" \
  "$image" \
  python scripts/prepare_music_search_resume.py \
    --baseline-db "/baseline/$db_copy_name" \
    --resume-db "/resume/$resume_db_name" \
    --json-output /preflight/resume-report.json
python3 - "$work_dir/resume-report.json" <<'PY'
import json
import re
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
except (OSError, json.JSONDecodeError):
    print("音乐搜索续建副本判定摘要不可读", file=sys.stderr)
    raise SystemExit(0)
reason = str(payload.get("reason") or "unknown")
if not re.fullmatch(r"[a-z0-9_]{1,96}", reason):
    reason = "redacted"
validation = payload.get("validation") or {}
print(
    "音乐搜索续建副本判定："
    f"reused={str(bool(payload.get('resume_reused'))).lower()} "
    f"reason={reason} "
    f"ready_rows={int(validation.get('ready_snapshot_rows') or 0)}",
    file=sys.stderr,
)
PY

existing_preflight="$(
  for container_id in $(docker ps -q); do
    container_command="$(
      docker inspect --format '{{.Path}} {{join .Args " "}}' "$container_id" 2>/dev/null || true
    )"
    case "$container_command" in
      *scripts/rebuild_music_search_derived_data.py*"--db-path /resume/"*)
        printf '%s\n' "$container_id"
        ;;
    esac
  done
)"
if [[ -n "$existing_preflight" ]]; then
  echo "检测到仍在运行的音乐搜索副本重建容器，拒绝并发预检：$existing_preflight" >&2
  exit 1
fi
echo "音乐搜索候选维护与统计复用校验开始；生产服务保持在线。" >&2
rebuild_started="$SECONDS"
docker run --name "$container_name" --rm --init \
  -e SPOTIFY_STATS_WARMUP=0 \
  -e SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0 \
  --mount "type=bind,src=$resume_db_dir,dst=/resume" \
  --mount "type=bind,src=$work_dir,dst=/preflight" \
  "$image" \
  python scripts/rebuild_music_search_derived_data.py \
    --db-path "/resume/$resume_db_name" --json --require-all-ready \
    --statistics-reuse-only \
    > "$work_dir/rebuild-report.json" &
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
    echo "音乐搜索候选维护与统计复用校验仍在运行：elapsed=$((SECONDS - rebuild_started))s" >&2
  fi
done
if wait "$rebuild_pid"; then
  rebuild_status=0
else
  rebuild_status="$?"
  rebuild_pid=""
  echo "音乐搜索候选维护与统计复用校验失败：exit=$rebuild_status" >&2
  python3 - "$work_dir/rebuild-report.json" <<'PY'
import json
import re
import sys


def safe_token(value: object) -> str:
    token = str(value or "unknown")
    return token if re.fullmatch(r"[A-Za-z0-9_.-]{1,96}", token) else "redacted"


try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        payload = json.load(handle)
except (OSError, json.JSONDecodeError):
    print("音乐搜索预检失败摘要不可读", file=sys.stderr)
else:
    error = payload.get("error") if isinstance(payload, dict) else None
    resources = payload.get("resources") if isinstance(payload, dict) else None
    print(
        "音乐搜索预检失败摘要："
        f"status={safe_token(payload.get('status'))} "
        f"stage={safe_token(error.get('stage') if isinstance(error, dict) else None)} "
        f"type={safe_token(error.get('type') if isinstance(error, dict) else None)} "
        f"elapsed_ms={float(payload.get('total_elapsed_ms') or 0):.3f} "
        f"peak_rss_mib={float(resources.get('peak_rss_mib') or 0):.3f}",
        file=sys.stderr,
    )
PY
  exit "$rebuild_status"
fi
rebuild_pid=""
container_name=""
echo "音乐搜索候选维护与统计复用校验完成：elapsed=$((SECONDS - rebuild_started))s" >&2

# The captured stdout must be exactly one JSON document; logs belong on stderr.
python3 - "$work_dir/rebuild-report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if not isinstance(payload, dict):
    raise SystemExit("music-search rebuild stdout is not one JSON object")
PY

python3 - "$resume_db_path" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.execute("PRAGMA journal_mode=DELETE")
conn.close()
PY

python3 "$CAPACITY_PROBE" \
  --db-path "$resume_db_path" \
  --min-available-mib "$minimum_available_mib" \
  --phase after \
  --previous-report "$capacity_report" \
  --json-output "$capacity_report"

python3 "$VALIDATOR" \
  --db-path "$resume_db_path" \
  --rebuild-report "$work_dir/rebuild-report.json" \
  --resume-report "$work_dir/resume-report.json" \
  --capacity-report "$capacity_report" \
  --json-output "$report_temporary"

install -m 600 "$resume_db_path" "$replacement_path"
mv -f -- "$replacement_path" "$db_copy_path"
mv -f -- "$report_temporary" "$json_report_path"
trap - EXIT
rm -rf -- "$work_dir"
rm -f -- "$capacity_report"

echo "预检副本已原子更新，JSON 报告：$json_report_path"
