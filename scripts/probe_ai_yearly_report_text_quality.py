#!/usr/bin/env python3
"""Probe generated yearly AI report text through the HTTP API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db  # noqa: E402
from backend.domains.ai_reports.yearly_validator import validate_yearly_report  # noqa: E402
from backend.services.ai_insights_service import _gather_yearly_data  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    data = _load_validation_data(args.year)
    response = _fetch_yearly_report(args.base_url, args.year, args.force, args.timeout)
    if not response.get("success"):
        print(json.dumps(response, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    report = str(response.get("report") or "")
    validation = validate_yearly_report(report, data)
    summary = {
        "year": args.year,
        "base_url": args.base_url,
        "cached": response.get("cached"),
        "report_length": len(report),
        "ok": validation.ok,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "severity": issue.severity,
            }
            for issue in validation.issues
        ],
        "report_preview": report[:1200],
    }

    if args.json_output:
        args.json_output.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if not validation.ok:
        return 1
    return 0


def _load_validation_data(year: int) -> dict:
    conn = get_db(readonly=True)
    try:
        return _gather_yearly_data(
            conn,
            min_ms=30000,
            music_only=True,
            merge_enabled=True,
            year=year,
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
        )
    finally:
        conn.close()


def _fetch_yearly_report(
    base_url: str,
    year: int,
    force: bool,
    timeout: float,
) -> dict:
    query = urlencode(
        {
            "year": year,
            "force": str(force).lower(),
            "min_ms": 30000,
            "music_only": "true",
            "merge_enabled": "true",
            "dynamic_threshold": "true",
        }
    )
    url = f"{base_url.rstrip('/')}/api/ai-insights/yearly-story?{query}"
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "status": exc.code, "error": body}
    except (URLError, TimeoutError) as exc:
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    raise SystemExit(main())
