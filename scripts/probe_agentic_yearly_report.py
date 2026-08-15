#!/usr/bin/env python3
"""Probe agentic yearly report quality through the observable task API."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

FORBIDDEN_PARTIAL_TERMS = (
    "年度专辑",
    "年度单曲",
    "年度冠军",
    "全年冠军",
    "来年寄语",
)
PERSONAL_BILLBOARD_TOOLS = {"personal_billboard_year_end", "billboard_yearly_diagnostics"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--min-length", type=int, default=1400)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    created = _create_task(args.base_url, args.year, args.timeout)
    task_id = str(created.get("task_id") or "")
    if not task_id:
        return _finish(
            {
                "ok": False,
                "issues": ["task_create_failed"],
                "create_response": created,
            },
            args.json_output,
        )

    task = _poll_task(args.base_url, task_id, args.timeout, args.poll_interval)
    events_payload = _fetch_json(args.base_url, f"/api/ai/tasks/{task_id}/events", args.timeout)
    summary = _summarize(args.year, task, events_payload, args.min_length)
    return _finish(summary, args.json_output)


def _create_task(base_url: str, year: int, timeout: float) -> dict:
    payload = {
        "report_type": "yearly",
        "action": "generate",
        "force": True,
        "report_mode": "agentic_longform",
        "year": year,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 5,
    }
    return _fetch_json(base_url, "/api/ai/tasks/report", timeout, method="POST", payload=payload)


def _poll_task(
    base_url: str,
    task_id: str,
    timeout: float,
    poll_interval: float,
) -> dict:
    deadline = time.monotonic() + timeout
    last_payload: dict = {}
    while time.monotonic() < deadline:
        last_payload = _fetch_json(base_url, f"/api/ai/tasks/{task_id}", timeout)
        status = str(last_payload.get("status") or "")
        if status in {"done", "error", "cancelled"}:
            return last_payload
        time.sleep(poll_interval)
    return {
        "found": True,
        "status": "timeout",
        "task_id": task_id,
        "message": f"task did not finish within {timeout:.0f}s",
        "last_payload": last_payload,
    }


def _summarize(
    year: int,
    task: dict,
    events_payload: dict,
    min_length: int,
) -> dict:
    result = task.get("result") if isinstance(task.get("result"), dict) else {}
    report = str(result.get("report") or "")
    metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    critic = result.get("critic") if isinstance(result.get("critic"), dict) else {}
    fact_validation = (
        result.get("fact_validation") if isinstance(result.get("fact_validation"), dict) else {}
    )
    tool_calls = (
        events_payload.get("tool_calls")
        if isinstance(events_payload.get("tool_calls"), list)
        else []
    )
    tool_names = [
        str(call.get("tool_name") or "")
        for call in tool_calls
        if isinstance(call, dict) and call.get("tool_name")
    ]
    issues = _quality_issues(
        task=task,
        report=report,
        metadata=metadata,
        critic=critic,
        fact_validation=fact_validation,
        tool_names=tool_names,
        min_length=min_length,
    )
    return {
        "ok": not issues,
        "issues": issues,
        "year": year,
        "task_id": task.get("task_id"),
        "task_status": task.get("status"),
        "metadata": metadata,
        "critic": critic,
        "fact_validation": fact_validation,
        "report_length": len(report),
        "tool_call_count": len(tool_names),
        "tool_names": tool_names,
        "event_count": len(events_payload.get("events") or []),
        "preview": report[:1200],
    }


def _quality_issues(
    *,
    task: dict,
    report: str,
    metadata: dict,
    critic: dict,
    fact_validation: dict,
    tool_names: list[str],
    min_length: int,
) -> list[str]:
    issues: list[str] = []
    if task.get("status") != "done":
        issues.append(f"task_not_done:{task.get('status')}")
    if metadata.get("report_mode") != "agentic_longform":
        issues.append("missing_agentic_report_mode")
    if metadata.get("contract_version") != "agentic_yearly_v14":
        issues.append("wrong_contract_version")
    if metadata.get("fallback_level") is not None:
        issues.append(f"unexpected_fallback:{metadata.get('fallback_level')}")
    if metadata.get("critic_passed") is not True:
        issues.append("critic_not_passed")
    if critic and critic.get("ok") is not True:
        issues.append("critic_payload_not_ok")
    if fact_validation and fact_validation.get("ok") is not True:
        codes = [
            str(issue.get("code") or "")
            for issue in fact_validation.get("issues") or []
            if isinstance(issue, dict)
        ]
        issues.append(f"fact_validation_not_ok:{','.join(codes)}")
    if len(report) < min_length:
        issues.append(f"report_too_short:{len(report)}")
    if int(metadata.get("tool_calls") or 0) < 6:
        issues.append("metadata_too_few_tool_calls")
    if len(tool_names) < 6:
        issues.append("persisted_too_few_tool_calls")
    if len(PERSONAL_BILLBOARD_TOOLS.intersection(tool_names)) < 2:
        issues.append("missing_personal_billboard_tool_calls")
    forbidden_hits = [term for term in FORBIDDEN_PARTIAL_TERMS if term in report]
    if forbidden_hits:
        issues.append(f"forbidden_partial_terms:{','.join(forbidden_hits)}")
    if "个人 Billboard" not in report and "个人榜" not in report:
        issues.append("missing_personal_billboard_text")
    if "播放" not in report:
        issues.append("missing_playback_text")
    return issues


def _fetch_json(
    base_url: str,
    path: str,
    timeout: float,
    *,
    method: str = "GET",
    payload: dict | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if method == "GET" and payload:
        url = f"{url}?{urlencode(payload)}"
        data = None
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {"success": False, "status": exc.code, "error": body}
    except (URLError, TimeoutError) as exc:
        return {"success": False, "error": str(exc)}


def _finish(summary: dict, json_output: Path | None) -> int:
    if json_output:
        json_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    if not summary.get("ok"):
        for issue in summary.get("issues") or []:
            print(f"FAIL: {issue}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
