#!/usr/bin/env bash
set -Eeuo pipefail

DEPLOY_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VALIDATOR="$DEPLOY_DIR/validate-music-search-preflight.py"
CAPACITY_PROBE="$DEPLOY_DIR/music_search_preflight_capacity.py"
db_copy_input=""
json_report_input=""
image=""

usage() {
  cat >&2 <<'EOF'
用法：preflight-music-search.sh --db-copy <明确的数据库副本> \
  --json-report <新报告路径> --image <目标 backend 镜像>

脚本拒绝 production data/ 下的数据库和未解析路径。只有临时工作副本通过
六变体 --require-all-ready 及数据库契约校验后，才会原子更新传入副本。
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

minimum_available_mib="${SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB:-1280}"
if [[ ! "$minimum_available_mib" =~ ^[1-9][0-9]*$ ]]; then
  echo "SEARCH_PREFLIGHT_MIN_AVAILABLE_MIB 必须是正整数。" >&2
  exit 2
fi

db_copy_dir="$(dirname -- "$db_copy_path")"
capacity_report="$(mktemp "$db_copy_dir/.music-search-capacity.XXXXXX")"
work_dir=""
replacement_path="${db_copy_path}.preflight-ready.$$"
report_temporary="$(mktemp "$(dirname -- "$json_report_path")/.music-search-preflight.XXXXXX")"
cleanup() {
  if [[ -n "$work_dir" && -d "$work_dir" ]]; then
    rm -rf -- "$work_dir"
  fi
  rm -f -- "$replacement_path" "$report_temporary" "$capacity_report"
}
trap cleanup EXIT

python3 "$CAPACITY_PROBE" \
  --db-path "$db_copy_path" \
  --min-available-mib "$minimum_available_mib" \
  --phase before \
  --json-output "$capacity_report"

work_dir="$(mktemp -d "$db_copy_dir/.spotify-stats-search-preflight.XXXXXX")"
cp -- "$db_copy_path" "$work_dir/spotify_stats.db"

docker run --rm --init \
  -e SPOTIFY_STATS_WARMUP=0 \
  -e SPOTIFY_STATS_SEARCH_STARTUP_REBUILD=0 \
  --mount "type=bind,src=$work_dir,dst=/preflight" \
  "$image" \
  python scripts/rebuild_music_search_derived_data.py \
    --db-path /preflight/spotify_stats.db --json --require-all-ready \
    > "$work_dir/rebuild-report.json"

# The captured stdout must be exactly one JSON document; logs belong on stderr.
python3 - "$work_dir/rebuild-report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
if not isinstance(payload, dict):
    raise SystemExit("music-search rebuild stdout is not one JSON object")
PY

python3 - "$work_dir/spotify_stats.db" <<'PY'
import sqlite3
import sys

conn = sqlite3.connect(sys.argv[1])
conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
conn.execute("PRAGMA journal_mode=DELETE")
conn.close()
PY

python3 "$CAPACITY_PROBE" \
  --db-path "$work_dir/spotify_stats.db" \
  --min-available-mib "$minimum_available_mib" \
  --phase after \
  --previous-report "$capacity_report" \
  --json-output "$capacity_report"

python3 "$VALIDATOR" \
  --db-path "$work_dir/spotify_stats.db" \
  --rebuild-report "$work_dir/rebuild-report.json" \
  --capacity-report "$capacity_report" \
  --json-output "$report_temporary"

install -m 600 "$work_dir/spotify_stats.db" "$replacement_path"
mv -f -- "$replacement_path" "$db_copy_path"
mv -f -- "$report_temporary" "$json_report_path"
trap - EXIT
rm -rf -- "$work_dir"
rm -f -- "$capacity_report"

echo "预检副本已原子更新，JSON 报告：$json_report_path"
