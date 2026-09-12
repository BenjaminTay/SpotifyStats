"""Build one exact, reusable context for a yearly Agent report task."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from backend.core.cache import singleflight
from backend.core.db import get_db
from backend.domains.ai_reports.agentic_tools import execute_report_tool
from backend.domains.ai_reports.context_snapshot import (
    load_context_snapshot,
    store_context_snapshot,
)
from backend.domains.ai_reports.narrative_brief import build_narrative_brief
from backend.domains.ai_reports.visual_brief import build_visual_brief
from backend.domains.ai_reports.visual_chart_data import build_visual_chart_data, chart_coverage
from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
from backend.domains.yearly_review.context import build_yearly_review_context
from backend.services.yearly_review_service import _prepare_artifact

AGENT_CONTEXT_BUILDER_VERSION = "yearly_agent_context_v2"
REPORT_RESEARCH_TOOLS = (
    "report_period_context",
    "yearly_overview",
    "yearly_top_entities",
    "yearly_same_period_comparison",
    "personal_billboard_year_end",
    "billboard_yearly_diagnostics",
    "genre_distribution",
    "discovery_and_returns",
    "highlight_day_detail",
)


@dataclass(frozen=True)
class YearlyAgentContextResult:
    snapshot_key: str
    source_db_revision: str
    filter_fingerprint: str
    cache_hit: bool
    built: bool
    build_elapsed_ms: int
    payload: dict[str, Any]

    @property
    def context(self) -> dict[str, Any]:
        value = self.payload.get("context")
        return dict(value) if isinstance(value, dict) else {}


def prepare_yearly_agent_context(request: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return exact snapshot key, source revision, filter fingerprint and request JSON."""

    year = int(request.get("year") or 0)
    if year <= 0:
        raise ValueError("yearly Agent context requires a report year")
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        filters = SimpleNamespace(
            min_ms=_int(request.get("min_ms"), 30000),
            music_only=_bool(request.get("music_only"), True),
            merge_enabled=_bool(request.get("merge_enabled"), True),
            dynamic_threshold=_bool(request.get("dynamic_threshold"), True),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            merge_level=2,
            include_compilations=bool(
                settings.get("include_compilations", SETTINGS_DEFAULTS["include_compilations"])
            ),
            bb_top_n=int(settings.get("bb_top_n", SETTINGS_DEFAULTS["bb_top_n"])),
            bb_album_top_n=int(settings.get("bb_album_top_n", SETTINGS_DEFAULTS["bb_album_top_n"])),
            bb_artist_top_n=int(
                settings.get("bb_artist_top_n", SETTINGS_DEFAULTS["bb_artist_top_n"])
            ),
            bb_week_start_dow=int(
                settings.get("bb_week_start_dow", SETTINGS_DEFAULTS["bb_week_start_dow"])
            ),
            bb_week_start_hour=int(
                settings.get("bb_week_start_hour", SETTINGS_DEFAULTS["bb_week_start_hour"])
            ),
        )
        filter_context = build_yearly_review_context(conn, filters)
    finally:
        conn.close()
    prepared = _prepare_artifact(year, filter_context)
    snapshot_key = hashlib.sha256(
        f"{prepared.cache_key}:{AGENT_CONTEXT_BUILDER_VERSION}".encode()
    ).hexdigest()
    normalized_request = {
        "year": year,
        "min_ms": filters.min_ms,
        "music_only": filters.music_only,
        "merge_enabled": filters.merge_enabled,
        "dynamic_threshold": filters.dynamic_threshold,
        "max_merge_gap_minutes": filter_context.max_merge_gap_minutes,
    }
    return (
        snapshot_key,
        prepared.db_revision,
        prepared.context.filter_fingerprint,
        json.dumps(normalized_request, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
    )


def get_or_build_yearly_agent_context(request: dict[str, Any]) -> YearlyAgentContextResult:
    """Load an exact snapshot or build the expensive yearly context exactly once."""

    snapshot_key, source_revision, fingerprint, request_json = prepare_yearly_agent_context(request)
    cached = load_context_snapshot(snapshot_key)
    if cached is not None:
        return YearlyAgentContextResult(
            snapshot_key=snapshot_key,
            source_db_revision=source_revision,
            filter_fingerprint=fingerprint,
            cache_hit=True,
            built=False,
            build_elapsed_ms=int(cached.get("build_elapsed_ms") or 0),
            payload=cached,
        )
    return _load_or_build_exact(snapshot_key, source_revision, fingerprint, request_json)


@singleflight
def _load_or_build_exact(
    snapshot_key: str,
    source_revision: str,
    fingerprint: str,
    request_json: str,
) -> YearlyAgentContextResult:
    cached = load_context_snapshot(snapshot_key)
    if cached is not None:
        return YearlyAgentContextResult(
            snapshot_key=snapshot_key,
            source_db_revision=source_revision,
            filter_fingerprint=fingerprint,
            cache_hit=True,
            built=False,
            build_elapsed_ms=int(cached.get("build_elapsed_ms") or 0),
            payload=cached,
        )

    started = time.perf_counter()
    request = json.loads(request_json)
    context, evidence = _build_base_context(request)
    narrative = build_narrative_brief(context)
    coverage = chart_coverage(context)
    visual = build_visual_brief(narrative, coverage)
    chart_specs = list(visual.get("chart_specs") or [])
    chart_data = build_visual_chart_data(context, chart_specs)
    build_elapsed_ms = max(0, round((time.perf_counter() - started) * 1000))
    payload = {
        "schema_version": AGENT_CONTEXT_BUILDER_VERSION,
        "source_db_revision": source_revision,
        "filter_fingerprint": fingerprint,
        "build_elapsed_ms": build_elapsed_ms,
        "context": context,
        "evidence": evidence,
        "narrative": narrative,
        "visual": visual,
        "chart_specs": chart_specs,
        "chart_data": chart_data,
    }
    store_context_snapshot(
        snapshot_key,
        payload,
        year=int(request["year"]),
        filter_fingerprint=fingerprint,
        source_db_revision=source_revision,
        builder_version=AGENT_CONTEXT_BUILDER_VERSION,
        build_elapsed_ms=build_elapsed_ms,
    )
    return YearlyAgentContextResult(
        snapshot_key=snapshot_key,
        source_db_revision=source_revision,
        filter_fingerprint=fingerprint,
        cache_hit=False,
        built=True,
        build_elapsed_ms=build_elapsed_ms,
        payload=payload,
    )


def _build_base_context(request: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    from backend.services.ai_insights_service import _gather_yearly_data

    conn = get_db(readonly=True)
    try:
        raw_context = _gather_yearly_data(
            conn,
            min_ms=int(request["min_ms"]),
            music_only=bool(request["music_only"]),
            merge_enabled=bool(request["merge_enabled"]),
            year=int(request["year"]),
            dynamic_threshold=bool(request["dynamic_threshold"]),
            max_merge_gap_minutes=request.get("max_merge_gap_minutes"),
            allow_expensive_year_end=False,
        )
    finally:
        conn.close()
    raw_context = {
        **raw_context,
        "request_filters": dict(request),
    }
    context: dict[str, Any] = {"year": request["year"]}
    evidence: list[dict[str, Any]] = []
    for tool_name in REPORT_RESEARCH_TOOLS:
        result = execute_report_tool(tool_name, request, context=raw_context)
        data = result.get("data") if isinstance(result, dict) else {}
        if isinstance(data, dict):
            context.update(_context_fragment(tool_name, data))
        evidence.append(
            {
                "tool_name": tool_name,
                "params": dict(request),
                "result_summary": str(result.get("summary") or ""),
                "supports": [tool_name],
                "questions_raised": [],
            }
        )
    context["request_filters"] = dict(request)
    return context, evidence


def _context_fragment(tool_name: str, data: dict[str, Any]) -> dict[str, Any]:
    if tool_name == "report_period_context":
        return {"reporting_period": data}
    if tool_name == "yearly_overview":
        return data
    if tool_name == "yearly_top_entities":
        return {
            "top_artists": data.get("top_artists") or [],
            "top_tracks": data.get("top_tracks") or [],
            "top_albums": data.get("top_albums") or [],
        }
    return {tool_name: data}


def _bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
