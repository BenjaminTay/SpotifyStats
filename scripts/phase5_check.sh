#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

SKIP_BACKEND_TESTS=0

usage() {
  cat <<'EOF'
Usage:
  sh scripts/phase5_check.sh [options]

Standalone default still runs every Phase 5 check used by the shared quality
workflow. Skip flags are intended for a parent gate that executes the same
checks elsewhere in the same invocation; skipped checks are always printed.

Options:
  --skip-backend-tests  Skip unit and contract pytest commands
  -h, --help            Show this help
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --skip-backend-tests)
      SKIP_BACKEND_TESTS=1
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

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

python scripts/docs_audit.py --include-archive
python scripts/ci_baseline_parity.py
if [ "$SKIP_BACKEND_TESTS" = "1" ]; then
  echo "SKIPPED: backend unit/contract (owned by the parent full-stack backend stage)"
else
  pytest -m unit -q
  pytest -m contract -q
fi
ruff check backend/

cd frontend
npm test
npm run build
