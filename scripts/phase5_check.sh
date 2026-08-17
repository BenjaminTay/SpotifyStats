#!/usr/bin/env sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

python scripts/docs_audit.py --include-archive
python scripts/ci_baseline_parity.py
pytest -m unit -q
pytest -m contract -q
ruff check backend/

cd frontend
npm test
npm run build
