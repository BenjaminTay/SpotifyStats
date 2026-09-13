#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:5173}
PREVIEW_URL=${PREVIEW_URL:-}
PREVIEW_API_URL=${PREVIEW_API_URL:-$BACKEND_URL}
BENCHMARK_RUNS=${BENCHMARK_RUNS:-22}
SLOW_MS=${SLOW_MS:-500}
BENCHMARK_JSON=${BENCHMARK_JSON:-}
OPENAPI_OPERATION_AUDIT_JSON=${OPENAPI_OPERATION_AUDIT_JSON:-}
OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON=${OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON:-}
RUN_QUICKSTART_PREFLIGHT=${RUN_QUICKSTART_PREFLIGHT:-0}
QUICKSTART_JSON=${QUICKSTART_JSON:-}
RUN_CROSS_BROWSER=${RUN_CROSS_BROWSER:-1}
RUN_WEB_VITALS=${RUN_WEB_VITALS:-0}
RUN_RESOURCE_SNAPSHOT=${RUN_RESOURCE_SNAPSHOT:-0}
RESOURCE_MAX_TOTAL_RSS_MB=${RESOURCE_MAX_TOTAL_RSS_MB:-}
RESOURCE_MAX_TOTAL_CPU_PERCENT=${RESOURCE_MAX_TOTAL_CPU_PERCENT:-}
WEB_VITALS_MAX_LCP_MS=${WEB_VITALS_MAX_LCP_MS:-}
WEB_VITALS_MAX_CLS=${WEB_VITALS_MAX_CLS:-}
WEB_VITALS_MAX_TBT_MS=${WEB_VITALS_MAX_TBT_MS:-}
WEB_VITALS_MAX_RESOURCE_COUNT=${WEB_VITALS_MAX_RESOURCE_COUNT:-}
WEB_VITALS_MAX_ENCODED_RESOURCE_KB=${WEB_VITALS_MAX_ENCODED_RESOURCE_KB:-}
WEB_VITALS_MAX_SCROLL_OVERFLOW_PX=${WEB_VITALS_MAX_SCROLL_OVERFLOW_PX:-}
RESOURCE_SNAPSHOT_JSON=${RESOURCE_SNAPSHOT_JSON:-}
SUMMARY_JSON=${SUMMARY_JSON:-}
FULLSTACK_RUN_ROOT=${FULLSTACK_RUN_ROOT:-${TMPDIR:-/tmp}/spotify-fullstack-verification}
FULLSTACK_LOCK_FILE=${FULLSTACK_LOCK_FILE:-${TMPDIR:-/tmp}/spotify-fullstack-verification.lock}
FULLSTACK_LOCK_METADATA_FILE=${FULLSTACK_LOCK_METADATA_FILE:-${FULLSTACK_LOCK_FILE}.owner.json}

ALL_STAGES="preflight quality backend api browser-routes browser-interactions browser-inventory browser-compat optional"
REQUIRED_STAGES="preflight quality backend api browser-routes browser-interactions browser-inventory browser-compat"
SELECTION_MODE=full
ONLY_STAGES=
FROM_STAGE=
ONLY_SET=0
FROM_SET=0
SELECTED_STAGES=
DRY_RUN=0
LIST_STAGES=0
REPORT_INITIALIZED=0
RESULTS_FILE=
STARTED_AT=
START_EPOCH_MS=
REPORT_PYTHON=
PYTHON_PLAYWRIGHT_RESOLVED=
RUN_ID=
RUN_DIR=
RUN_SUMMARY_JSON=
LATEST_POINTER=
LOCK_PID=
LOCK_STATUS_FILE=

usage() {
  cat <<'EOF'
Usage:
  sh scripts/fullstack_verification_check.sh [options]

Runs the non-destructive full-stack verification matrix. Start the backend
and frontend dev server before running the default command:
  source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --host 127.0.0.1 --port 8000
  cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

Stage selection:
  --list-stages             Print stable stage keys and exit
  --only <a,b>              Run only the comma-separated stages; result is PARTIAL
  --from <stage>            Run the required stage suffix; result is PARTIAL
  --dry-run                 Resolve stages and write a NOT_RUN summary without checks
  --summary-json <path>     Compatibility copy of the run-scoped stage summary

Options:
  --backend-url <url>       Backend URL for API benchmark, default http://127.0.0.1:8000
  --frontend-url <url>      Frontend dev URL for browser smoke, default http://localhost:5173
  --preview-url <url>       Optional Vite preview URL; when set, preview smoke also runs
  --preview-api-url <url>   Backend URL used by preview smoke request rewriting
  --benchmark-runs <n>      Number of benchmark requests per endpoint, default 22
  --slow-ms <ms>            API hot P95 slow threshold, default 500
  --benchmark-json <path>   JSON benchmark output path, default inside the run directory
  --openapi-operation-audit-json <path>
                           OpenAPI operation audit JSON output path
  --openapi-parameter-boundary-audit-json <path>
                           OpenAPI parameter boundary audit JSON output path
  --quickstart-preflight
                           Verify quickstart health/docs/frontend/proxy against already-running services
  --quickstart-json <path>
                           Quickstart timing JSON output path
  --skip-cross-browser     Skip Playwright Chromium/Firefox/WebKit smoke; full result is PARTIAL
  --web-vitals             Run Web Vitals lab probes for dev and preview URLs
  --resource-snapshot      Capture backend/frontend process CPU/RSS snapshot
  --resource-snapshot-json <path>
                           Runtime resource snapshot JSON output path
  --resource-max-total-rss-mb <mb>
                           Optional combined backend/frontend RSS budget
  --resource-max-total-cpu-percent <percent>
                           Optional combined backend/frontend CPU budget
  --web-vitals-max-lcp-ms <ms>
                           Optional Web Vitals LCP budget passed to lab probes
  --web-vitals-max-cls <score>
                           Optional Web Vitals CLS budget passed to lab probes
  --web-vitals-max-tbt-ms <ms>
                           Optional Web Vitals TBT approx budget passed to lab probes
  --web-vitals-max-resource-count <n>
                           Optional loaded resource count budget for preview probes
                           (dev probes skip it to avoid Vite module request noise)
  --web-vitals-max-encoded-resource-kb <kb>
                           Optional encoded resource KB budget for preview probes
                           (dev probes skip it to avoid Vite module request noise)
  --web-vitals-max-scroll-overflow-px <px>
                           Optional horizontal scroll overflow budget passed to lab probes
  -h, --help               Show this help

Environment variables with the same uppercase names can also configure the
existing runtime options. Every run writes its canonical report below
/tmp/spotify-fullstack-verification/<run-id>/summary.json; SUMMARY_JSON or
--summary-json additionally writes a compatibility copy at the requested path.
When cross-browser smoke is selected, PYTHON_PLAYWRIGHT may point to a Python
that can import playwright.sync_api; otherwise the script auto-detects one.
EOF
}

die_usage() {
  echo "$1" >&2
  exit 2
}

require_value() {
  option=$1
  remaining=$2
  [ "$remaining" -ge 2 ] || die_usage "Missing value for $option"
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --list-stages)
      LIST_STAGES=1
      ;;
    --only)
      require_value "$1" "$#"
      shift
      ONLY_STAGES=$1
      ONLY_SET=1
      ;;
    --from)
      require_value "$1" "$#"
      shift
      FROM_STAGE=$1
      FROM_SET=1
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    --summary-json)
      require_value "$1" "$#"
      shift
      SUMMARY_JSON=$1
      ;;
    --backend-url)
      require_value "$1" "$#"
      shift
      BACKEND_URL=$1
      ;;
    --frontend-url)
      require_value "$1" "$#"
      shift
      FRONTEND_URL=$1
      ;;
    --preview-url)
      require_value "$1" "$#"
      shift
      PREVIEW_URL=$1
      ;;
    --preview-api-url)
      require_value "$1" "$#"
      shift
      PREVIEW_API_URL=$1
      ;;
    --benchmark-runs)
      require_value "$1" "$#"
      shift
      BENCHMARK_RUNS=$1
      ;;
    --slow-ms)
      require_value "$1" "$#"
      shift
      SLOW_MS=$1
      ;;
    --benchmark-json)
      require_value "$1" "$#"
      shift
      BENCHMARK_JSON=$1
      ;;
    --openapi-operation-audit-json)
      require_value "$1" "$#"
      shift
      OPENAPI_OPERATION_AUDIT_JSON=$1
      ;;
    --openapi-parameter-boundary-audit-json)
      require_value "$1" "$#"
      shift
      OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON=$1
      ;;
    --quickstart-preflight)
      RUN_QUICKSTART_PREFLIGHT=1
      ;;
    --quickstart-json)
      require_value "$1" "$#"
      shift
      QUICKSTART_JSON=$1
      ;;
    --skip-cross-browser)
      RUN_CROSS_BROWSER=0
      ;;
    --web-vitals)
      RUN_WEB_VITALS=1
      ;;
    --resource-snapshot)
      RUN_RESOURCE_SNAPSHOT=1
      ;;
    --resource-snapshot-json)
      require_value "$1" "$#"
      shift
      RESOURCE_SNAPSHOT_JSON=$1
      ;;
    --resource-max-total-rss-mb)
      require_value "$1" "$#"
      shift
      RESOURCE_MAX_TOTAL_RSS_MB=$1
      ;;
    --resource-max-total-cpu-percent)
      require_value "$1" "$#"
      shift
      RESOURCE_MAX_TOTAL_CPU_PERCENT=$1
      ;;
    --web-vitals-max-lcp-ms)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_LCP_MS=$1
      ;;
    --web-vitals-max-cls)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_CLS=$1
      ;;
    --web-vitals-max-tbt-ms)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_TBT_MS=$1
      ;;
    --web-vitals-max-resource-count)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_RESOURCE_COUNT=$1
      ;;
    --web-vitals-max-encoded-resource-kb)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_ENCODED_RESOURCE_KB=$1
      ;;
    --web-vitals-max-scroll-overflow-px)
      require_value "$1" "$#"
      shift
      WEB_VITALS_MAX_SCROLL_OVERFLOW_PX=$1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      die_usage "Unknown argument: $1"
      ;;
  esac
  shift
done

if [ "$LIST_STAGES" = "1" ]; then
  for stage in $ALL_STAGES; do
    echo "$stage"
  done
  exit 0
fi

[ "$ONLY_SET" = "0" ] || [ "$FROM_SET" = "0" ] || die_usage "--only and --from are mutually exclusive"

stage_exists() {
  candidate_stage=$1
  for known_stage in $ALL_STAGES; do
    [ "$candidate_stage" != "$known_stage" ] || return 0
  done
  return 1
}

contains_stage() {
  stage_list=$1
  wanted_stage=$2
  for listed_stage in $stage_list; do
    [ "$listed_stage" != "$wanted_stage" ] || return 0
  done
  return 1
}

optional_requested() {
  [ "$RUN_QUICKSTART_PREFLIGHT" = "1" ] ||
    [ "$RUN_RESOURCE_SNAPSHOT" = "1" ] ||
    [ "$RUN_WEB_VITALS" = "1" ] ||
    [ -n "$PREVIEW_URL" ]
}

if [ "$ONLY_SET" = "1" ]; then
  [ -n "$ONLY_STAGES" ] || die_usage "Stage selection cannot be empty"
  case "$ONLY_STAGES" in
    ,*|*,|*,,*) die_usage "Invalid empty stage in --only: $ONLY_STAGES" ;;
  esac
  SELECTION_MODE=only
  requested_stages=$(printf '%s' "$ONLY_STAGES" | tr ',' ' ')
  for requested_stage in $requested_stages; do
    stage_exists "$requested_stage" || die_usage "Unknown stage: $requested_stage"
    contains_stage "$SELECTED_STAGES" "$requested_stage" && die_usage "Duplicate stage: $requested_stage"
    SELECTED_STAGES="$SELECTED_STAGES $requested_stage"
  done
  SELECTED_STAGES=${SELECTED_STAGES# }
elif [ "$FROM_SET" = "1" ]; then
  [ -n "$FROM_STAGE" ] || die_usage "Stage selection cannot be empty"
  stage_exists "$FROM_STAGE" || die_usage "Unknown stage: $FROM_STAGE"
  SELECTION_MODE=from
  include_stage=0
  for required_stage in $REQUIRED_STAGES; do
    [ "$required_stage" != "$FROM_STAGE" ] || include_stage=1
    if [ "$include_stage" = "1" ]; then
      SELECTED_STAGES="$SELECTED_STAGES $required_stage"
    fi
  done
  if [ "$FROM_STAGE" = "optional" ]; then
    SELECTED_STAGES=" optional"
  elif [ "$include_stage" = "0" ]; then
    die_usage "Stage is not part of the required suffix: $FROM_STAGE"
  fi
  SELECTED_STAGES=${SELECTED_STAGES# }
else
  SELECTED_STAGES=$REQUIRED_STAGES
  if optional_requested; then
    SELECTED_STAGES="$SELECTED_STAGES optional"
  fi
fi

[ -n "$SELECTED_STAGES" ] || die_usage "Stage selection cannot be empty"

REPORT_PYTHON=$(command -v python3 || command -v python || true)
[ -n "$REPORT_PYTHON" ] || {
  echo "No Python executable is available for the full-stack stage report." >&2
  exit 1
}

RUN_ID=${FULLSTACK_RUN_ID:-$("$REPORT_PYTHON" - <<'PY'
from datetime import datetime, timezone
from uuid import uuid4

stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
print(f"{stamp}-{uuid4().hex[:12]}")
PY
)}
RUN_DIR=$FULLSTACK_RUN_ROOT/$RUN_ID
RUN_SUMMARY_JSON=$RUN_DIR/summary.json
LATEST_POINTER=$FULLSTACK_RUN_ROOT/latest
mkdir -p "$RUN_DIR"
BENCHMARK_JSON=${BENCHMARK_JSON:-$RUN_DIR/api-benchmark.json}
OPENAPI_OPERATION_AUDIT_JSON=${OPENAPI_OPERATION_AUDIT_JSON:-$RUN_DIR/openapi-operation-audit.json}
OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON=${OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON:-$RUN_DIR/openapi-parameter-boundary-audit.json}
QUICKSTART_JSON=${QUICKSTART_JSON:-$RUN_DIR/quickstart-timing.json}
RESOURCE_SNAPSHOT_JSON=${RESOURCE_SNAPSHOT_JSON:-$RUN_DIR/runtime-resources.json}

epoch_ms() {
  "$REPORT_PYTHON" -c 'import time; print(int(time.time() * 1000))'
}

STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
START_EPOCH_MS=$(epoch_ms)
RESULTS_FILE=$(mktemp "$RUN_DIR/stages.XXXXXX")
for stage in $ALL_STAGES; do
  printf '%s\t%s\t%s\n' "$stage" "NOT_RUN" "0" >>"$RESULTS_FILE"
done
REPORT_INITIALIZED=1

record_stage() {
  printf '%s\t%s\t%s\n' "$1" "$2" "$3" >>"$RESULTS_FILE"
}

write_summary() {
  script_exit_code=$1
  end_epoch_ms=$(epoch_ms)
  duration_ms=$((end_epoch_ms - START_EPOCH_MS))
  git_head=$(git rev-parse HEAD 2>/dev/null || true)
  if [ -n "$(git status --porcelain 2>/dev/null || true)" ]; then
    dirty=true
  else
    dirty=false
  fi

  FULLSTACK_RESULTS_FILE=$RESULTS_FILE \
  FULLSTACK_RUN_ID=$RUN_ID \
  FULLSTACK_RUN_DIR=$RUN_DIR \
  FULLSTACK_RUN_SUMMARY_JSON=$RUN_SUMMARY_JSON \
  FULLSTACK_LATEST_POINTER=$LATEST_POINTER \
  FULLSTACK_LOCK_FILE=$FULLSTACK_LOCK_FILE \
  FULLSTACK_SUMMARY_JSON=$SUMMARY_JSON \
  FULLSTACK_ALL_STAGES=$ALL_STAGES \
  FULLSTACK_REQUIRED_STAGES=$REQUIRED_STAGES \
  FULLSTACK_SELECTED_STAGES=$SELECTED_STAGES \
  FULLSTACK_SELECTION_MODE=$SELECTION_MODE \
  FULLSTACK_STARTED_AT=$STARTED_AT \
  FULLSTACK_DURATION_MS=$duration_ms \
  FULLSTACK_GIT_HEAD=$git_head \
  FULLSTACK_DIRTY=$dirty \
  FULLSTACK_BACKEND_URL=$BACKEND_URL \
  FULLSTACK_FRONTEND_URL=$FRONTEND_URL \
  FULLSTACK_PREVIEW_URL=$PREVIEW_URL \
  FULLSTACK_DRY_RUN=$DRY_RUN \
  FULLSTACK_EXIT_CODE=$script_exit_code \
  "$REPORT_PYTHON" - <<'PY'
import json
import os
import tempfile
from pathlib import Path


all_stages = os.environ["FULLSTACK_ALL_STAGES"].split()
required_stages = os.environ["FULLSTACK_REQUIRED_STAGES"].split()
selected_stages = os.environ["FULLSTACK_SELECTED_STAGES"].split()
latest = {name: {"name": name, "status": "NOT_RUN", "duration_ms": 0} for name in all_stages}
for line in Path(os.environ["FULLSTACK_RESULTS_FILE"]).read_text(encoding="utf-8").splitlines():
    name, status, duration_ms = line.split("\t")
    latest[name] = {"name": name, "status": status, "duration_ms": int(duration_ms)}

statuses = [latest[name]["status"] for name in all_stages]
mode = os.environ["FULLSTACK_SELECTION_MODE"]
dry_run = os.environ["FULLSTACK_DRY_RUN"] == "1"
exit_code = int(os.environ["FULLSTACK_EXIT_CODE"])
if "FAIL" in statuses or (exit_code != 0 and "BLOCKED" not in statuses):
    overall_status = "FAIL"
elif "BLOCKED" in statuses:
    overall_status = "BLOCKED"
elif dry_run or mode != "full":
    overall_status = "PARTIAL"
elif all(latest[name]["status"] == "PASS" for name in required_stages):
    overall_status = "PASS"
else:
    overall_status = "PARTIAL"

payload = {
    "schema_version": 1,
    "run_id": os.environ["FULLSTACK_RUN_ID"],
    "run_directory": os.environ["FULLSTACK_RUN_DIR"],
    "overall_status": overall_status,
    "selection": {"mode": mode, "stages": selected_stages},
    "dry_run": dry_run,
    "started_at": os.environ["FULLSTACK_STARTED_AT"],
    "duration_ms": int(os.environ["FULLSTACK_DURATION_MS"]),
    "git_head": os.environ["FULLSTACK_GIT_HEAD"] or None,
    "dirty": os.environ["FULLSTACK_DIRTY"] == "true",
    "services": {
        "backend_url": os.environ["FULLSTACK_BACKEND_URL"],
        "frontend_url": os.environ["FULLSTACK_FRONTEND_URL"],
        "preview_url": os.environ["FULLSTACK_PREVIEW_URL"] or None,
    },
    "shared_stage_lock": {
        "path": os.environ["FULLSTACK_LOCK_FILE"],
        "events": [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted(Path(os.environ["FULLSTACK_RUN_DIR"]).glob("lock-*.json"))
        ],
    },
    "stages": [latest[name] for name in all_stages],
}


def atomic_json(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


canonical = Path(os.environ["FULLSTACK_RUN_SUMMARY_JSON"])
atomic_json(canonical)
compatibility = os.environ["FULLSTACK_SUMMARY_JSON"]
if compatibility and Path(compatibility) != canonical:
    atomic_json(Path(compatibility))

latest = Path(os.environ["FULLSTACK_LATEST_POINTER"])
latest.parent.mkdir(parents=True, exist_ok=True)
temporary_link = latest.parent / f".{latest.name}.{os.getpid()}"
try:
    temporary_link.unlink(missing_ok=True)
    temporary_link.symlink_to(canonical.parent.name, target_is_directory=True)
    os.replace(temporary_link, latest)
finally:
    temporary_link.unlink(missing_ok=True)

print(f"Stage summary written to {canonical}")
if compatibility and Path(compatibility) != canonical:
    print(f"Compatibility summary written to {compatibility}")
PY
}

release_stage_lock() {
  if [ -n "$LOCK_PID" ]; then
    kill "$LOCK_PID" 2>/dev/null || true
    wait "$LOCK_PID" 2>/dev/null || true
    LOCK_PID=
  fi
}

stage_needs_lock() {
  case "$1" in
    api|browser-routes|browser-interactions|browser-inventory|browser-compat|optional) return 0 ;;
    backend) [ -n "${SPOTIFY_STATS_TEST_SOURCE_DB:-}" ] ;;
    *) return 1 ;;
  esac
}

acquire_stage_lock() {
  lock_stage=$1
  LOCK_STATUS_FILE=$RUN_DIR/lock-$(printf '%s' "$lock_stage" | tr '-' '_').json
  rm -f "$LOCK_STATUS_FILE"
  git_head=$(git rev-parse HEAD 2>/dev/null || true)
  "$REPORT_PYTHON" scripts/fullstack_verification_lock.py \
    --lock-file "$FULLSTACK_LOCK_FILE" \
    --metadata-file "$FULLSTACK_LOCK_METADATA_FILE" \
    --status-file "$LOCK_STATUS_FILE" \
    --run-id "$RUN_ID" \
    --worktree "$ROOT_DIR" \
    --git-sha "$git_head" \
    --stage "$lock_stage" \
    --parent-pid "$$" &
  LOCK_PID=$!

  attempts=0
  while [ ! -f "$LOCK_STATUS_FILE" ] && kill -0 "$LOCK_PID" 2>/dev/null; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 200 ]; then
      echo "Shared-stage lock acquisition timed out: $FULLSTACK_LOCK_FILE" >&2
      release_stage_lock
      return 3
    fi
    sleep 0.05
  done

  lock_status=$("$REPORT_PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["status"])' "$LOCK_STATUS_FILE" 2>/dev/null || true)
  if [ "$lock_status" != "acquired" ]; then
    echo "Shared-stage lock is held by another SpotifyStats verification run:" >&2
    cat "$LOCK_STATUS_FILE" >&2 2>/dev/null || true
    wait "$LOCK_PID" 2>/dev/null || true
    LOCK_PID=
    return 3
  fi
}

finalize_report() {
  script_exit_code=$?
  release_stage_lock
  if [ "$REPORT_INITIALIZED" = "1" ]; then
    write_summary "$script_exit_code" || echo "Failed to write stage summary: $RUN_SUMMARY_JSON" >&2
    rm -f "$RESULTS_FILE"
  fi
}
trap finalize_report 0

if [ "$DRY_RUN" = "1" ]; then
  echo "Selection mode: $SELECTION_MODE"
  echo "Selected stages: $SELECTED_STAGES"
  echo "Full-stack status: PARTIAL (dry run; no checks executed)"
  exit 0
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

run_without_proxy() {
  run env \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY \
    -u http_proxy -u https_proxy -u all_proxy \
    "$@"
}

detect_playwright_python() {
  for candidate in "${PYTHON_PLAYWRIGHT:-}" python3 python "$ROOT_DIR/.venv/bin/python"; do
    [ -n "$candidate" ] || continue
    resolved=$(command -v "$candidate" 2>/dev/null || true)
    [ -n "$resolved" ] || continue
    if "$resolved" - <<'PY' >/dev/null 2>&1
import playwright.sync_api
PY
    then
      printf '%s\n' "$resolved"
      return 0
    fi
  done
  return 1
}

ensure_playwright_python() {
  if [ -n "$PYTHON_PLAYWRIGHT_RESOLVED" ]; then
    return 0
  fi
  PYTHON_PLAYWRIGHT_RESOLVED=$(detect_playwright_python || true)
  if [ -z "$PYTHON_PLAYWRIGHT_RESOLVED" ]; then
    echo "No Python executable can import playwright.sync_api; set PYTHON_PLAYWRIGHT or pass --skip-cross-browser." >&2
    return 3
  fi
  export PYTHON_PLAYWRIGHT="$PYTHON_PLAYWRIGHT_RESOLVED"
}

check_backend_health() {
  command -v curl >/dev/null 2>&1 || {
    echo "curl is required for backend health checks." >&2
    return 3
  }
  curl --noproxy '*' -fsS "$BACKEND_URL/api/health" >/dev/null 2>&1 || {
    echo "Backend health check is blocked: $BACKEND_URL/api/health" >&2
    return 3
  }
}

check_browser_health() {
  check_backend_health || return $?
  curl --noproxy '*' -fsS "$FRONTEND_URL" >/dev/null 2>&1 || {
    echo "Frontend health check is blocked: $FRONTEND_URL" >&2
    return 3
  }
}

run_web_vitals_probe() {
  base_url=$1
  api_base_url=${2:-}
  include_resource_budgets=${3:-0}

  set -- node scripts/frontend_web_vitals_probe.mjs --base-url "$base_url"
  if [ -n "$api_base_url" ]; then
    set -- "$@" --api-base-url "$api_base_url"
  fi
  set -- "$@" --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
  if [ -n "$WEB_VITALS_MAX_LCP_MS" ]; then
    set -- "$@" --max-lcp-ms "$WEB_VITALS_MAX_LCP_MS"
  fi
  if [ -n "$WEB_VITALS_MAX_CLS" ]; then
    set -- "$@" --max-cls "$WEB_VITALS_MAX_CLS"
  fi
  if [ -n "$WEB_VITALS_MAX_TBT_MS" ]; then
    set -- "$@" --max-tbt-ms "$WEB_VITALS_MAX_TBT_MS"
  fi
  if [ "$include_resource_budgets" = "1" ] && [ -n "$WEB_VITALS_MAX_RESOURCE_COUNT" ]; then
    set -- "$@" --max-resource-count "$WEB_VITALS_MAX_RESOURCE_COUNT"
  fi
  if [ "$include_resource_budgets" = "1" ] && [ -n "$WEB_VITALS_MAX_ENCODED_RESOURCE_KB" ]; then
    set -- "$@" --max-encoded-resource-kb "$WEB_VITALS_MAX_ENCODED_RESOURCE_KB"
  fi
  if [ -n "$WEB_VITALS_MAX_SCROLL_OVERFLOW_PX" ]; then
    set -- "$@" --max-scroll-overflow-px "$WEB_VITALS_MAX_SCROLL_OVERFLOW_PX"
  fi

  run "$@"
}

run_resource_snapshot() {
  set -- python scripts/runtime_resource_probe.py --backend-url "$BACKEND_URL" --frontend-url "$FRONTEND_URL" --json-output "$RESOURCE_SNAPSHOT_JSON" --fail-on-missing
  if [ -n "$PREVIEW_URL" ]; then
    set -- "$@" --preview-url "$PREVIEW_URL"
  fi
  if [ -n "$RESOURCE_MAX_TOTAL_RSS_MB" ]; then
    set -- "$@" --max-total-rss-mb "$RESOURCE_MAX_TOTAL_RSS_MB"
  fi
  if [ -n "$RESOURCE_MAX_TOTAL_CPU_PERCENT" ]; then
    set -- "$@" --max-total-cpu-percent "$RESOURCE_MAX_TOTAL_CPU_PERCENT"
  fi

  run "$@"
}

run_quickstart_preflight() {
  run python scripts/quickstart_smoke.py --backend-url "$BACKEND_URL" --frontend-url "$FRONTEND_URL" --require-running --json-output "$QUICKSTART_JSON"
}

stage_preflight() {
  run git diff --check || return $?
  run python scripts/fullstack_preflight.py || return $?
  run python scripts/docs_audit.py --include-archive || return $?
  run python scripts/openapi_operation_audit.py --json-output "$OPENAPI_OPERATION_AUDIT_JSON" || return $?
  run python scripts/openapi_parameter_boundary_audit.py --json-output "$OPENAPI_PARAMETER_BOUNDARY_AUDIT_JSON" || return $?
}

stage_quality() {
  run pre-commit run --all-files || return $?
  run sh scripts/phase5_check.sh --skip-backend-tests || return $?
}

stage_backend() {
  run pytest backend/tests/ -q || return $?
}

stage_api() {
  check_backend_health || return $?
  if [ -n "${SPOTIFY_STATS_TEST_SOURCE_DB:-}" ]; then
    run python scripts/api_smoke_probe.py --db-path "$SPOTIFY_STATS_TEST_SOURCE_DB" || return $?
    run python scripts/api_boundary_probe.py --db-path "$SPOTIFY_STATS_TEST_SOURCE_DB" || return $?
  else
    run python scripts/api_smoke_probe.py || return $?
    run python scripts/api_boundary_probe.py || return $?
  fi
  run_without_proxy python scripts/benchmark_api.py --base-url "$BACKEND_URL" --runs "$BENCHMARK_RUNS" --slow-ms "$SLOW_MS" --fail-on-slow --json-output "$BENCHMARK_JSON" || return $?
}

stage_browser_routes() {
  check_browser_health || return $?
  run node scripts/frontend_route_smoke.mjs --base-url "$FRONTEND_URL" --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes || return $?
  run node scripts/frontend_route_smoke.mjs --base-url "$FRONTEND_URL" --routes /,/analysis/stats,/yearly-review,/billboard/records,/music/search,/settings --viewport matrix --wait-ms 3000 --max-scroll-overflow 0 --fail-on-console-warning || return $?
}

stage_browser_interactions() {
  check_browser_health || return $?
  run node scripts/frontend_interaction_smoke.mjs --base-url "$FRONTEND_URL" || return $?
  run node scripts/frontend_interaction_smoke.mjs --base-url "$FRONTEND_URL" --viewport mobile --scenarios mobile-bottom-navigation,mobile-section-sheet,mobile-time-filter || return $?
  run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$FRONTEND_URL" || return $?
  run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$FRONTEND_URL" --viewport mobile --scenarios mobile-tap-tooltip,mobile-fullscreen || return $?
}

stage_browser_inventory() {
  check_browser_health || return $?
  run node scripts/frontend_control_inventory_smoke.mjs --base-url "$FRONTEND_URL" --viewport both --include-detail-routes || return $?
  run node scripts/frontend_long_list_smoke.mjs --base-url "$FRONTEND_URL" || return $?
}

stage_browser_compat() {
  if [ "$RUN_CROSS_BROWSER" = "0" ]; then
    echo "SKIPPED: browser-compat (--skip-cross-browser)"
    return 4
  fi
  check_browser_health || return $?
  ensure_playwright_python || return $?
  run node scripts/frontend_cross_browser_smoke.mjs --base-url "$FRONTEND_URL" --python "$PYTHON_PLAYWRIGHT" --include-detail-routes || return $?
}

stage_optional() {
  optional_ran=0
  if ! optional_requested; then
    echo "SKIPPED: optional (no optional probe was requested)"
    return 4
  fi
  check_browser_health || return $?

  if [ "$RUN_QUICKSTART_PREFLIGHT" = "1" ]; then
    optional_ran=1
    run_quickstart_preflight || return $?
  fi

  if [ "$RUN_RESOURCE_SNAPSHOT" = "1" ]; then
    optional_ran=1
    run_resource_snapshot || return $?
  fi

  if [ "$RUN_WEB_VITALS" = "1" ]; then
    optional_ran=1
    if [ -z "$PREVIEW_URL" ] && { [ -n "$WEB_VITALS_MAX_RESOURCE_COUNT" ] || [ -n "$WEB_VITALS_MAX_ENCODED_RESOURCE_KB" ]; }; then
      echo "Skipping resource count/encoded resource Web Vitals budgets for dev server; set --preview-url to enforce production bundle resource budgets."
    fi
    run_web_vitals_probe "$FRONTEND_URL" "" 0 || return $?
  fi

  if [ -n "$PREVIEW_URL" ]; then
    optional_ran=1
    run node scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --viewport both --max-scroll-overflow 0 --fail-on-console-warning --include-detail-routes || return $?
    run node scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --routes /,/analysis/stats,/yearly-review,/billboard/records,/music/search,/settings --viewport matrix --wait-ms 3000 --max-scroll-overflow 0 --fail-on-console-warning || return $?
    run node scripts/frontend_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" || return $?
    run node scripts/frontend_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --viewport mobile --scenarios mobile-bottom-navigation,mobile-section-sheet,mobile-time-filter || return $?
    run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" || return $?
    run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --viewport mobile --scenarios mobile-tap-tooltip,mobile-fullscreen || return $?
    run node scripts/frontend_control_inventory_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --viewport both --include-detail-routes || return $?
    run node scripts/frontend_long_list_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" || return $?
    if [ "$RUN_CROSS_BROWSER" = "1" ]; then
      ensure_playwright_python || return $?
      run node scripts/frontend_cross_browser_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --python "$PYTHON_PLAYWRIGHT" --include-detail-routes || return $?
    fi
    if [ "$RUN_WEB_VITALS" = "1" ]; then
      run_web_vitals_probe "$PREVIEW_URL" "$PREVIEW_API_URL" 1 || return $?
    fi
  fi

  [ "$optional_ran" = "1" ]
}

stage_function() {
  case "$1" in
    preflight) echo stage_preflight ;;
    quality) echo stage_quality ;;
    backend) echo stage_backend ;;
    api) echo stage_api ;;
    browser-routes) echo stage_browser_routes ;;
    browser-interactions) echo stage_browser_interactions ;;
    browser-inventory) echo stage_browser_inventory ;;
    browser-compat) echo stage_browser_compat ;;
    optional) echo stage_optional ;;
  esac
}

run_selected_stage() {
  stage_name=$1
  stage_runner=$(stage_function "$stage_name")
  stage_started_ms=$(epoch_ms)
  printf '\n=== Stage: %s ===\n' "$stage_name"
  if stage_needs_lock "$stage_name"; then
    if acquire_stage_lock "$stage_name"; then
      if "$stage_runner"; then
        stage_exit_code=0
      else
        stage_exit_code=$?
      fi
      release_stage_lock
    else
      stage_exit_code=$?
    fi
  else
    if "$stage_runner"; then
      stage_exit_code=0
    else
      stage_exit_code=$?
    fi
  fi
  stage_finished_ms=$(epoch_ms)
  stage_duration_ms=$((stage_finished_ms - stage_started_ms))

  case "$stage_exit_code" in
    0) stage_status=PASS ;;
    3) stage_status=BLOCKED ;;
    4) stage_status=SKIPPED ;;
    *) stage_status=FAIL ;;
  esac
  record_stage "$stage_name" "$stage_status" "$stage_duration_ms"
  printf '=== Stage result: %s %s (%sms) ===\n' "$stage_name" "$stage_status" "$stage_duration_ms"

  case "$stage_status" in
    FAIL) exit "$stage_exit_code" ;;
    BLOCKED) exit 1 ;;
  esac
}

for stage in $ALL_STAGES; do
  if contains_stage "$SELECTED_STAGES" "$stage"; then
    run_selected_stage "$stage"
  fi
done

if [ "$SELECTION_MODE" = "full" ] && [ "$RUN_CROSS_BROWSER" = "1" ]; then
  OVERALL_STATUS=PASS
  printf '\nFull-stack verification matrix completed.\n'
else
  OVERALL_STATUS=PARTIAL
  printf '\nSelected full-stack verification stages completed.\n'
fi
printf 'Full-stack status: %s\n' "$OVERALL_STATUS"
