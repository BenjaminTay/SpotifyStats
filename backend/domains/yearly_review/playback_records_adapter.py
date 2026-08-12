"""Normalize playback and Billboard record catalogs for Yearly Review V2."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any, Literal
from urllib.parse import quote

import numpy as np
import pandas as pd

from backend.models.yearly_review import (
    YearlyEntityRef,
    YearlyHighlightCandidate,
    YearlyMetric,
    YearlyReviewFilterContext,
)
from backend.services.analysis_records_service import _get_analysis_records_uncached

CandidateSource = Literal["playback_records", "billboard_records"]
PLAYBACK_FAMILY_TABS = {
    "obsession": "highlights",
    "behavior": "highlights",
    "reigns": "reigns",
    "longevity": "longevity",
    "time_patterns": "timePatterns",
    "discovery": "discovery",
}
BILLBOARD_FAMILY_TABS = {
    "championship": "championship",
    "longevity": "longevity",
    "endurance": "endurance",
    "movement": "breakthrough",
    "hall_of_fame": "halloffame",
    "market": "market",
    "quirky": "curiosities",
    "self_replacement_blocker": "selfReplacement",
}

_METRIC_FIELDS: tuple[tuple[str, str, str | None], ...] = (
    ("plays", "播放次数", "次"),
    ("play_count", "播放次数", "次"),
    ("hours", "收听时长", "小时"),
    ("max_plays", "最高播放次数", "次"),
    ("total_plays", "总播放次数", "次"),
    ("weeks_at_no1", "冠军周数", "周"),
    ("weeks_on_chart", "在榜周数", "周"),
    ("streak_days", "连续天数", "天"),
    ("active_months", "活跃月份", "个月"),
    ("span_days", "跨度", "天"),
    ("peak_position", "最高排名", "名"),
)


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp, datetime, date)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _iter_record_rows(value: Any, path: tuple[str, ...] = ()):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _iter_record_rows(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, row in enumerate(value):
            if isinstance(row, Mapping):
                yield path, index, dict(row)


def _entity_refs(
    row: Mapping[str, Any], fact_type: str | None = None, record_key: str = ""
) -> list[YearlyEntityRef]:
    track_id = row.get("track_id") or row.get("debut_track_id")
    track_name = row.get("track_name") or row.get("歌曲") or row.get("debut_track")
    album_name = row.get("album_name") or row.get("专辑") or row.get("debut_album")
    artist_name = row.get("artist_name") or row.get("艺人")
    cover_url = row.get("cover_url")

    metric_subject = str(row.get("name") or "")
    if "discovery.discovery_day" in record_key:
        return []
    if "behavior.playback_milestones" in record_key and track_id is None:
        return []
    if fact_type == "track" and track_id is None:
        return []
    if fact_type == "album" and not album_name and metric_subject:
        album_name = metric_subject
    if fact_type == "artist" and not artist_name and metric_subject:
        artist_name = metric_subject

    if track_id is not None and track_name:
        track_id = int(track_id)
        return [
            YearlyEntityRef(
                entity_type="track",
                entity_id=track_id,
                name=str(track_name),
                artist_name=str(artist_name) if artist_name else None,
                cover_url=str(cover_url) if cover_url else None,
                deep_link=f"/music/tracks/{track_id}",
            )
        ]
    if album_name:
        album = quote(str(album_name), safe="")
        artist = quote(str(artist_name or ""), safe="")
        return [
            YearlyEntityRef(
                entity_type="album",
                entity_id=row.get("album_project_id") or row.get("album_id"),
                name=str(album_name),
                artist_name=str(artist_name) if artist_name else None,
                cover_url=str(cover_url) if cover_url else None,
                deep_link=f"/music/albums/{album}?artist={artist}",
            )
        ]
    if artist_name:
        return [
            YearlyEntityRef(
                entity_type="artist",
                entity_id=row.get("artist_id"),
                name=str(artist_name),
                cover_url=str(cover_url) if cover_url else None,
                deep_link=f"/music/artists/{quote(str(artist_name), safe='')}",
            )
        ]
    return []


def _primary_metric(row: Mapping[str, Any]) -> YearlyMetric | None:
    generic_value = row.get("value")
    if isinstance(generic_value, (int, float, np.integer, np.floating)) and not isinstance(
        generic_value, bool
    ):
        return YearlyMetric(
            key="value",
            label=str(row.get("name") or "记录值"),
            value=_json_value(generic_value),
            unit=str(row["unit"]) if row.get("unit") else None,
        )
    for key, label, unit in _METRIC_FIELDS:
        value = row.get(key)
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            return YearlyMetric(key=key, label=label, value=_json_value(value), unit=unit)
    return None


def _candidate_id(
    source: CandidateSource,
    record_key: str,
    index: int,
    row: Mapping[str, Any],
) -> str:
    identity = {
        key: _json_value(row.get(key))
        for key in (
            "track_id",
            "track_name",
            "album_project_id",
            "album_name",
            "artist_name",
            "date",
            "month",
            "year",
            "billboard_week",
        )
        if row.get(key) is not None
    }
    payload = json.dumps(
        [source, record_key, index, identity],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:20]


def normalize_record_catalog(
    records: Mapping[str, Any] | None,
    *,
    source: CandidateSource,
    fallback_base: str = "/analysis/records",
) -> tuple[list[YearlyHighlightCandidate], dict[str, int]]:
    """Flatten one nested catalog without choosing the final featured records."""
    candidates: list[YearlyHighlightCandidate] = []
    family_counts: Counter[str] = Counter()
    if not records:
        return candidates, {}

    for path, index, raw_row in _iter_record_rows(records):
        if not path:
            continue
        family = path[0]
        record_key = ".".join(path)
        row = _json_value(raw_row)
        refs = _entity_refs(row, path[-1], record_key)
        metric = _primary_metric(row)
        structurally_eligible = bool(row)
        reasons = ["source_service_qualified"] if structurally_eligible else ["empty_record_row"]
        if refs:
            deep_link = refs[0].deep_link
        elif source == "playback_records":
            deep_link = f"{fallback_base}?family={PLAYBACK_FAMILY_TABS.get(family, 'highlights')}"
        else:
            deep_link = f"{fallback_base}?family={BILLBOARD_FAMILY_TABS.get(family, 'curiosities')}"
        candidates.append(
            YearlyHighlightCandidate(
                candidate_id=_candidate_id(source, record_key, index, row),
                source=source,
                source_family=family,
                record_key=record_key,
                category=family,
                fact_type=path[-1],
                entity_refs=refs,
                primary_metric=metric,
                raw_values=row,
                eligible=structurally_eligible,
                eligibility_reasons=reasons,
                evidence_grade="A",
                source_refs=[f"{source}:{record_key}:{index}"],
                deep_link=deep_link,
            )
        )
        family_counts[family] += 1
    return candidates, dict(sorted(family_counts.items()))


def build_playback_record_candidates(
    conn: sqlite3.Connection,
    year: int,
    context: YearlyReviewFilterContext,
    *,
    payload: Mapping[str, Any] | None = None,
    event_frame: pd.DataFrame | None = None,
    entity_frames: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """Compute the annual custom-range catalog and normalize it for M3."""
    if payload is None:
        payload = _get_analysis_records_uncached(
            conn=conn,
            min_ms=context.min_ms,
            music_only=context.music_only,
            merge_enabled=context.merge_enabled,
            period="custom",
            start_date=f"{year}-01-01",
            end_date=f"{year}-12-31",
            merge_level=context.merge_level,
            dynamic_threshold=context.dynamic_threshold,
            max_merge_gap_minutes=context.max_merge_gap_minutes,
            include_compilations=context.include_compilations,
            preloaded_event_frame=event_frame,
            preloaded_entity_frames=entity_frames,
        )
    candidates, family_counts = normalize_record_catalog(
        payload.get("records", {}),
        source="playback_records",
    )
    return {
        "year": year,
        "period": dict(payload.get("period", {})),
        "meta": dict(payload.get("meta", {})),
        "catalog_counts": {
            "total": len(candidates),
            "eligible": sum(candidate.eligible for candidate in candidates),
            **family_counts,
        },
        "candidates": candidates,
    }
