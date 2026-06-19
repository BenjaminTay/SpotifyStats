#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

BACKEND_URL=${BACKEND_URL:-http://127.0.0.1:8000}
FRONTEND_URL=${FRONTEND_URL:-http://127.0.0.1:5173}
PREVIEW_URL=${PREVIEW_URL:-}
PREVIEW_API_URL=${PREVIEW_API_URL:-$BACKEND_URL}
BENCHMARK_RUNS=${BENCHMARK_RUNS:-3}
SLOW_MS=${SLOW_MS:-500}
BENCHMARK_JSON=${BENCHMARK_JSON:-/tmp/spotify_api_benchmark.json}
RUN_CROSS_BROWSER=${RUN_CROSS_BROWSER:-1}
RUN_WEB_VITALS=${RUN_WEB_VITALS:-0}

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

usage() {
  cat <<'EOF'
Usage:
  sh scripts/fullstack_verification_check.sh [options]

Runs the non-destructive full-stack verification matrix. Start the backend
and frontend dev server before running the default command:
  source .venv/bin/activate && SPOTIFY_STATS_WARMUP=0 uvicorn backend.main:app --host 127.0.0.1 --port 8000
  cd frontend && npm run dev -- --host 127.0.0.1 --port 5173

Options:
  --backend-url <url>       Backend URL for API benchmark, default http://127.0.0.1:8000
  --frontend-url <url>      Frontend dev URL for browser smoke, default http://127.0.0.1:5173
  --preview-url <url>      Optional Vite preview URL; when set, preview smoke also runs
  --preview-api-url <url>  Backend URL used by preview smoke request rewriting
  --benchmark-runs <n>     Number of benchmark requests per endpoint, default 3
  --slow-ms <ms>           API hot P95 slow threshold, default 500
  --benchmark-json <path>  JSON benchmark output path, default /tmp/spotify_api_benchmark.json
  --skip-cross-browser    Skip Playwright Chromium/Firefox/WebKit smoke
  --web-vitals            Run Web Vitals lab probes for dev and preview URLs
  -h, --help              Show this help

Environment variables with the same uppercase names can also configure the
defaults: BACKEND_URL, FRONTEND_URL, PREVIEW_URL, PREVIEW_API_URL,
BENCHMARK_RUNS, SLOW_MS, BENCHMARK_JSON, RUN_CROSS_BROWSER, RUN_WEB_VITALS.
When cross-browser smoke is enabled, PYTHON_PLAYWRIGHT may point to a Python
that can import playwright.sync_api; otherwise the script auto-detects one
before activating .venv.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --backend-url)
      shift
      BACKEND_URL=$1
      ;;
    --frontend-url)
      shift
      FRONTEND_URL=$1
      ;;
    --preview-url)
      shift
      PREVIEW_URL=$1
      ;;
    --preview-api-url)
      shift
      PREVIEW_API_URL=$1
      ;;
    --benchmark-runs)
      shift
      BENCHMARK_RUNS=$1
      ;;
    --slow-ms)
      shift
      SLOW_MS=$1
      ;;
    --benchmark-json)
      shift
      BENCHMARK_JSON=$1
      ;;
    --skip-cross-browser)
      RUN_CROSS_BROWSER=0
      ;;
    --web-vitals)
      RUN_WEB_VITALS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$RUN_CROSS_BROWSER" = "1" ]; then
  PYTHON_PLAYWRIGHT=$(detect_playwright_python || true)
  if [ -z "$PYTHON_PLAYWRIGHT" ]; then
    echo "No Python executable can import playwright.sync_api; set PYTHON_PLAYWRIGHT or pass --skip-cross-browser." >&2
    exit 1
  fi
  export PYTHON_PLAYWRIGHT
fi

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

run() {
  printf '\n==> %s\n' "$*"
  "$@"
}

run pytest backend/tests/ -q
run pre-commit run --all-files
run sh scripts/phase5_check.sh

run python scripts/api_smoke_probe.py
run python scripts/api_boundary_probe.py
run python scripts/benchmark_api.py --base-url "$BACKEND_URL" --runs "$BENCHMARK_RUNS" --slow-ms "$SLOW_MS" --fail-on-slow --json-output "$BENCHMARK_JSON"

run node scripts/frontend_route_smoke.mjs --base-url "$FRONTEND_URL" --viewport both --max-scroll-overflow 0
run node scripts/frontend_interaction_smoke.mjs --base-url "$FRONTEND_URL"
run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$FRONTEND_URL"
run node scripts/frontend_long_list_smoke.mjs --base-url "$FRONTEND_URL"

if [ "$RUN_CROSS_BROWSER" = "1" ]; then
  run node scripts/frontend_cross_browser_smoke.mjs --base-url "$FRONTEND_URL" --python "$PYTHON_PLAYWRIGHT"
fi

if [ "$RUN_WEB_VITALS" = "1" ]; then
  run node scripts/frontend_web_vitals_probe.mjs --base-url "$FRONTEND_URL" --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
fi

if [ -n "$PREVIEW_URL" ]; then
  run node scripts/frontend_route_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --viewport both --max-scroll-overflow 0
  run node scripts/frontend_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"
  run node scripts/frontend_chart_interaction_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"
  run node scripts/frontend_long_list_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL"
  if [ "$RUN_CROSS_BROWSER" = "1" ]; then
    run node scripts/frontend_cross_browser_smoke.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --python "$PYTHON_PLAYWRIGHT"
  fi
  if [ "$RUN_WEB_VITALS" = "1" ]; then
    run node scripts/frontend_web_vitals_probe.mjs --base-url "$PREVIEW_URL" --api-base-url "$PREVIEW_API_URL" --routes /,/analysis/stats,/analysis/charts,/billboard/number-ones,/account,/settings --viewport both --wait-ms 5000
  fi
fi

printf '\nFull-stack verification matrix completed.\n'
