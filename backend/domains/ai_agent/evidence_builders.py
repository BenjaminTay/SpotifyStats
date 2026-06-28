"""Build compact evidence cards from read-only Agent tool results."""

from __future__ import annotations

from typing import Any

from backend.domains.ai_agent.evidence import EvidenceCard, EvidenceMetric, EvidenceSource


def _source(item: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(
        tool_name=str(item.get("tool_name") or ""),
        source_range=str(item.get("source_range") or ""),
        params_summary=str(item.get("params_summary") or ""),
        result_summary=str(item.get("result_summary") or ""),
    )


def _metric(
    name: str,
    label: str,
    value: Any,
    unit: str | None = None,
) -> EvidenceMetric | None:
    if value is None:
        return None
    return EvidenceMetric(name=name, label=label, value=value, unit=unit)


def _append_metric(metrics: list[EvidenceMetric], metric: EvidenceMetric | None) -> None:
    if metric is not None:
        metrics.append(metric)


def _entity_name(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    for key in ("album_name", "artist_name", "track_name"):
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith(("album_name=", "artist_name=", "track_name=")):
            return part.split("=", 1)[1]
    return None


def _entity_type(item: dict[str, Any], data: dict[str, Any]) -> str | None:
    entity = data.get("entity")
    if isinstance(entity, str):
        return entity
    params_summary = str(item.get("params_summary") or "")
    for part in params_summary.split(", "):
        if part.startswith("entity="):
            return part.split("=", 1)[1]
    return None


def _entity_stats_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(metrics, _metric("total_plays", "播放次数", summary.get("total_plays"), "plays"))
    _append_metric(metrics, _metric("total_hours", "播放时长", summary.get("total_hours"), "hours"))
    _append_metric(
        metrics, _metric("unique_tracks", "不同歌曲数", summary.get("unique_tracks"), "tracks")
    )
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:entity_stats",
        title=f"{name or '实体'} 播放统计",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_playback",
        source=_source(item),
        metrics=metrics,
        limitations=["本地 Spotify 播放记录口径"],
    )


def _billboard_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    summary = data.get("chart_summary")
    if not isinstance(summary, dict):
        return None
    name = _entity_name(item, data)
    entity_type = _entity_type(item, data)
    metrics: list[EvidenceMetric] = []
    _append_metric(
        metrics, _metric("power_score", "个人榜单 Power Score", summary.get("power_score"))
    )
    _append_metric(metrics, _metric("power_rank", "个人榜单总排名", summary.get("power_rank")))
    _append_metric(metrics, _metric("peak_position", "最高排名", summary.get("peak_position")))
    _append_metric(
        metrics, _metric("weeks_on_chart", "在榜周数", summary.get("weeks_on_chart"), "weeks")
    )
    _append_metric(metrics, _metric("no1_weeks", "冠军周数", summary.get("no1_weeks"), "weeks"))
    return EvidenceCard(
        card_id=f"{entity_type or 'entity'}:{name or 'unknown'}:billboard",
        title=f"{name or '实体'} 个人榜单表现",
        entity_name=name,
        entity_type=entity_type,
        question_axis="personal_billboard",
        source=_source(item),
        metrics=metrics,
        limitations=["SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"],
    )


def _comparison_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    entities = data.get("entities")
    if not isinstance(entities, list):
        return None
    metrics: list[EvidenceMetric] = []
    _append_metric(
        metrics,
        _metric(
            "winner_by_cumulative_plays",
            "累计播放胜出",
            data.get("winner_by_cumulative_plays"),
        ),
    )
    _append_metric(
        metrics,
        _metric(
            "winner_by_total_hours",
            "播放时长胜出",
            data.get("winner_by_total_hours"),
        ),
    )
    _append_metric(
        metrics,
        _metric(
            "winner_by_power_score",
            "个人榜单 Power Score 胜出",
            data.get("winner_by_power_score"),
        ),
    )
    _append_metric(
        metrics,
        _metric(
            "winner_by_intensity",
            "单位在榜周强度胜出",
            data.get("winner_by_intensity"),
        ),
    )
    observations = [str(note) for note in data.get("fairness_notes", []) if isinstance(note, str)]
    for entity in entities[:4]:
        if not isinstance(entity, dict):
            continue
        name = str(entity.get("name") or entity.get("requested_name") or "实体")
        if entity.get("found") is False:
            observations.append(f"{name}: 未找到完整比较证据")
        for metric_name, label, unit in (
            ("plays", "播放次数", "plays"),
            ("hours", "播放时长", "hours"),
            ("power_score", "个人榜单 Power Score", None),
            ("power_rank", "个人榜单排名", None),
            ("weeks_on_chart", "在榜周数", "weeks"),
            ("plays_per_chart_week", "单位在榜周播放", "plays/week"),
        ):
            _append_metric(
                metrics,
                _metric(
                    f"{name}_{'total_plays' if metric_name == 'plays' else metric_name}",
                    f"{name} {label}",
                    entity.get(metric_name),
                    unit,
                ),
            )
    return EvidenceCard(
        card_id=f"{data.get('entity_type', 'entity')}:comparison",
        title="实体比较摘要",
        entity_type=str(data.get("entity_type") or "unknown"),
        question_axis="comparison",
        source=_source(item),
        metrics=metrics,
        observations=observations,
        limitations=["比较结果同时包含累计播放/时长与单位在榜周归一化强度，最终回答必须说明口径。"],
    )


def _display_row_name(entity_type: str, row: dict[str, Any]) -> str:
    if entity_type == "track":
        track = str(row.get("track_name") or row.get("name") or "未知歌曲")
        artist = str(row.get("artist_name") or "").strip()
        return f"{track} - {artist}" if artist else track
    if entity_type == "album":
        album = str(row.get("album_name") or row.get("name") or "未知专辑")
        artist = str(row.get("artist_name") or "").strip()
        return f"{album} - {artist}" if artist else album
    return str(row.get("artist_name") or row.get("name") or "未知艺人")


def _analysis_charts_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        return None
    entity_type = str(data.get("entity") or "track")
    metric = str(data.get("metric") or "plays")
    period = data.get("period") if isinstance(data.get("period"), dict) else {}
    source_range = _source(item).source_range
    period_label = str(period.get("label") or source_range or "所选范围")
    metric_label = "播放次数" if metric == "plays" else "播放时长"
    metrics: list[EvidenceMetric] = []
    _append_metric(metrics, _metric("total_ranked_entities", "候选数量", data.get("total")))
    for row in rows[:3]:
        if not isinstance(row, dict):
            continue
        rank = row.get("rank")
        prefix = f"top_{rank}" if rank is not None else f"top_{len(metrics)}"
        name = _display_row_name(entity_type, row)
        _append_metric(metrics, _metric(f"{prefix}_name", f"#{rank or '?'}", name))
        _append_metric(
            metrics,
            _metric(
                f"{prefix}_{metric}",
                f"#{rank or '?'} {metric_label}",
                row.get(metric),
                "plays" if metric == "plays" else "hours",
            ),
        )
        _append_metric(
            metrics,
            _metric(f"{prefix}_share_pct", f"#{rank or '?'} 占比", row.get("share_pct"), "%"),
        )
    return EvidenceCard(
        card_id=f"{entity_type}:{metric}:{source_range or period_label}:analysis_charts",
        title=f"{period_label} {entity_type} 排行证据",
        entity_type=entity_type,
        question_axis=f"ranked_{metric}",
        source=_source(item),
        metrics=metrics,
        limitations=["本地 Spotify 播放记录排行口径"],
    )


def _wrapped_yearly_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    hero = data.get("hero")
    if not isinstance(hero, dict):
        return None
    year = data.get("year") or _source(item).source_range or "年度"
    metrics: list[EvidenceMetric] = []
    total_minutes = hero.get("total_minutes")
    total_hours = round(float(total_minutes) / 60, 2) if total_minutes is not None else None
    _append_metric(
        metrics, _metric("total_plays", "年度播放次数", hero.get("total_plays"), "plays")
    )
    _append_metric(metrics, _metric("total_hours", "年度播放时长", total_hours, "hours"))
    _append_metric(
        metrics, _metric("unique_tracks", "不同歌曲数", hero.get("unique_tracks"), "tracks")
    )
    _append_metric(
        metrics, _metric("unique_artists", "不同艺人数", hero.get("unique_artists"), "artists")
    )
    _append_metric(metrics, _metric("active_days", "活跃天数", hero.get("active_days"), "days"))

    observations: list[str] = []
    top_lists = data.get("top_lists") if isinstance(data.get("top_lists"), dict) else {}
    artists = top_lists.get("artists") if isinstance(top_lists.get("artists"), list) else []
    tracks = top_lists.get("tracks") if isinstance(top_lists.get("tracks"), list) else []
    if artists and isinstance(artists[0], dict):
        artist = artists[0]
        name = str(artist.get("name") or "未知艺人")
        _append_metric(metrics, _metric("top_artist", "年度第一艺人", name))
        _append_metric(
            metrics, _metric("top_artist_plays", "第一艺人播放", artist.get("plays"), "plays")
        )
        _append_metric(
            metrics, _metric("top_artist_hours", "第一艺人时长", artist.get("hours"), "hours")
        )
        observations.append(f"年度第一艺人：{name}")
    if tracks and isinstance(tracks[0], dict):
        track = tracks[0]
        name = _display_row_name("track", track)
        _append_metric(metrics, _metric("top_track", "年度第一歌曲", name))
        _append_metric(
            metrics, _metric("top_track_plays", "第一歌曲播放", track.get("plays"), "plays")
        )

    return EvidenceCard(
        card_id=f"year:{year}:wrapped_yearly",
        title=f"{year} 年度概览证据",
        question_axis="yearly_summary",
        source=_source(item),
        metrics=metrics,
        observations=observations,
        limitations=["本地 Spotify 年度总结口径"],
    )


def _listening_hours_card(item: dict[str, Any], data: dict[str, Any]) -> EvidenceCard | None:
    if data.get("view") != "late_night_tracks":
        return None
    items = data.get("items")
    if not isinstance(items, dict):
        return None
    tracks = items.get("tracks")
    if not isinstance(tracks, list):
        return None
    metrics: list[EvidenceMetric] = []
    _append_metric(
        metrics,
        _metric(
            "total_late_night_plays", "深夜播放总次数", items.get("total_late_night_plays"), "plays"
        ),
    )
    for track in tracks[:3]:
        if not isinstance(track, dict):
            continue
        rank = track.get("rank")
        prefix = f"top_{rank}" if rank is not None else f"top_{len(metrics)}"
        name = _display_row_name("track", track)
        _append_metric(metrics, _metric(f"{prefix}_track", f"#{rank or '?'} 深夜歌曲", name))
        _append_metric(
            metrics,
            _metric(f"{prefix}_plays", f"#{rank or '?'} 深夜播放", track.get("plays"), "plays"),
        )
        _append_metric(
            metrics,
            _metric(f"{prefix}_share_pct", f"#{rank or '?'} 深夜占比", track.get("share_pct"), "%"),
        )
    return EvidenceCard(
        card_id="listening_hours:late_night_tracks",
        title="深夜歌曲排行证据",
        question_axis="time_of_day",
        source=_source(item),
        metrics=metrics,
        limitations=["深夜窗口按 00:00-05:59 本地播放记录统计"],
    )


def build_evidence_cards(tool_results: list[dict[str, Any]]) -> list[EvidenceCard]:
    cards: list[EvidenceCard] = []
    for item in tool_results:
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        tool_name = item.get("tool_name")
        if tool_name == "entity_stats":
            card = _entity_stats_card(item, data)
        elif tool_name == "billboard_entity_detail":
            card = _billboard_card(item, data)
        elif tool_name == "compare_entities":
            card = _comparison_card(item, data)
        elif tool_name == "analysis_charts":
            card = _analysis_charts_card(item, data)
        elif tool_name == "wrapped_yearly":
            card = _wrapped_yearly_card(item, data)
        elif tool_name == "listening_hours":
            card = _listening_hours_card(item, data)
        else:
            card = None
        if card is not None:
            cards.append(card)
    return cards
