from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from backend.services import ai_insights_service, ai_task_service

pytestmark = pytest.mark.unit


@pytest.fixture
def ai_report_task_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "ai_report_tasks.db"
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE ai_task_runs (
                task_id TEXT PRIMARY KEY,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                progress_pct REAL NOT NULL DEFAULT 0,
                message TEXT NOT NULL DEFAULT '',
                request_json TEXT,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE ai_task_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                payload_json TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE ai_tool_calls (
                tool_call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                status TEXT NOT NULL,
                params_summary TEXT NOT NULL DEFAULT '',
                result_summary TEXT NOT NULL DEFAULT '',
                source_range TEXT NOT NULL DEFAULT '',
                error TEXT,
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );
            CREATE TABLE wikipedia_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT,
                fetched_at TEXT
            );
            """
        )
    finally:
        conn.close()

    def get_test_db(readonly: bool = False) -> sqlite3.Connection:
        del readonly
        test_conn = sqlite3.connect(db_path)
        test_conn.row_factory = sqlite3.Row
        return test_conn

    monkeypatch.setattr(ai_task_service, "get_db", get_test_db)
    return db_path


def _base_report_request(**overrides: Any) -> dict[str, Any]:
    request = {
        "report_type": "weekly",
        "action": "cache_only",
        "force": False,
        "week_start": "2026-06-17",
        "week_end": "2026-06-23",
        "month": None,
        "year": 2026,
        "min_ms": 30000,
        "music_only": True,
        "merge_enabled": True,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": None,
    }
    request.update(overrides)
    return request


def _insert_cache(
    db_path: Path,
    *,
    report_type: str,
    report: str,
    fetched_at: str = "2099-06-28T00:00:00",
    **request_overrides: Any,
) -> dict[str, Any]:
    request = _base_report_request(report_type=report_type, **request_overrides)
    key = ai_insights_service._report_cache_key(
        report_type,
        min_ms=request["min_ms"],
        music_only=request["music_only"],
        merge_enabled=request["merge_enabled"],
        dynamic_threshold=request["dynamic_threshold"],
        max_merge_gap_minutes=request["max_merge_gap_minutes"],
        week_start=request.get("week_start"),
        week_end=request.get("week_end"),
        month=request.get("month"),
        year=request.get("year"),
    )
    assert key is not None

    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO wikipedia_cache (cache_key, data, fetched_at) VALUES (?, ?, ?)",
            (key, report, fetched_at),
        )
        conn.commit()
    finally:
        conn.close()
    return request


def test_peek_report_cache_reads_weekly_cache_without_llm(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    request = _insert_cache(
        ai_report_task_db,
        report_type="weekly",
        report="缓存周报",
        min_ms=45000,
        music_only=False,
        merge_enabled=False,
        dynamic_threshold=False,
        max_merge_gap_minutes=45,
    )
    monkeypatch.setattr(
        ai_insights_service,
        "_get_llm",
        lambda *args, **kwargs: pytest.fail("peek_report_cache must not call LLM"),
    )
    monkeypatch.setattr(
        ai_insights_service,
        "_gather_weekly_data",
        lambda *args, **kwargs: {
            "top_artists": [{"name": "缓存艺人"}],
            "top_tracks": [{"name": "缓存歌曲"}],
        },
    )
    conn = sqlite3.connect(ai_report_task_db)
    conn.row_factory = sqlite3.Row
    try:
        result = ai_insights_service.peek_report_cache(
            conn,
            "weekly",
            min_ms=request["min_ms"],
            music_only=request["music_only"],
            merge_enabled=request["merge_enabled"],
            dynamic_threshold=request["dynamic_threshold"],
            max_merge_gap_minutes=request["max_merge_gap_minutes"],
            week_start=request["week_start"],
            week_end=request["week_end"],
        )
    finally:
        conn.close()

    assert result == {
        "cached": True,
        "report": "缓存周报",
        "cached_at": "2099-06-28T00:00:00",
        "entities": {"artists": ["缓存艺人"], "tracks": ["缓存歌曲"]},
    }


@pytest.mark.parametrize(
    ("report_type", "request_overrides", "expected_report"),
    [
        ("weekly", {"week_start": "2026-06-17", "week_end": "2026-06-23"}, "周报"),
        ("monthly", {"month": "2026-06", "year": 2026}, "月报"),
        ("yearly", {"year": 2026}, "年报"),
    ],
)
def test_peek_report_cache_uses_generate_cache_keys_for_all_report_types(
    ai_report_task_db: Path,
    report_type: str,
    request_overrides: dict[str, Any],
    expected_report: str,
):
    request = _insert_cache(
        ai_report_task_db,
        report_type=report_type,
        report=expected_report,
        **request_overrides,
    )
    conn = sqlite3.connect(ai_report_task_db)
    conn.row_factory = sqlite3.Row
    try:
        result = ai_insights_service.peek_report_cache(
            conn,
            report_type,
            min_ms=request["min_ms"],
            music_only=request["music_only"],
            merge_enabled=request["merge_enabled"],
            dynamic_threshold=request["dynamic_threshold"],
            max_merge_gap_minutes=request["max_merge_gap_minutes"],
            week_start=request.get("week_start"),
            week_end=request.get("week_end"),
            month=request.get("month"),
            year=request.get("year"),
        )
    finally:
        conn.close()

    assert result["cached"] is True
    assert result["report"] == expected_report


def test_cache_only_weekly_report_does_not_call_llm(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    called = {"llm": False}

    monkeypatch.setattr(
        ai_task_service,
        "peek_report_cache",
        lambda request: {
            "cached": False,
            "report": None,
            "cached_at": None,
            "entities": None,
            "needs_generation": True,
        },
        raising=False,
    )
    monkeypatch.setattr(
        ai_task_service,
        "run_report_generation_task",
        lambda task_id, request: called.__setitem__("llm", True),
        raising=False,
    )

    result = ai_task_service.start_report_task(_base_report_request())

    assert result["status"] == "done"
    assert result["result"]["needs_generation"] is True
    assert called["llm"] is False


def test_cache_only_visual_yearly_report_ignores_legacy_yearly_cache(
    ai_report_task_db: Path,
):
    legacy_request = _insert_cache(
        ai_report_task_db,
        report_type="yearly",
        report="旧版 Markdown 年报",
        year=2025,
    )

    result = ai_task_service.start_report_task(
        {
            **legacy_request,
            "action": "cache_only",
            "report_mode": "visual_yearly_artifact",
        }
    )

    assert result["status"] == "done"
    assert result["result"]["cached"] is False
    assert result["result"]["report"] is None
    assert result["result"]["needs_generation"] is True


def test_visual_yearly_report_generation_writes_artifact_cache(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    request = _base_report_request(
        action="generate",
        report_type="yearly",
        year=2025,
        report_mode="visual_yearly_artifact",
        force=True,
    )
    task = ai_task_service.create_task(
        task_type="ai_report_yearly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )

    def fake_generate(request_payload, *, emit_event=None):
        del request_payload
        if emit_event:
            emit_event("stage_started", "正在生成图文年报", {"stage": "composing_artifact"})
        return {
            "success": True,
            "report": "图文年报正文",
            "artifact": {
                "report_mode": "visual_yearly_artifact",
                "contract_version": "visual_yearly_v1",
                "title": "你的 2025 音乐年记",
                "sections": [],
                "insight_cards": [],
                "chart_specs": [],
                "chart_data": {},
                "metadata": {"report_mode": "visual_yearly_artifact"},
            },
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["Taylor Swift"], "tracks": []},
            "metadata": {"report_mode": "visual_yearly_artifact"},
            "evidence_ledger": [],
            "error": None,
        }

    monkeypatch.setattr(
        "backend.domains.ai_reports.visual_yearly_artifact_service.generate_visual_yearly_artifact",
        fake_generate,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)
    cached = ai_task_service.start_report_task({**request, "action": "cache_only", "force": False})
    stored = ai_task_service.get_task(task["task_id"])

    assert stored is not None
    assert stored["result"]["cached_at"] is not None
    assert cached["result"]["cached"] is True
    assert cached["result"]["cached_at"] == stored["result"]["cached_at"]
    assert cached["result"]["report"] == "图文年报正文"
    assert cached["result"]["artifact"]["contract_version"] == "visual_yearly_v1"
    assert cached["result"]["needs_generation"] is False


def test_generate_weekly_report_starts_background_task(monkeypatch: pytest.MonkeyPatch):
    observed = {}

    def fake_create_task(*, task_type, stage, message, request, handler):
        observed.update(
            {
                "task_type": task_type,
                "stage": stage,
                "message": message,
                "request": request,
                "handler": handler,
            }
        )
        return {
            "task_id": "task-123",
            "status": "queued",
            "stage": stage,
            "progress_pct": 0.0,
            "message": message,
            "result": None,
        }

    monkeypatch.setattr(ai_task_service, "create_task", fake_create_task)

    result = ai_task_service.start_report_task(_base_report_request(action="generate", force=True))

    assert result["task_id"] == "task-123"
    assert observed["task_type"] == "ai_report_weekly"
    assert observed["stage"] == "checking_cache"
    assert observed["request"]["force"] is True
    assert observed["handler"] == ai_task_service.run_report_generation_task


def test_run_report_generation_task_success_writes_done_result(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=_base_report_request(action="generate"),
    )

    def fake_generate_weekly_digest(*args, **kwargs):
        kwargs["progress_callback"]("calling_llm", 0.7, "正在调用 LLM 生成报告")
        return {
            "success": True,
            "report": "生成后的周报",
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["A"], "tracks": ["T"]},
            "error": None,
        }

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_weekly_digest",
        fake_generate_weekly_digest,
    )

    ai_task_service.run_report_generation_task(
        task["task_id"], _base_report_request(action="generate")
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "done"
    assert stored["stage"] == "done"
    assert stored["result"]["report"] == "生成后的周报"
    assert stored["result"]["entities"] == {"artists": ["A"], "tracks": ["T"]}
    assert events is not None
    stages = [event["stage"] for event in events[0]]
    assert "checking_cache" in stages
    assert "gathering_local_data" in stages
    assert "calling_llm" in stages
    assert "saving_cache" in stages
    assert stages[-1] == "done"


def test_run_report_generation_task_writes_report_cache_after_generation(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    request = _base_report_request(action="generate", force=True)
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )
    observed: dict[str, Any] = {}

    def fake_generate_weekly_digest(*args, **kwargs):
        del args
        observed["cache_result"] = kwargs["cache_result"]
        kwargs["progress_callback"]("calling_llm", 0.7, "正在调用 LLM 生成报告")
        return {
            "success": True,
            "report": "应写入缓存的周报",
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["A"], "tracks": ["T"]},
            "error": None,
        }

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_weekly_digest",
        fake_generate_weekly_digest,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)

    conn = sqlite3.connect(ai_report_task_db)
    try:
        row = conn.execute(
            "SELECT data, fetched_at FROM wikipedia_cache WHERE cache_key LIKE 'ai:report:weekly:%'"
        ).fetchone()
    finally:
        conn.close()
    stored = ai_task_service.get_task(task["task_id"])

    assert observed["cache_result"] is False
    assert row is not None
    assert row[0] == "应写入缓存的周报"
    assert stored is not None
    assert stored["result"]["cached_at"] == row[1]


def test_run_report_generation_task_cancelled_after_llm_skips_cache_write(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    request = _base_report_request(action="generate", force=True)
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )
    observed: dict[str, Any] = {}

    def fake_generate_weekly_digest(*args, **kwargs):
        del args
        observed["cache_result"] = kwargs["cache_result"]
        kwargs["progress_callback"]("calling_llm", 0.7, "正在调用 LLM 生成报告")
        cancelled = ai_task_service.cancel_task(task["task_id"])
        observed["cancelled_status"] = cancelled["status"] if cancelled else None
        return {
            "success": True,
            "report": "取消后不应写入缓存",
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["A"], "tracks": ["T"]},
            "error": None,
        }

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_weekly_digest",
        fake_generate_weekly_digest,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)

    stored = ai_task_service.get_task(task["task_id"])
    conn = sqlite3.connect(ai_report_task_db)
    try:
        cache_count = conn.execute(
            "SELECT COUNT(*) FROM wikipedia_cache WHERE cache_key LIKE 'ai:report:weekly:%'"
        ).fetchone()[0]
    finally:
        conn.close()

    assert observed == {"cache_result": False, "cancelled_status": "cancelled"}
    assert stored is not None
    assert stored["status"] == "cancelled"
    assert stored["stage"] == "cancelled"
    assert cache_count == 0


def test_run_report_generation_task_no_data_does_not_claim_llm_call(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=_base_report_request(action="generate"),
    )

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_weekly_digest",
        lambda *args, **kwargs: {
            "success": False,
            "report": None,
            "cached": False,
            "error": "该时间范围暂无听歌数据",
        },
    )

    ai_task_service.run_report_generation_task(
        task["task_id"], _base_report_request(action="generate")
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "error"
    assert stored["stage"] == "error"
    assert events is not None
    stages = [event["stage"] for event in events[0]]
    assert "gathering_local_data" in stages
    assert "calling_llm" not in stages


def test_run_report_generation_task_error_result_writes_error(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    task = ai_task_service.create_task(
        task_type="ai_report_weekly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=_base_report_request(action="generate"),
    )

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_weekly_digest",
        lambda *args, **kwargs: {
            "success": False,
            "report": None,
            "cached": False,
            "error": "LLM 未配置",
        },
    )

    ai_task_service.run_report_generation_task(
        task["task_id"], _base_report_request(action="generate")
    )

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert stored is not None
    assert stored["status"] == "error"
    assert stored["stage"] == "error"
    assert stored["error"] == "LLM 未配置"
    assert stored["result"]["error"] == "LLM 未配置"
    assert events is not None
    assert events[0][-1]["event_type"] == "stage_failed"
    assert events[0][-1]["stage"] == "error"


@pytest.mark.parametrize(
    ("report_type", "expected_function", "request_overrides"),
    [
        (
            "weekly",
            "generate_weekly_digest",
            {"week_start": "2026-06-17", "week_end": "2026-06-23"},
        ),
        (
            "monthly",
            "generate_monthly_personality",
            {"month": "2026-06", "year": 2026},
        ),
    ],
)
def test_run_report_generation_task_dispatches_report_type(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
    report_type: str,
    expected_function: str,
    request_overrides: dict[str, Any],
):
    del ai_report_task_db
    called = []
    task = ai_task_service.create_task(
        task_type=f"ai_report_{report_type}",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=_base_report_request(
            action="generate", report_type=report_type, **request_overrides
        ),
    )

    def fake_generator(*args, **kwargs):
        called.append(expected_function)
        return {
            "success": True,
            "report": f"{report_type} report",
            "cached": False,
            "error": None,
        }

    for name in (
        "generate_weekly_digest",
        "generate_monthly_personality",
        "generate_yearly_story",
    ):
        monkeypatch.setattr(
            ai_task_service.ai_insights_service,
            name,
            fake_generator if name == expected_function else pytest.fail,
        )

    ai_task_service.run_report_generation_task(
        task["task_id"],
        _base_report_request(action="generate", report_type=report_type, **request_overrides),
    )

    assert called == [expected_function]


def test_basic_summary_yearly_report_mode_dispatches_legacy_generator(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    called = []
    request = _base_report_request(
        action="generate",
        report_type="yearly",
        year=2026,
        report_mode="basic_summary",
    )
    task = ai_task_service.create_task(
        task_type="ai_report_yearly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )

    def fake_generate_yearly_story(*args, **kwargs):
        called.append("generate_yearly_story")
        return {"success": True, "report": "legacy yearly", "cached": False, "error": None}

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_yearly_story",
        fake_generate_yearly_story,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)

    assert called == ["generate_yearly_story"]


def test_yearly_agent_task_emits_research_outline_and_critic_events(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    request = _base_report_request(
        action="generate",
        report_type="yearly",
        year=2026,
        report_mode="agentic_longform",
    )
    task = ai_task_service.create_task(
        task_type="ai_report_yearly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )
    captured: list[dict[str, Any]] = []

    def fake_generate(request_payload, *, emit_event=None):
        if emit_event:
            emit_event("stage_started", "查询年度播放概览", {"stage": "researching"})
            emit_event("stage_started", "生成文章大纲", {"stage": "outlining"})
            emit_event("stage_started", "审稿与修订", {"stage": "critic_review"})
        captured.append(request_payload)
        return {
            "success": True,
            "report": "## Longform\n" + "解释" * 800,
            "cached": False,
            "cached_at": None,
            "entities": {"artists": ["Taylor Swift"], "tracks": ["Opalite"]},
            "metadata": {
                "report_mode": "agentic_longform",
                "contract_version": "agentic_yearly_v14",
                "fallback_level": None,
                "tool_calls": 2,
                "data_range": "2026-01-01 to 2026-06-23",
                "is_partial_year": True,
                "critic_passed": True,
                "article_length": 1600,
            },
            "evidence_ledger": [
                {
                    "tool_name": "yearly_overview",
                    "params": {"year": 2026},
                    "result_summary": "播放 7,860 次，累计 498 小时。",
                },
                {
                    "tool_name": "personal_billboard_year_end",
                    "params": {"year": 2026},
                    "result_summary": "个人 Billboard 显示 Taylor Swift 三榜联动。",
                },
            ],
            "critic": {"ok": True, "issues": []},
            "error": None,
        }

    monkeypatch.setattr(
        "backend.services.yearly_report_agent_service.generate_agentic_yearly_report",
        fake_generate,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)

    stored = ai_task_service.get_task(task["task_id"])
    events = ai_task_service.get_task_events(task["task_id"])

    assert captured and captured[0]["report_mode"] == "agentic_longform"
    assert stored is not None
    assert stored["status"] == "done"
    assert stored["result"]["metadata"]["contract_version"] == "agentic_yearly_v14"
    assert events is not None
    messages = [event["message"] for event in events[0]]
    assert "查询年度播放概览" in messages
    assert "生成文章大纲" in messages
    assert "审稿与修订" in messages
    assert [call["tool_name"] for call in events[1]] == [
        "yearly_overview",
        "personal_billboard_year_end",
    ]


def test_visual_yearly_report_mode_dispatches_visual_artifact(monkeypatch: pytest.MonkeyPatch):
    called: dict[str, Any] = {}

    def fake_generate(request, emit_event=None):
        called["request"] = request
        if emit_event:
            emit_event(
                "stage_started",
                "正在提炼年度故事线",
                {"stage": "building_narrative_brief"},
            )
        return {
            "success": True,
            "report": "visual",
            "artifact": {},
            "cached": False,
            "metadata": {"report_mode": "visual_yearly_artifact"},
            "evidence_ledger": [],
        }

    monkeypatch.setattr(
        "backend.domains.ai_reports.visual_yearly_artifact_service.generate_visual_yearly_artifact",
        fake_generate,
    )

    result = ai_task_service._run_report_generator(
        None,
        {"report_type": "yearly", "report_mode": "visual_yearly_artifact", "year": 2025},
        progress_callback=lambda *args: None,
        should_continue=lambda: True,
    )

    assert result["metadata"]["report_mode"] == "visual_yearly_artifact"
    assert called["request"]["year"] == 2025


def test_monthly_generation_forwards_filter_parameters(
    ai_report_task_db: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    del ai_report_task_db
    observed: dict[str, Any] = {}
    request = _base_report_request(
        action="generate",
        report_type="monthly",
        month="2026-06",
        year=2026,
        force=True,
        min_ms=45000,
        music_only=False,
        merge_enabled=False,
        dynamic_threshold=False,
        max_merge_gap_minutes=45,
    )
    task = ai_task_service.create_task(
        task_type="ai_report_monthly",
        stage="checking_cache",
        message="准备生成 AI 报告",
        request=request,
    )

    def fake_generate_monthly_personality(
        conn,
        min_ms,
        music_only,
        merge_enabled,
        month,
        year,
        *,
        force,
        dynamic_threshold,
        max_merge_gap_minutes,
        cache_result,
        progress_callback,
        should_continue,
    ):
        del conn
        observed.update(
            {
                "min_ms": min_ms,
                "music_only": music_only,
                "merge_enabled": merge_enabled,
                "month": month,
                "year": year,
                "force": force,
                "dynamic_threshold": dynamic_threshold,
                "max_merge_gap_minutes": max_merge_gap_minutes,
                "cache_result": cache_result,
                "progress_callback_present": callable(progress_callback),
                "should_continue_present": callable(should_continue),
            }
        )
        return {"success": True, "report": "月报", "cached": False, "error": None}

    monkeypatch.setattr(
        ai_task_service.ai_insights_service,
        "generate_monthly_personality",
        fake_generate_monthly_personality,
    )

    ai_task_service.run_report_generation_task(task["task_id"], request)

    assert observed == {
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "month": "2026-06",
        "year": 2026,
        "force": True,
        "dynamic_threshold": False,
        "max_merge_gap_minutes": 45,
        "cache_result": False,
        "progress_callback_present": True,
        "should_continue_present": True,
    }
