#!/usr/bin/env python3
"""Static checker for the AI question matrix document."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MATRIX_PATH = ROOT / "docs" / "verification" / "2026-07-03-ai-question-test-matrix.md"
DEFAULT_GOLDEN_PATH = ROOT / "backend" / "tests" / "fixtures" / "ai_agent_golden_questions.json"

_TABLE_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|")
_CASE_ID_RE = re.compile(r"^[A-Z][A-Z0-9-]*-\d+$|^P0-\d+$")
_REQUIRED_P0_IDS = {f"P0-{index:02d}" for index in range(1, 13)}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"matrix file not found: {path}") from None


def _extract_case_ids(markdown: str) -> list[str]:
    ids: list[str] = []
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or "---" in line:
            continue
        match = _TABLE_ROW_RE.match(line)
        if match is None:
            continue
        candidate = match.group(1).strip(" `")
        if _CASE_ID_RE.match(candidate):
            ids.append(candidate)
    return ids


def _duplicates(values: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _golden_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def evaluate_matrix(matrix_path: Path, golden_path: Path) -> dict[str, Any]:
    markdown = _read(matrix_path)
    case_ids = _extract_case_ids(markdown)
    duplicate_ids = _duplicates(case_ids)
    p0_ids = [case_id for case_id in case_ids if case_id.startswith("P0-")]
    missing_p0 = sorted(_REQUIRED_P0_IDS - set(p0_ids))
    section_prefixes = sorted({case_id.split("-", 1)[0] for case_id in case_ids})
    failures: list[str] = []
    if duplicate_ids:
        failures.append(f"duplicate ids: {duplicate_ids}")
    if missing_p0:
        failures.append(f"missing P0 ids: {missing_p0}")
    if len(case_ids) < 80:
        failures.append(f"too few matrix questions: {len(case_ids)} < 80")
    if _golden_count(golden_path) < 10:
        failures.append("golden fixture should cover at least 10 core AI harness cases")
    return {
        "ok": not failures,
        "total_questions": len(case_ids),
        "p0_questions": len(p0_ids),
        "section_prefixes": section_prefixes,
        "duplicate_ids": duplicate_ids,
        "missing_p0": missing_p0,
        "golden_cases": _golden_count(golden_path),
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN_PATH)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    args = parser.parse_args()

    result = evaluate_matrix(args.matrix, args.golden)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("AI question matrix evaluation")
        print(f"questions: {result['total_questions']}")
        print(f"P0: {result['p0_questions']}")
        print(f"golden cases: {result['golden_cases']}")
        print(f"sections: {', '.join(result['section_prefixes'])}")
        if result["failures"]:
            print("FAIL")
            for failure in result["failures"]:
                print(f"- {failure}")
        else:
            print("PASS")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
