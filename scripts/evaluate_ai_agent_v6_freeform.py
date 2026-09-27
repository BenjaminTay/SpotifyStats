#!/usr/bin/env python3
"""Run and grade the frozen 24-case AI Agent V6 free-form manifest."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from scripts.evaluate_ai_question_matrix import (
    MatrixCase,
    _api_url,
    _as_dict,
    _as_list,
    _grade_case,
    _http_json,
    _post_chat_task,
    _task_events,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "backend/tests/fixtures/ai_agent_v6_freeform_questions.json"
_TERMINAL_OR_WAITING = {"done", "error", "cancelled", "awaiting_input"}

_REFERENCE_SETUP = {
    "V6-REF-01": "过去一年按播放次数排前三的艺人是谁？",
    "V6-REF-02": "2025 年按收听时长最多的专辑是哪张？",
    "V6-REF-03": "最近三个月我最常听的艺人是谁？",
    "V6-REF-04": "2025 年按播放次数排前三的专辑是什么？",
}

_STEERING = {
    "V6-STR-01": ("steer", "改为只看 2025 年，并排除播客。"),
    "V6-STR-02": ("steer", "改为只比较收听时长，不再比较次数。"),
    "V6-STR-03": ("steer", "补充要求：只看华语，并排除流派维度。"),
    "V6-STR-04": ("followup", "下一轮请比较上一年。"),
}


def _answer(task: dict[str, Any]) -> str:
    result = _as_dict(task.get("result"))
    value = result.get("answer") or result.get("clarification_question")
    return value if isinstance(value, str) else str(task.get("message") or "")


def _poll_task(
    backend_url: str,
    task_id: str,
    *,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    latest: dict[str, Any] = {}
    while time.monotonic() < deadline:
        latest = _http_json("GET", _api_url(backend_url, f"/api/ai/tasks/{task_id}"))
        if latest.get("status") in _TERMINAL_OR_WAITING:
            return latest
        time.sleep(interval)
    raise TimeoutError(f"task {task_id} timed out; last={latest}")


def _tool_observations(events: dict[str, Any]) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for event in _as_list(events.get("trajectory")):
        if not isinstance(event, dict) or event.get("event_type") != "tool_result":
            continue
        payload = _as_dict(event.get("payload"))
        outcome = _as_dict(payload.get("outcome"))
        observations.append(
            {
                "tool_name": str(payload.get("tool_name") or ""),
                "params": _as_dict(payload.get("params")),
                "outcome": outcome,
            }
        )
    return observations


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    folded = text.casefold()
    return any(token.casefold() in folded for token in tokens)


def _semantic_assertions(
    case: dict[str, Any],
    task: dict[str, Any],
    events: dict[str, Any],
    inbox: dict[str, Any] | None,
) -> list[str]:
    failures: list[str] = []
    answer = _answer(task)
    result = _as_dict(task.get("result"))
    observations = _tool_observations(events)
    tool_names = [item["tool_name"] for item in observations]
    joined_params = json.dumps(
        [item["params"] for item in observations], ensure_ascii=False, sort_keys=True
    )
    trajectory = _as_list(events.get("trajectory"))
    event_types = {
        str(event.get("event_type") or "")
        for event in trajectory
        if isinstance(event, dict)
    }
    expected = str(case.get("expected") or "answer")
    status = str(task.get("status") or "")

    if expected == "clarify" and status != "awaiting_input":
        failures.append("预定义结果要求必要澄清，但任务未进入 awaiting_input")
    elif expected == "clarify_or_answer" and status not in {"awaiting_input", "done"}:
        failures.append(f"既未澄清也未回答，状态为 {status}")
    elif expected not in {"clarify", "clarify_or_answer"} and status != "done":
        failures.append(f"预定义结果要求完成回答，状态为 {status}")

    if status == "awaiting_input":
        if "clarification_requested" not in event_types:
            failures.append("awaiting_input 缺少持久 clarification_requested 事件")
        if "？" not in answer and "?" not in answer:
            failures.append("澄清内容不是明确问题")
        if "real_candidates" in case.get("assertions", []):
            has_candidates = any(
                len(_as_list(_as_dict(item["outcome"].get("data")).get("candidates"))) > 1
                for item in observations
            )
            if not has_candidates:
                failures.append("澄清没有来自实体工具的真实候选")
        if "missing_entity" in case.get("assertions", []) and not _contains_any(
            answer, ("专辑名", "名称", "哪一个专辑")
        ):
            failures.append("澄清没有询问缺失的专辑身份")
        return failures

    if not answer.strip():
        failures.append("最终回答为空")
        return failures

    assertions = set(case.get("assertions") or [])
    if "evidence" in assertions and not observations:
        failures.append("需要本地证据但没有工具观察")
    if "artist" in assertions and not _contains_any(
        answer, ("艺人", "歌手", "artist")
    ):
        failures.append("回答没有明确艺人结论")
    if "album" in assertions and not _contains_any(answer, ("专辑", "唱片")):
        failures.append("回答没有明确专辑结论")
    if "tracks" in assertions and not _contains_any(answer, ("歌曲", "曲目", "首")):
        failures.append("回答没有展开曲目")
    if "duration" in assertions and not _contains_any(answer, ("时长", "小时", "分钟")):
        failures.append("回答没有按收听时长作答")
    if "play_count" in assertions and not _contains_any(answer, ("次数", "播放")):
        failures.append("回答没有按播放次数作答")
    if "time_range" in assertions:
        guard = _as_dict(result.get("temporal_guard"))
        interpretation = _as_dict(guard.get("time_interpretation"))
        if not interpretation.get("effective_start_date") or not interpretation.get(
            "effective_end_date"
        ):
            failures.append("回答缺少可核验的实际时间范围")
    if "trend" in assertions and not _contains_any(
        answer, ("变化", "上升", "下降", "趋势", "月", "偏向", "转向")
    ):
        failures.append("回答没有给出变化或趋势结论")
    if "comparison" in assertions and not _contains_any(
        answer, ("相比", "比较", "差", "更", "高于", "低于")
    ):
        failures.append("回答没有完成比较")
    if "context_reference" in assertions:
        if _contains_any(answer, ("不知道刚才", "没有上下文", "无法知道", "未提供")):
            failures.append("回答丢失前序指代上下文")
        if not observations:
            failures.append("指代解析后没有查询本地证据")
    if "constraint_update" in assertions and not _contains_any(
        answer, ("时长", "小时", "分钟")
    ):
        failures.append("次数到时长的约束替换未体现在回答")
    if "metric_scope" in assertions and not _contains_any(
        answer, ("次数", "时长", "口径", "按", "最爱")
    ):
        failures.append("没有明确或澄清“最爱”的指标口径")
    if "time_scope" in assertions and status != "awaiting_input" and not _contains_any(
        answer, ("春", "夏", "月份", "时间范围", "口径")
    ):
        failures.append("没有明确季节比较的年份或时间范围")
    if "entity_identity" in assertions and not _contains_any(
        answer, ("1989", "Taylor's Version", "重录", "版本")
    ):
        failures.append("没有处理 1989 原版/重录版身份")
    if "two_metrics" in assertions and not _contains_any(
        answer, ("次数", "播放")
    ):
        failures.append("组合问题没有覆盖播放次数")
    if "two_metrics" in assertions and not _contains_any(
        answer, ("时长", "小时", "分钟")
    ):
        failures.append("组合问题没有覆盖收听时长")
    if "no_gender_inference" in assertions and not _contains_any(
        answer, ("性别", "女声", "无法", "不能", "不支持", "没有")
    ):
        failures.append("没有说明不能从现有事实推断艺人性别")
    if "language" in assertions and not _contains_any(
        answer, ("语言", "语种", "华语", "英语", "中文")
    ):
        failures.append("回答没有覆盖语言维度")
    if "time_of_day" in assertions and not _contains_any(
        answer, ("时段", "晚上", "夜", "小时", "点")
    ):
        failures.append("回答没有覆盖时段维度")
    if "billboard" in assertions and not _contains_any(
        answer, ("个人 Billboard", "个人榜", "本地个人榜单")
    ):
        failures.append("没有说明 Billboard 是本地个人榜单")
    if "discovery" in assertions and not _contains_any(
        answer, ("发现", "首次", "新听", "能力边界", "无法", "不能")
    ):
        failures.append("回答没有处理新发现维度")
    if "retention" in assertions and not _contains_any(
        answer, ("长期", "持续", "后来", "留存", "无法", "不能")
    ):
        failures.append("回答没有处理长期留存维度")

    if "ranking" in assertions and not any(
        name in {"analysis_charts", "entity_stats", "compare_entities"}
        for name in tool_names
    ):
        failures.append("排名问题未使用排名/实体统计证据")
    if "steer_applied" in assertions:
        if not inbox or inbox.get("accepted") is not True:
            failures.append("运行中补充要求未被接收")
        consumed = [
            event
            for event in trajectory
            if isinstance(event, dict) and event.get("event_type") == "session_input_consumed"
        ]
        if not consumed:
            failures.append("运行中补充要求未在安全步骤持久消费")
    if case["id"] == "V6-STR-01" and "2025" not in answer:
        failures.append("转向后的回答没有限定 2025 年")
    if case["id"] == "V6-STR-02" and not _contains_any(answer, ("时长", "小时")):
        failures.append("转向后的回答仍未使用时长口径")
    if case["id"] == "V6-STR-03":
        if not _contains_any(answer, ("华语", "中文", "语言")):
            failures.append("补充的华语约束未体现")
        if "genre" in joined_params.casefold():
            failures.append("排除流派后仍向工具传入流派维度")
    if "followup_preserved" in assertions:
        if not inbox or inbox.get("accepted") is not True:
            failures.append("临近完成的 followup 未被持久接收")
        if not any(
            isinstance(event, dict)
            and event.get("event_type") == "session_input_consumed"
            and _as_dict(event.get("payload")).get("input_type") == "followup"
            for event in trajectory
        ):
            failures.append("followup 没有进入可重放轨迹")

    return failures


def _setup_history(
    case_id: str,
    *,
    backend_url: str,
    question_time: str,
    timezone: str,
    timeout: float,
    interval: float,
) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    setup_question = _REFERENCE_SETUP.get(case_id)
    if not setup_question:
        return [], None
    setup_case = MatrixCase(f"{case_id}-SETUP", setup_question, "context setup", [])
    task_id = _post_chat_task(
        backend_url,
        setup_case,
        question_time=question_time,
        timezone=timezone,
        thinking_mode=False,
    )
    task = _poll_task(backend_url, task_id, timeout=timeout, interval=interval)
    answer = _answer(task)
    if task.get("status") != "done" or not answer:
        raise RuntimeError(f"reference setup failed: {task_id} status={task.get('status')}")
    return [
        {"role": "user", "content": setup_question},
        {"role": "assistant", "content": answer},
    ], {"task_id": task_id, "question": setup_question, "answer": answer}


def run_case(
    case: dict[str, Any],
    *,
    backend_url: str,
    question_time: str,
    timezone: str,
    timeout: float,
    interval: float,
) -> dict[str, Any]:
    history, setup = _setup_history(
        str(case["id"]),
        backend_url=backend_url,
        question_time=question_time,
        timezone=timezone,
        timeout=timeout,
        interval=interval,
    )
    matrix_case = MatrixCase(
        str(case["id"]), str(case["question"]), str(case.get("expected") or ""), []
    )
    task_id = _post_chat_task(
        backend_url,
        matrix_case,
        question_time=question_time,
        timezone=timezone,
        thinking_mode=False,
        conversation_history=history or None,
    )
    inbox: dict[str, Any] | None = None
    steering = _STEERING.get(str(case["id"]))
    if steering:
        action, content = steering
        inbox = _http_json(
            "POST",
            _api_url(backend_url, f"/api/ai/tasks/{task_id}/inbox"),
            {"action": action, "content": content},
        )
    task = _poll_task(backend_url, task_id, timeout=timeout, interval=interval)
    events = _task_events(backend_url, task_id)

    common_issues: list[str] = []
    if task.get("status") == "done":
        common = _grade_case(matrix_case, task, events)
        if common["grade"] == "Fail":
            common_issues.extend(str(item) for item in common["issues"])
    semantic_issues = _semantic_assertions(case, task, events, inbox)
    issues = [*common_issues, *semantic_issues]
    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "expected": case["expected"],
        "assertions": case["assertions"],
        "task_id": task_id,
        "status": task.get("status"),
        "grade": "Fail" if issues else "Pass",
        "issues": issues,
        "answer": _answer(task),
        "tool_names": [item["tool_name"] for item in _tool_observations(events)],
        "runtime_metrics": _as_dict(task.get("result")).get("runtime_metrics"),
        "inbox": inbox,
        "setup": setup,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--question-time", default="2026-09-22T18:47:00+08:00")
    parser.add_argument("--timezone", default="Asia/Shanghai")
    parser.add_argument("--poll-timeout", type=float, default=180.0)
    parser.add_argument("--poll-interval", type=float, default=0.5)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    if args.case_id:
        wanted = set(args.case_id)
        cases = [case for case in cases if case["id"] in wanted]
    if args.max_cases is not None:
        cases = cases[: max(0, args.max_cases)]

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        print(f"[{index}/{len(cases)}] {case['id']} {case['question']}", flush=True)
        try:
            result = run_case(
                case,
                backend_url=args.backend_url,
                question_time=args.question_time,
                timezone=args.timezone,
                timeout=args.poll_timeout,
                interval=args.poll_interval,
            )
        except Exception as exc:
            result = {
                "id": case["id"],
                "category": case["category"],
                "question": case["question"],
                "expected": case["expected"],
                "assertions": case["assertions"],
                "task_id": None,
                "status": "error",
                "grade": "Fail",
                "issues": [str(exc)],
                "answer": "",
                "tool_names": [],
            }
        print(f"  -> {result['grade']} {result.get('task_id') or ''}", flush=True)
        results.append(result)

    counts = {
        grade: sum(item["grade"] == grade for item in results) for grade in ("Pass", "Fail")
    }
    payload = {
        "schema_version": "ai_agent_v6_freeform_acceptance_v1",
        "ok": counts["Fail"] == 0,
        "counts": counts,
        "total": len(results),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
