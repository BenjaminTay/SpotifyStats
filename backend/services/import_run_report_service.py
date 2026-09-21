"""Generate durable, local import run reports from the control plane."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _duration_ms(started_at: str | None, completed_at: str | None) -> int | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return None
    return max(0, round((completed - started).total_seconds() * 1000))


def build_import_run_report(run_id: str, *, db_path: str | None = None) -> dict[str, Any]:
    """Build the inspectable report without exposing it through the ordinary UI."""

    from backend.domains.imports.control_store import get_batch, get_run, latest_stage_attempts

    run = get_run(run_id, db_path=db_path)
    if run is None:
        raise KeyError(run_id)
    batch = get_batch(str(run["batch_id"]), db_path=db_path)
    stages = latest_stage_attempts(run_id, db_path=db_path)
    stage_reports = []
    errors: list[dict[str, Any]] = []
    for stage in stages:
        evidence = stage.get("output_evidence") or {}
        evidence_contract = evidence.get("evidence_contract") or {}
        item = {
            "stage": stage["stage"],
            "attempt": stage["attempt"],
            "status": stage["status"],
            "target_generation_id": stage["target_generation_id"],
            "target_dataset_digest": stage["target_dataset_digest"],
            "strategy": stage.get("strategy"),
            "fallback_reason": stage.get("fallback_reason"),
            "queued_at": stage.get("queued_at"),
            "started_at": stage.get("started_at"),
            "completed_at": stage.get("completed_at"),
            "duration_ms": _duration_ms(stage.get("started_at"), stage.get("completed_at")),
            "output": evidence,
            "scope": evidence_contract.get("scope"),
            "denominator": evidence_contract.get("denominator"),
            "problem_count": evidence_contract.get("problem_count"),
            "affected_play_count": evidence_contract.get("affected_play_count"),
            "affected_ms": evidence_contract.get("affected_ms"),
            "error_code": stage.get("error_code"),
            "retryable": bool(stage.get("retryable")),
        }
        stage_reports.append(item)
        if stage.get("error_code"):
            errors.append(
                {
                    "scope": "stage",
                    "stage": stage["stage"],
                    "error_code": stage["error_code"],
                    "retryable": bool(stage.get("retryable")),
                }
            )
    if run.get("error_code"):
        errors.insert(
            0,
            {
                "scope": "run",
                "error_code": run["error_code"],
                "retryable": bool(run.get("retryable")),
            },
        )
    plan = run.get("plan") or {}
    result = run.get("result") or {}
    critical = next(
        (item.get("output") or {} for item in stage_reports if item["stage"] == "critical_prewarm"),
        {},
    )
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "status": run["status"],
        "publication_state": run["publication_state"],
        "report_status": run.get("report_status"),
        "report_error_code": run.get("report_error_code"),
        "input": {
            "batch_id": run["batch_id"],
            "kind": batch.get("kind") if batch else None,
            "manifest_digest": batch.get("manifest_digest") if batch else None,
            "parent_source_version_id": (batch.get("parent_source_version_id") if batch else None),
            "detected_relation": run.get("detected_relation"),
            "baseline_reason_code": run.get("baseline_reason_code"),
        },
        "execution": {
            "requested_mode": run.get("requested_mode"),
            "strategy": result.get("executed_strategy") or run.get("strategy"),
            "old_generation_id": run.get("old_generation_id"),
            "new_generation_id": run.get("new_generation_id"),
            "old_dataset_digest": run.get("old_dataset_digest"),
            "new_dataset_digest": run.get("new_dataset_digest"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "duration_ms": _duration_ms(run.get("started_at"), run.get("completed_at")),
        },
        "conservation": {
            "existing_count": plan.get("existing_count"),
            "incoming_count": plan.get("incoming_count"),
            "unchanged_count": plan.get("unchanged_count"),
            "added_count": plan.get("added_count"),
            "removed_count": plan.get("removed_count"),
            "inserted_records": result.get("inserted_records"),
            "active_records": result.get("active_records"),
        },
        "stages": stage_reports,
        "quality": {
            "status": critical.get("status"),
            "warning_count": critical.get("warning_count"),
            "blocker_count": critical.get("blocker_count"),
            "cover": next(
                (
                    item.get("output") or {"status": item["status"]}
                    for item in stage_reports
                    if item["stage"] == "cover_supplemental"
                ),
                None,
            ),
        },
        "recovery": {
            "status": run.get("recovery_status"),
            "database_snapshot_path": run.get("database_snapshot_path"),
            "old_source_version_id": run.get("old_source_version_id"),
        },
        "errors": errors,
    }


def render_import_run_markdown(report: dict[str, Any]) -> str:
    execution = report["execution"]
    conservation = report["conservation"]
    lines = [
        f"# 导入运行报告 {report['run_id']}",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- 任务状态：{report['status']}",
        f"- 发布状态：{report['publication_state']}",
        f"- 输入关系：{report['input'].get('detected_relation') or 'unknown'}",
        f"- 实际策略：{execution.get('strategy') or 'unknown'}",
        f"- 新增 / 移除：{conservation.get('added_count')} / {conservation.get('removed_count')}",
        f"- 最终输入记录：{conservation.get('incoming_count')}",
        "",
        "## 阶段",
        "",
        "| 阶段 | attempt | 状态 | 策略 | 回退原因 | 耗时 ms |",
        "| --- | ---: | --- | --- | --- | ---: |",
    ]
    for stage in report["stages"]:
        lines.append(
            "| {stage} | {attempt} | {status} | {strategy} | {fallback} | {duration} |".format(
                stage=stage["stage"],
                attempt=stage["attempt"],
                status=stage["status"],
                strategy=stage.get("strategy") or "-",
                fallback=stage.get("fallback_reason") or "-",
                duration=stage.get("duration_ms") if stage.get("duration_ms") is not None else "-",
            )
        )
    lines.extend(["", "## 错误与恢复", ""])
    if report["errors"]:
        lines.extend(
            f"- {item['scope']}：{item['error_code']}（可重试：{item['retryable']}）"
            for item in report["errors"]
        )
    else:
        lines.append("- 无")
    lines.append(f"- 恢复状态：{report['recovery'].get('status') or 'not_needed'}")
    return "\n".join(lines) + "\n"


def write_import_run_reports(run_id: str, *, db_path: str | None = None) -> dict[str, Path]:
    """Atomically publish JSON and Markdown reports beside the control database."""

    from backend.domains.imports.control_store import control_root

    report = build_import_run_report(run_id, db_path=db_path)
    root = control_root(db_path) / "reports"
    root.mkdir(parents=True, exist_ok=True)
    try:
        root.chmod(0o700)
    except OSError:
        pass
    outputs = {
        "json": root / f"{run_id}.json",
        "markdown": root / f"{run_id}.md",
    }
    payloads = {
        "json": json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        "markdown": render_import_run_markdown(report),
    }
    for kind, target in outputs.items():
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(payloads[kind], encoding="utf-8")
        os.chmod(temporary, 0o600)
        temporary.replace(target)
    return outputs
