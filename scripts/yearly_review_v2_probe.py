#!/usr/bin/env python3
"""Read-only real-data contract and performance probe for Yearly Review V2."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.db import get_db  # noqa: E402
from backend.domains.settings.repository import SettingsRepository  # noqa: E402
from backend.domains.yearly_review.context import build_yearly_review_context  # noqa: E402
from backend.domains.yearly_review.versions import YEARLY_REVIEW_CONTENT_VERSION  # noqa: E402
from backend.services.yearly_review_service import (  # noqa: E402
    _artifact,
    _build_cached_artifact,
    bypass_yearly_review_persistent_cache,
    get_yearly_review,
    get_yearly_review_available_years,
    get_yearly_review_records,
)

PROBE_VERSION = "yearly_review_v2_probe_v5"

CONSUMER_BANNED_COPY = (
    "统计口径",
    "可比基线",
    "有效阈值",
    "证据门槛",
    "展示阈值",
    "服务端分页",
    "多实体结构性变化",
    "事实差值",
    "口径索引",
    "有效播放",
    "有效时长",
)


def _semantic_fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def parse_years(value: str) -> list[int]:
    try:
        years = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    except ValueError as exc:
        raise argparse.ArgumentTypeError("years must be comma-separated integers") from exc
    if not years or any(year < 2000 or year > 2100 for year in years):
        raise argparse.ArgumentTypeError("years must be between 2000 and 2100")
    return years


def _context():
    conn = get_db(readonly=True)
    try:
        settings = SettingsRepository(conn).load_all()
        filters = SimpleNamespace(
            min_ms=int(settings["min_ms"]),
            music_only=bool(settings["music_only"]),
            merge_enabled=bool(settings["merge_enabled"]),
            dynamic_threshold=True,
            max_merge_gap_minutes=None,
            merge_level=2,
            include_compilations=bool(settings["include_compilations"]),
            bb_top_n=int(settings["bb_top_n"]),
            bb_album_top_n=int(settings["bb_album_top_n"]),
            bb_artist_top_n=int(settings["bb_artist_top_n"]),
            bb_week_start_dow=int(settings["bb_week_start_dow"]),
            bb_week_start_hour=int(settings["bb_week_start_hour"]),
        )
        return build_yearly_review_context(conn, filters)
    finally:
        conn.close()


def _taste_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    taste = payload["coverage"]["taste"]
    distributions = payload["taste_migration"]["distributions"]
    for axis in ("style", "scene", "language", "release_era"):
        rows = distributions.get(axis, [])
        total_share = sum(float(row.get("share_pct", 0)) for row in rows)
        if rows and not 99.0 <= total_share <= 100.5:
            issues.append(f"taste_share_not_conserved:{axis}:{total_share:.2f}")
        if taste[axis]["unknown_hours"] > 0 and rows:
            has_unknown = any(str(row.get("key")) == "unknown" for row in rows)
            if not has_unknown:
                issues.append(f"unknown_bucket_missing:{axis}")
    return issues


def _identity_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    appendix = payload["appendix"]
    for key, rows in appendix["play_charts"].items():
        identities = [row.get("identity_key") for row in rows if row.get("identity_key")]
        if len(identities) != len(set(identities)):
            issues.append(f"duplicate_play_identity:{key}")
    for entity, rows in appendix["billboard_charts"].items():
        if entity == "album" and any(not row.get("identity_key") for row in rows):
            issues.append("billboard_album_identity_missing")
    return issues


def _editorial_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    featured = payload["records"]["featured"]
    banned = ("年度事实", "记录到 championship", "记录到 endurance", " / ")
    for item in featured:
        text = f"{item['title']} {item['statement']}"
        if any(token in text for token in banned):
            issues.append(f"featured_internal_copy:{item['record_id']}")
        has_date = bool(re.search(r"\b20\d{2}-\d{2}-\d{2}\b", item["statement"]))
        if not item["metrics"] and not has_date:
            issues.append(f"featured_missing_evidence:{item['record_id']}")
    for point in payload["season"]["turning_points"]:
        if any(token in point["statement"] for token in banned):
            issues.append(f"timeline_internal_copy:{point['point_id']}")
    opening = {item["statement"] for item in payload["headlines"]}
    closing = {item["statement"] for item in payload["epilogue"]["conclusions"]}
    if opening & closing:
        issues.append("epilogue_duplicates_opening")
    stage_status = payload["season"]["stage_status"]
    stages = payload["season"]["stages"]
    if stage_status == "available" and not stages:
        issues.append("stage_status_available_without_stages")
    if stage_status != "available" and stages:
        issues.append("stages_present_without_available_status")
    timeline_statements = {item["statement"] for item in payload["season"]["turning_points"]}
    record_statements = {item["statement"] for item in featured}
    if timeline_statements & record_statements:
        issues.append("records_duplicate_timeline")
    return issues


def _consumer_issues(payload: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    strings: list[tuple[str, str]] = []

    def add(path: str, value: Any) -> None:
        if isinstance(value, str):
            strings.append((path, value))

    for metric in (payload.get("passport") or {}).get("metrics", []):
        add(f"passport:{metric.get('key')}", metric.get("label"))
    for section in ("headlines", "relationships"):
        for index, item in enumerate(payload.get(section, [])):
            add(f"{section}:{index}:title", item.get("title"))
            add(f"{section}:{index}:statement", item.get("statement"))
    for item in payload["honors"].get("annual_honors", []):
        add(f"honors:{item.get('honor_id')}", item.get("title"))
    for item in payload["season"].get("turning_points", []):
        add(f"season:{item.get('point_id')}:title", item.get("title"))
        add(f"season:{item.get('point_id')}:statement", item.get("statement"))
    for item in payload["listening_life"].get("observations", []):
        add(f"listening_life:{item.get('headline_id')}:title", item.get("title"))
        add(f"listening_life:{item.get('headline_id')}:statement", item.get("statement"))
    for item in payload["records"].get("featured", []):
        add(f"records:{item.get('record_id')}:title", item.get("title"))
        add(f"records:{item.get('record_id')}:statement", item.get("statement"))
    for section in ("taste_migration", "epilogue"):
        key = "observations" if section == "taste_migration" else "conclusions"
        for index, item in enumerate(payload[section].get(key, [])):
            add(f"{section}:{index}:title", item.get("title"))
            add(f"{section}:{index}:statement", item.get("statement"))

    for path, value in strings:
        for token in CONSUMER_BANNED_COPY:
            if token in value:
                issues.append(f"consumer_copy:{path}:{token}")
        if payload["status"] == "year_to_date" and "全年" in value:
            issues.append(f"ytd_full_year_copy:{path}")
        if re.search(r"\d+(?:\.\d+)?pp\b", value, re.IGNORECASE):
            issues.append(f"consumer_pp_copy:{path}")

    refs: list[dict[str, Any]] = []

    def collect_refs(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("entity_type") in {"track", "album", "artist"} and value.get("name"):
                refs.append(value)
            for child in value.values():
                collect_refs(child)
        elif isinstance(value, list):
            for child in value:
                collect_refs(child)

    for key in (
        "headlines",
        "honors",
        "season",
        "relationships",
        "listening_life",
        "records",
        "taste_migration",
        "epilogue",
    ):
        collect_refs(payload[key])
    if any(not ref.get("deep_link") for ref in refs):
        issues.append("consumer_entity_link_missing")
    if any(not ref.get("cover_url") for ref in refs):
        issues.append("consumer_entity_cover_missing")
    if len(payload["relationships"]) > 8:
        issues.append(f"relationship_count:{len(payload['relationships'])}")
    if payload["season"].get("stage_note"):
        issues.append("consumer_stage_note_visible")
    return issues


def probe_year(
    year: int,
    context,
    *,
    max_json_kib: int,
    max_cold_ms: float,
    max_hot_ms: float,
) -> dict[str, Any]:
    start = time.perf_counter()
    report = get_yearly_review(year, context)
    cold_ms = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    hot_report = get_yearly_review(year, context)
    hot_ms = (time.perf_counter() - start) * 1000
    records = get_yearly_review_records(year, context, page=1, page_size=50)
    full_artifact = _artifact(year, context)
    payload = report.model_dump(mode="json")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    issues: list[str] = []
    if hot_report.filter_context.filter_fingerprint != context.filter_fingerprint:
        issues.append("hot_filter_fingerprint_mismatch")
    if records.filter_fingerprint != context.filter_fingerprint:
        issues.append("records_filter_fingerprint_mismatch")
    if report.methodology.content_version != YEARLY_REVIEW_CONTENT_VERSION:
        issues.append("report_content_version_mismatch")
    if records.content_version != YEARLY_REVIEW_CONTENT_VERSION:
        issues.append("records_content_version_mismatch")
    if len(report.season.months) != 12:
        issues.append(f"month_count:{len(report.season.months)}")
    if report.status != "empty" and not 6 <= len(report.season.turning_points) <= 10:
        issues.append(f"turning_point_count:{len(report.season.turning_points)}")
    featured = len(report.records.featured)
    if records.total >= 6 and not 6 <= featured <= 8:
        issues.append(f"featured_record_count:{featured}")
    if len(encoded) > max_json_kib * 1024:
        issues.append(f"json_budget:{len(encoded)}")
    if cold_ms > max_cold_ms:
        issues.append(f"cold_latency_budget:{cold_ms:.2f}")
    if hot_ms > max_hot_ms:
        issues.append(f"hot_latency_budget:{hot_ms:.2f}")
    issues.extend(_taste_issues(payload))
    issues.extend(_identity_issues(payload))
    issues.extend(_editorial_issues(payload))
    issues.extend(_consumer_issues(payload))
    return {
        "year": year,
        "status": report.status,
        "filter_fingerprint": context.filter_fingerprint,
        "content_version": report.methodology.content_version,
        "cold_ms": round(cold_ms, 2),
        "hot_ms": round(hot_ms, 2),
        "json_bytes": len(encoded),
        "semantic_fingerprint": _semantic_fingerprint(payload),
        "record_catalog_fingerprint": _semantic_fingerprint(full_artifact["record_catalog"]),
        "headlines": len(report.headlines),
        "months": len(report.season.months),
        "turning_points": len(report.season.turning_points),
        "relationships": len(report.relationships),
        "featured_records": featured,
        "record_catalog_total": records.total,
        "record_page_items": len(records.items),
        "taste_observations": len(report.taste_migration.observations),
        "limitations": report.methodology.limitations,
        "issues": issues,
    }


def run_probe(
    years: list[int],
    *,
    max_json_kib: int,
    max_cold_ms: float,
    max_hot_ms: float,
    cache_mode: str = "recompute",
) -> dict[str, Any]:
    context = _context()
    available = get_yearly_review_available_years()
    missing = [year for year in years if year not in available.years]
    _build_cached_artifact.cache_clear()
    cache_scope = (
        bypass_yearly_review_persistent_cache() if cache_mode == "recompute" else nullcontext()
    )
    with cache_scope:
        results = [
            probe_year(
                year,
                context,
                max_json_kib=max_json_kib,
                max_cold_ms=max_cold_ms,
                max_hot_ms=max_hot_ms,
            )
            for year in years
        ]
    issues = [f"available_year_missing:{year}" for year in missing]
    issues.extend(f"{result['year']}:{issue}" for result in results for issue in result["issues"])
    return {
        "probe_version": PROBE_VERSION,
        "content_version": YEARLY_REVIEW_CONTENT_VERSION,
        "read_only": True,
        "read_only_scope": "source_database",
        "persistent_cache_write": cache_mode == "recompute",
        "cache_mode": cache_mode,
        "requested_years": years,
        "available_years": available.years,
        "latest_year": available.latest_year,
        "filter_fingerprint": context.filter_fingerprint,
        "budgets": {
            "max_json_kib": max_json_kib,
            "max_cold_ms": max_cold_ms,
            "max_hot_ms": max_hot_ms,
        },
        "cache_info": _build_cached_artifact.cache_info()._asdict(),
        "years": results,
        "issues": issues,
        "passed": not issues,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=parse_years, default=parse_years("2023,2024,2025,2026"))
    parser.add_argument("--max-json-kib", type=int, default=512)
    parser.add_argument("--max-cold-ms", type=float, default=30_000.0)
    parser.add_argument("--max-hot-ms", type=float, default=250.0)
    parser.add_argument(
        "--cache-mode",
        choices=("recompute", "persistent"),
        default="recompute",
        help="recompute measures true calculation cost; persistent measures restart-cache hits",
    )
    parser.add_argument("--json-output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_probe(
        args.years,
        max_json_kib=args.max_json_kib,
        max_cold_ms=args.max_cold_ms,
        max_hot_ms=args.max_hot_ms,
        cache_mode=args.cache_mode,
    )
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
