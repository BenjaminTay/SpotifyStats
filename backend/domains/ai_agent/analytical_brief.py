"""Deterministic analytical briefs for AI Agent final answers."""

from __future__ import annotations

from typing import Any

LOCAL_BILLBOARD_NOTE = "SpotifyStats Billboard 是本地个人榜单，不是外部官方 Billboard"

_RECENT_PERIOD_KEYS = {
    "last_6_months": "recent_6_months",
    "last_4_weeks": "recent_4_weeks",
}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _as_tool_results(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _as_evidence_cards(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_as_dict(item) for item in value if _as_dict(item)]


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped


def _text_blob(item: dict[str, Any]) -> str:
    parts = [
        item.get("source_range"),
        item.get("params_summary"),
        item.get("result_summary"),
        item.get("params"),
        item.get("data"),
    ]
    return " ".join(str(part) for part in parts if part is not None)


def _frame_entities(frame: dict[str, Any]) -> list[str]:
    entities = frame.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity.strip() for entity in entities if isinstance(entity, str) and entity.strip()]


def _compare_entity_names(data: dict[str, Any]) -> set[str]:
    rows = data.get("entities")
    if not isinstance(rows, list):
        return set()
    names: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in ("requested_name", "name"):
            value = row.get(key)
            if isinstance(value, str) and value.strip():
                names.add(value.strip().casefold())
    return names


def _compare_item_matches_frame(item: dict[str, Any], frame: dict[str, Any]) -> bool:
    if item.get("tool_name") != "compare_entities" or item.get("status") == "error":
        return False
    data = item.get("data")
    if not isinstance(data, dict):
        return False
    entity_type = frame.get("entity_type")
    if entity_type in {"album", "artist", "track"} and data.get("entity_type") not in {
        None,
        entity_type,
    }:
        return False
    entities = [entity.casefold() for entity in _frame_entities(frame)]
    if not entities:
        return True
    row_names = _compare_entity_names(data)
    if row_names:
        return all(entity in row_names for entity in entities)
    text = _text_blob(item).casefold()
    return all(entity in text for entity in entities)


def _compare_data(tool_results: list[dict[str, Any]], frame: dict[str, Any]) -> dict[str, Any]:
    for item in tool_results:
        if not _compare_item_matches_frame(item, frame):
            continue
        data = item.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _winner_values(compare_data: dict[str, Any]) -> dict[str, str]:
    winners: dict[str, str] = {}
    mapping = {
        "cumulative_plays": compare_data.get("winner_by_cumulative_plays"),
        "total_hours": compare_data.get("winner_by_total_hours"),
        "power_score": compare_data.get("winner_by_power_score"),
        "power_rank": compare_data.get("winner_by_power_rank"),
        "intensity": compare_data.get("winner_by_intensity"),
    }
    for key, value in mapping.items():
        if value:
            winners[key] = str(value)

    personal_billboard = winners.get("power_score") or winners.get("power_rank")
    if personal_billboard:
        winners["personal_billboard"] = personal_billboard
    return winners


def _has_conflict(winners: dict[str, str]) -> bool:
    values = {winner for winner in winners.values() if winner}
    return len(values) > 1


def _period_from_item(item: dict[str, Any]) -> str:
    data = item.get("data")
    if isinstance(data, dict):
        period = data.get("period")
        if isinstance(period, str):
            return period
        if isinstance(period, dict):
            value = period.get("period") or period.get("label")
            if isinstance(value, str):
                return value

    params = item.get("params")
    if isinstance(params, dict):
        period = params.get("period")
        if isinstance(period, str):
            return period

    text = _text_blob(item)
    for period in _RECENT_PERIOD_KEYS:
        if period in text:
            return period
    return ""


def _metric_value_from_item(item: dict[str, Any]) -> float | None:
    data = item.get("data")
    if not isinstance(data, dict):
        return None

    candidates: list[Any] = [
        data.get("total_plays"),
        data.get("plays"),
    ]
    summary = data.get("summary")
    if isinstance(summary, dict):
        candidates.extend([summary.get("total_plays"), summary.get("plays")])

    for value in candidates:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _entity_name_from_item(item: dict[str, Any], entities: list[str]) -> str | None:
    normalized_entities = {entity.casefold(): entity for entity in entities}

    params = item.get("params")
    if isinstance(params, dict):
        for key in ("album_name", "artist_name", "track_name", "entity_name", "name", "query"):
            value = params.get(key)
            if isinstance(value, str) and value.casefold() in normalized_entities:
                return normalized_entities[value.casefold()]

    data = item.get("data")
    if isinstance(data, dict):
        for key in ("album_name", "artist_name", "track_name", "entity_name", "name"):
            value = data.get(key)
            if isinstance(value, str) and value.casefold() in normalized_entities:
                return normalized_entities[value.casefold()]

    text = _text_blob(item).casefold()
    for entity in entities:
        if entity.casefold() in text:
            return entity
    return None


def _item_matches_entity_type(item: dict[str, Any], entity_type: str | None) -> bool:
    if entity_type not in {"album", "artist", "track"}:
        return True
    data = item.get("data")
    if isinstance(data, dict):
        value = data.get("entity") or data.get("entity_type")
        if isinstance(value, str):
            return value == entity_type
    params = item.get("params")
    if isinstance(params, dict):
        value = params.get("entity") or params.get("entity_type")
        if isinstance(value, str):
            return value == entity_type
    text = _text_blob(item).casefold()
    return f"entity={entity_type}".casefold() in text or f"entity_type={entity_type}" in text


def _recent_period_winners(
    tool_results: list[dict[str, Any]],
    *,
    entities: list[str],
    entity_type: str | None = None,
) -> dict[str, str]:
    expected_entities = {entity.casefold() for entity in entities if entity}
    scores: dict[str, list[tuple[float, str]]] = {period: [] for period in _RECENT_PERIOD_KEYS}
    for item in tool_results:
        if item.get("tool_name") != "entity_stats" or item.get("status") == "error":
            continue
        period = _period_from_item(item)
        if period not in scores:
            continue
        if not _item_matches_entity_type(item, entity_type):
            continue
        entity_name = _entity_name_from_item(item, entities)
        value = _metric_value_from_item(item)
        if entity_name and value is not None:
            scores[period].append((value, entity_name))

    winners: dict[str, str] = {}
    for period, rows in scores.items():
        if not rows:
            continue
        if expected_entities and {name.casefold() for _, name in rows} != expected_entities:
            continue
        rows.sort(key=lambda row: row[0], reverse=True)
        winners[_RECENT_PERIOD_KEYS[period]] = rows[0][1]
    return winners


def _period_params_from_scope(time_scope: Any) -> dict[str, str]:
    if not isinstance(time_scope, str) or not time_scope:
        return {"period": "lifetime"}
    if time_scope.startswith("year:"):
        year = time_scope.split(":", 1)[1]
        if year.isdigit():
            return {
                "period": "custom",
                "start_date": f"{year}-01-01",
                "end_date": f"{year}-12-31",
            }
    if time_scope in {
        "lifetime",
        "today",
        "this_week",
        "this_year",
        "last_4_weeks",
        "last_6_months",
        "custom",
    }:
        return {"period": time_scope}
    return {"period": "lifetime"}


def _item_period_date(item: dict[str, Any], key: str) -> str:
    data = item.get("data")
    if isinstance(data, dict):
        period = data.get("period")
        if isinstance(period, dict) and isinstance(period.get(key), str):
            return str(period[key])
    source_range = item.get("source_range")
    if isinstance(source_range, str) and ".." in source_range:
        start, end = source_range.split("..", 1)
        if key == "start_date" and start:
            return start
        if key == "end_date" and end:
            return end
    text = _text_blob(item)
    for token in text.replace(",", " ").split():
        if token.startswith(f"{key}="):
            return token.split("=", 1)[1]
    return ""


def _ranking_item_matches_context(
    item: dict[str, Any],
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
) -> bool:
    data = item.get("data")
    if not isinstance(data, dict):
        return False
    context = recipe.get("required_context")
    if not isinstance(context, dict):
        context = {}
    expected_entity = (
        context.get("entity_type") or context.get("entity") or frame.get("entity_type")
    )
    if expected_entity in {"album", "artist", "track"} and data.get("entity") != expected_entity:
        return False
    expected_metric = context.get("metric") or "plays"
    if expected_metric in {"plays", "hours"} and data.get("metric") != expected_metric:
        return False
    period_params = _period_params_from_scope(context.get("time_scope") or frame.get("time_scope"))
    period = data.get("period")
    data_period = period.get("period") if isinstance(period, dict) else None
    if data_period is not None and data_period != period_params.get("period"):
        return False
    for date_key in ("start_date", "end_date"):
        expected_date = period_params.get(date_key)
        if expected_date and _item_period_date(item, date_key) != expected_date:
            return False
    return True


def _ranking_top_result(
    tool_results: list[dict[str, Any]],
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
) -> str | None:
    for item in tool_results:
        if item.get("tool_name") != "analysis_charts" or item.get("status") == "error":
            continue
        if not _ranking_item_matches_context(item, frame=frame, recipe=recipe):
            continue
        data = item.get("data")
        rows = data.get("rows") if isinstance(data, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        first = rows[0]
        if not isinstance(first, dict):
            continue
        for key in ("artist_name", "album_name", "track_name", "name"):
            value = first.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _recipe_required_axes(recipe: dict[str, Any]) -> set[str]:
    axes = recipe.get("required_axes")
    if not isinstance(axes, list):
        return set()
    return {axis for axis in axes if isinstance(axis, str)}


def _has_personal_billboard_context(
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    winners: dict[str, str] | None = None,
    tool_results: list[dict[str, Any]] | None = None,
) -> bool:
    if "personal_billboard" in _recipe_required_axes(recipe):
        return True
    axes = frame.get("analysis_axes")
    if isinstance(axes, list) and "personal_billboard" in axes:
        return True
    if winners and any(
        key in winners for key in ("personal_billboard", "power_score", "power_rank")
    ):
        return True
    return bool(tool_results) and any(
        item.get("tool_name") == "billboard_entity_detail" and item.get("status") != "error"
        for item in tool_results
    )


def _comparison_must_explain(
    compare_data: dict[str, Any],
    *,
    conflict: bool,
    include_billboard_note: bool,
) -> list[str]:
    must_explain: list[str] = []
    if include_billboard_note:
        must_explain.append(LOCAL_BILLBOARD_NOTE)
    must_explain.append("累计值受进入播放历史时间影响")
    if conflict:
        must_explain.append("不同口径胜者不一致，不能说单方明显胜出")

    fairness_notes = compare_data.get("fairness_notes")
    if isinstance(fairness_notes, list):
        must_explain.extend(str(note) for note in fairness_notes if isinstance(note, str))
    return _dedupe(must_explain)


def _billboard_forbidden_claims() -> list[str]:
    return [
        "市场影响力更大",
        "外部官方 Billboard 成绩",
    ]


def _preference_brief(
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    compare_data = _compare_data(tool_results, frame)
    missing_notes: list[str] = []
    recent_winners = _recent_period_winners(
        tool_results,
        entities=_frame_entities(frame),
        entity_type=str(frame.get("entity_type") or ""),
    )
    if (
        _frame_entities(frame)
        and any(
            item.get("tool_name") == "entity_stats"
            and item.get("status") != "error"
            and _period_from_item(item) in _RECENT_PERIOD_KEYS
            for item in tool_results
        )
        and not recent_winners
    ):
        missing_notes.append("近期窗口证据未覆盖所有比较对象")
    winners = {
        **_winner_values(compare_data),
        **recent_winners,
    }
    conflict = _has_conflict(winners)
    long_term = winners.get("cumulative_plays") or winners.get("personal_billboard")
    recent_intensity = (
        winners.get("intensity")
        or winners.get("recent_4_weeks")
        or winners.get("recent_6_months")
        or winners.get("total_hours")
    )

    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "比较对象哪一个更能代表用户偏好",
        "dimension_winners": winners,
        "conflict": conflict,
        "recommended_conclusion": {
            "long_term": long_term,
            "recent_intensity": recent_intensity,
            "single_answer_if_forced": long_term or recent_intensity,
        },
        "must_explain": _dedupe(
            [
                *_comparison_must_explain(
                    compare_data,
                    conflict=conflict,
                    include_billboard_note=_has_personal_billboard_context(
                        frame=frame,
                        recipe=recipe,
                        winners=winners,
                    ),
                ),
                *missing_notes,
            ]
        ),
        "forbidden_claims": _dedupe(
            [
                *_billboard_forbidden_claims(),
                *(
                    [
                        "所有指标均指向同一对象",
                        "明显单方胜出",
                    ]
                    if conflict
                    else []
                ),
            ]
        ),
        "evidence_recipe": recipe,
    }


def _simple_ranking_brief(
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "找出指定范围内的最高排名结果",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {
            "top_result": _ranking_top_result(tool_results, frame=frame, recipe=recipe)
        },
        "must_explain": ["说明时间范围和排序指标"],
        "forbidden_claims": ["混用不同时间范围"],
        "evidence_recipe": recipe,
    }


def _time_of_day_brief(*, frame: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "找出指定时段内的偏好排行",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {"time_axis": "late_night_tracks"},
        "must_explain": ["说明时段窗口，不能用总体排行替代时段排行"],
        "forbidden_claims": ["用总体排行替代深夜排行"],
        "evidence_recipe": recipe,
    }


def _entity_detail_brief(
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> dict[str, Any]:
    must_explain = ["只基于本地工具证据回答"]
    forbidden_claims = ["声称访问了 DATA 之外的数据"]
    if _has_personal_billboard_context(frame=frame, recipe=recipe, tool_results=tool_results):
        must_explain.append(LOCAL_BILLBOARD_NOTE)
        forbidden_claims.extend(_billboard_forbidden_claims())

    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "解释实体在本地听歌数据中的表现",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {"required_axes": sorted(_recipe_required_axes(recipe))},
        "must_explain": _dedupe(must_explain),
        "forbidden_claims": _dedupe(forbidden_claims),
        "evidence_recipe": recipe,
    }


def _habit_summary_brief(*, frame: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    return {
        "family": frame.get("family"),
        "answer_contract": frame.get("answer_contract"),
        "main_question": "概括用户听歌习惯或解释播放指标边界",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {
            "required_axes": sorted(_recipe_required_axes(recipe)),
        },
        "must_explain": [
            "不能只用单一播放次数判断喜好",
            "需要结合行为证据和累计证据",
        ],
        "forbidden_claims": [
            "忽略行为证据",
            "把播放次数直接等同于最喜欢",
        ],
        "evidence_recipe": recipe,
    }


def build_analytical_brief(
    *,
    question_frame: dict[str, Any],
    evidence_recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
    coverage: dict[str, Any],
    evidence_cards: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a deterministic final-answer brief from local read-only evidence."""
    frame = _as_dict(question_frame)
    recipe = _as_dict(evidence_recipe)
    results = _as_tool_results(tool_results)
    family = str(frame.get("family") or recipe.get("family") or "habit_summary")

    if family in {"preference_comparison", "identity_preference"}:
        return _preference_brief(frame=frame, recipe=recipe, tool_results=results)
    if family == "simple_ranking":
        return _simple_ranking_brief(frame=frame, recipe=recipe, tool_results=results)
    if family == "time_of_day_ranking":
        return _time_of_day_brief(frame=frame, recipe=recipe)
    if family == "entity_detail":
        return _entity_detail_brief(frame=frame, recipe=recipe, tool_results=results)
    if family == "habit_summary":
        return _habit_summary_brief(frame=frame, recipe=recipe)

    return {
        "family": family,
        "answer_contract": frame.get("answer_contract"),
        "main_question": "概括用户问题对应的本地听歌数据证据",
        "dimension_winners": {},
        "conflict": False,
        "recommended_conclusion": {},
        "must_explain": ["只基于本地工具证据回答"],
        "forbidden_claims": ["声称访问了 DATA 之外的数据"],
        "evidence_recipe": recipe,
        "coverage": _as_dict(coverage),
        "evidence_card_count": len(_as_evidence_cards(evidence_cards)),
    }
