"""Deterministic coverage review for bounded AI Agent follow-up tool calls."""

from __future__ import annotations

from typing import Any


def _requested_entities(question_intent: dict[str, Any]) -> list[str]:
    entities = question_intent.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity for entity in entities if isinstance(entity, str) and entity.strip()]


def _requested_metrics(question_intent: dict[str, Any]) -> set[str]:
    metrics = question_intent.get("requested_metrics")
    if not isinstance(metrics, list):
        return set()
    return {metric for metric in metrics if isinstance(metric, str)}


def _entity_param(entity_type: str, entity_name: str) -> dict[str, Any]:
    if entity_type == "album":
        return {"entity": "album", "album_name": entity_name}
    if entity_type == "artist":
        return {"entity": "artist", "artist_name": entity_name}
    return {"entity": "track", "track_name": entity_name}


def _track_resolve_call(entity_name: str) -> dict[str, Any]:
    return {
        "tool_name": "resolve_entity",
        "params": {"entity_type": "track", "query": entity_name},
    }


def _missing_call(tool_name: str, entity_type: str, entity_name: str) -> dict[str, Any]:
    if entity_type == "track":
        return _track_resolve_call(entity_name)
    return {"tool_name": tool_name, "params": _entity_param(entity_type, entity_name)}


def _comparison_already_found(
    requested_entities: list[str],
    entities: dict[str, Any],
    coverage: dict[str, Any],
) -> bool:
    if not requested_entities:
        comparison = coverage.get("comparison")
        return isinstance(comparison, dict) and comparison.get("compare_entities") == "found"
    return all(
        isinstance(entities.get(entity_name), dict)
        and entities[entity_name].get("compare_entities") == "found"
        for entity_name in requested_entities
    )


def review_coverage(
    question_intent: dict[str, Any],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """Review evidence coverage and return one bounded follow-up tool plan."""
    if not isinstance(question_intent, dict):
        question_intent = {}
    if not isinstance(coverage, dict):
        coverage = {}

    task_type = question_intent.get("task_type")
    entity_type = str(question_intent.get("entity_type") or "unknown")
    requested_metrics = _requested_metrics(question_intent)
    requested_entities = _requested_entities(question_intent)
    entities = coverage.get("entities")
    if not isinstance(entities, dict):
        entities = {}

    followup_tool_calls: list[dict[str, Any]] = []
    reasons: list[str] = []
    seen_calls: set[tuple[str, str]] = set()

    def add_followup(tool_name: str, entity_name: str, reason: str) -> None:
        if len(followup_tool_calls) >= 4:
            return
        call = _missing_call(tool_name, entity_type, entity_name)
        identity = (call["tool_name"], repr(sorted(call.get("params", {}).items())))
        if identity in seen_calls:
            return
        seen_calls.add(identity)
        followup_tool_calls.append(call)
        reasons.append(reason)

    if task_type == "comparison" and not _comparison_already_found(
        requested_entities,
        entities,
        coverage,
    ):
        if entity_type == "track" and len(requested_entities) >= 2:
            followup_tool_calls.append(
                {
                    "tool_name": "compare_entities",
                    "params": {
                        "entity_type": "track",
                        "names": requested_entities[:4],
                    },
                }
            )
            reasons.append("歌曲比较缺少完整播放统计和个人榜单证据")
            return {
                "sufficient": False,
                "reasons": reasons,
                "followup_tool_calls": followup_tool_calls,
            }

        for entity_name in requested_entities:
            statuses = entities.get(entity_name, {})
            if not isinstance(statuses, dict):
                statuses = {}
            if statuses.get("compare_entities") == "found":
                continue
            if statuses.get("entity_stats") != "found":
                add_followup(
                    "entity_stats",
                    entity_name,
                    f"{entity_name} 缺少播放统计",
                )
            if (
                "personal_billboard" in requested_metrics
                and statuses.get("billboard_entity_detail") != "found"
            ):
                add_followup(
                    "billboard_entity_detail",
                    entity_name,
                    f"{entity_name} 缺少个人榜单证据",
                )

    return {
        "sufficient": len(followup_tool_calls) == 0,
        "reasons": reasons,
        "followup_tool_calls": followup_tool_calls,
    }


_ALLOWED_FOLLOWUP_TOOLS = {
    "analysis_stats",
    "analysis_charts",
    "wrapped_yearly",
    "entity_stats",
    "billboard_entity_detail",
    "listening_hours",
    "resolve_entity",
    "compare_entities",
    "account_summary",
    "account_collection_insights",
    "search_history",
    "community_feed_search",
    "community_trending",
}

_PERIOD_NAMES = {
    "lifetime",
    "today",
    "this_week",
    "this_year",
    "last_4_weeks",
    "last_6_months",
    "custom",
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


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(key, ""))
        for key in ("source_range", "params_summary", "result_summary", "data")
    )


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

    text = _item_text(item)
    for period_name in _PERIOD_NAMES:
        if period_name in text:
            return period_name
    return ""


def _view_from_item(item: dict[str, Any]) -> str:
    data = item.get("data")
    if isinstance(data, dict) and isinstance(data.get("view"), str):
        return str(data["view"])
    params = item.get("params")
    if isinstance(params, dict) and isinstance(params.get("view"), str):
        return str(params["view"])
    text = _item_text(item)
    for view_name in (
        "late_night_tracks",
        "late_night_ratio",
        "weekday_weekend",
        "platform_hourly",
        "yearly_heatmaps",
        "heatmap",
    ):
        if view_name in text:
            return view_name
    return ""


def _item_has_value(item: dict[str, Any], key: str, expected: str) -> bool:
    data = item.get("data")
    if isinstance(data, dict) and data.get(key) == expected:
        return True
    params = item.get("params")
    if isinstance(params, dict) and params.get(key) == expected:
        return True
    return f"{key}={expected}".casefold() in _item_text(item).casefold()


def _item_period_date(item: dict[str, Any], key: str) -> str:
    data = item.get("data")
    if isinstance(data, dict):
        period = data.get("period")
        if isinstance(period, dict) and isinstance(period.get(key), str):
            return str(period[key])
    params = item.get("params")
    if isinstance(params, dict) and isinstance(params.get(key), str):
        return str(params[key])
    text = _item_text(item)
    for token in text.replace(",", " ").split():
        if token.startswith(f"{key}="):
            return token.split("=", 1)[1]
    return ""


def _has_tool(tool_results: list[dict[str, Any]], tool_name: str) -> bool:
    return any(
        item.get("tool_name") == tool_name and item.get("status") != "error"
        for item in tool_results
    )


def _has_late_night_tool(tool_results: list[dict[str, Any]]) -> bool:
    return any(
        item.get("tool_name") == "listening_hours"
        and item.get("status") != "error"
        and _view_from_item(item) == "late_night_tracks"
        for item in tool_results
    )


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


def _compare_item_matches_names(
    item: dict[str, Any],
    *,
    names: list[str],
    entity_type: str | None = None,
) -> bool:
    if item.get("tool_name") != "compare_entities" or item.get("status") == "error":
        return False
    data = item.get("data")
    if not isinstance(data, dict):
        return False
    if entity_type and data.get("entity_type") not in {None, entity_type}:
        return False
    normalized_names = [name.strip().casefold() for name in names if name.strip()]
    if not normalized_names:
        return True
    row_names = _compare_entity_names(data)
    if row_names:
        return all(name in row_names for name in normalized_names)
    text = _item_text(item).casefold()
    return all(name in text for name in normalized_names)


def _compare_item_matches_frame(item: dict[str, Any], frame: dict[str, Any]) -> bool:
    entity_type = str(frame.get("entity_type") or "")
    names = _requested_frame_entities(frame)
    return _compare_item_matches_names(
        item,
        names=names,
        entity_type=entity_type if entity_type in {"album", "artist", "track"} else None,
    )


def _compare_data(tool_results: list[dict[str, Any]], frame: dict[str, Any]) -> dict[str, Any]:
    for item in tool_results:
        if not _compare_item_matches_frame(item, frame):
            continue
        data = item.get("data")
        if isinstance(data, dict):
            return data
    return {}


def _requested_frame_entities(frame: dict[str, Any]) -> list[str]:
    entities = frame.get("entities")
    if not isinstance(entities, list):
        return []
    return [entity.strip() for entity in entities if isinstance(entity, str) and entity.strip()]


def _scoped_context(frame: dict[str, Any], recipe: dict[str, Any]) -> dict[str, Any]:
    context = recipe.get("required_context")
    if not isinstance(context, dict):
        context = {}
    scope_name = context.get("scope_entity_name") or frame.get("scope_entity_name")
    if not isinstance(scope_name, str) or not scope_name.strip():
        entities = _requested_frame_entities(frame)
        scope_name = entities[0] if entities else ""
    scope_type = context.get("scope_entity_type") or frame.get("scope_entity_type") or "artist"
    target_types = context.get("target_entity_types") or frame.get("target_entity_types")
    if not isinstance(target_types, list):
        target_types = []
    return {
        "scope_entity_type": scope_type if scope_type in {"artist"} else "artist",
        "scope_entity_name": scope_name.strip(),
        "target_entity_types": [
            target
            for target in target_types
            if isinstance(target, str) and target in {"album", "track"}
        ],
    }


def _scoped_entity_stats_items(
    tool_results: list[dict[str, Any]],
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    period: str | None = None,
) -> list[dict[str, Any]]:
    context = _scoped_context(frame, recipe)
    scope_name = context["scope_entity_name"]
    if not scope_name:
        return []
    pattern: dict[str, Any] = {
        "tool_name": "entity_stats",
        "entity": context["scope_entity_type"],
    }
    if period:
        pattern["period"] = period
    return [
        item
        for item in tool_results
        if _item_matches_pattern(item, pattern, entity_name=scope_name)
    ]


def _scoped_rankings_present(
    tool_results: list[dict[str, Any]],
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
) -> bool:
    context = _scoped_context(frame, recipe)
    target_types = context["target_entity_types"] or ["track"]
    for item in _scoped_entity_stats_items(
        tool_results,
        frame=frame,
        recipe=recipe,
        period="lifetime",
    ):
        data = item.get("data")
        if not isinstance(data, dict):
            continue
        has_all_targets = True
        if "album" in target_types:
            top_albums = data.get("top_albums")
            has_all_targets = has_all_targets and isinstance(top_albums, list) and bool(top_albums)
        if "track" in target_types:
            top_tracks = data.get("top_tracks")
            has_all_targets = has_all_targets and isinstance(top_tracks, list) and bool(top_tracks)
        if has_all_targets:
            return True
    return False


def _item_mentions_entity(item: dict[str, Any], entity_name: str) -> bool:
    return entity_name.casefold() in _item_text(item).casefold()


def _item_matches_pattern(
    item: dict[str, Any],
    pattern: dict[str, Any],
    *,
    entity_name: str | None = None,
) -> bool:
    if item.get("status") == "error" or item.get("tool_name") != pattern.get("tool_name"):
        return False
    if entity_name and not _item_mentions_entity(item, entity_name):
        return False

    period = pattern.get("period")
    if isinstance(period, str) and _period_from_item(item) != period:
        return False

    view = pattern.get("view")
    if isinstance(view, str) and _view_from_item(item) != view:
        return False

    entity = pattern.get("entity") or pattern.get("entity_type")
    if isinstance(entity, str) and not (
        _item_has_value(item, "entity", entity) or _item_has_value(item, "entity_type", entity)
    ):
        return False

    metric = pattern.get("metric")
    if isinstance(metric, str) and not _item_has_value(item, "metric", metric):
        return False

    for date_key in ("start_date", "end_date"):
        expected_date = pattern.get(date_key)
        if isinstance(expected_date, str) and _item_period_date(item, date_key) != expected_date:
            return False

    return True


def _pattern_with_required_context(
    pattern: dict[str, Any],
    *,
    frame: dict[str, Any],
    required_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if pattern.get("tool_name") != "analysis_charts":
        return pattern

    context = {
        **(required_context or {}),
        **{key: value for key, value in pattern.items() if key != "tool_name"},
    }
    entity = context.get("entity") or context.get("entity_type") or frame.get("entity_type")
    if entity not in {"album", "artist", "track"}:
        entity = "track"
    metric = context.get("metric")
    if metric not in {"plays", "hours"}:
        metric = "plays"

    return {
        **pattern,
        "entity": entity,
        "metric": metric,
        **_period_params_from_scope(
            context.get("period") or context.get("time_scope") or frame.get("time_scope")
        ),
    }


def _pattern_is_covered(
    pattern: dict[str, Any],
    *,
    frame: dict[str, Any],
    tool_results: list[dict[str, Any]],
    required_context: dict[str, Any] | None = None,
) -> bool:
    pattern = _pattern_with_required_context(
        pattern,
        frame=frame,
        required_context=required_context,
    )
    tool_name = pattern.get("tool_name")
    if not isinstance(tool_name, str):
        return False
    if tool_name == "compare_entities":
        return any(_compare_item_matches_frame(item, frame) for item in tool_results)

    entities = _requested_frame_entities(frame)
    if tool_name in {"entity_stats", "billboard_entity_detail"} and entities:
        return all(
            any(
                _item_matches_pattern(item, pattern, entity_name=entity_name)
                for item in tool_results
            )
            for entity_name in entities
        )

    return any(_item_matches_pattern(item, pattern) for item in tool_results)


def _required_patterns(recipe: dict[str, Any]) -> list[dict[str, Any]]:
    patterns = recipe.get("required_tool_patterns")
    if not isinstance(patterns, list):
        return []
    return [pattern for pattern in patterns if isinstance(pattern, dict)]


def _required_recent_periods(recipe: dict[str, Any]) -> set[str]:
    return {
        str(pattern["period"])
        for pattern in _required_patterns(recipe)
        if pattern.get("tool_name") == "entity_stats"
        and pattern.get("period") in {"last_6_months", "last_4_weeks"}
    }


def _has_required_recent_period(
    tool_results: list[dict[str, Any]],
    frame: dict[str, Any],
    period: str,
) -> bool:
    return _pattern_is_covered(
        {"tool_name": "entity_stats", "period": period},
        frame=frame,
        tool_results=tool_results,
    )


def _period_params_from_scope(time_scope: Any) -> dict[str, Any]:
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
    if time_scope in _PERIOD_NAMES:
        return {"period": time_scope}
    return {"period": "lifetime"}


def _entity_tool_calls(
    tool_name: str,
    frame: dict[str, Any],
    extra_params: dict[str, Any],
) -> list[dict[str, Any]]:
    entity_type = str(frame.get("entity_type") or "unknown")
    if entity_type not in {"album", "artist", "track"}:
        return []

    calls: list[dict[str, Any]] = []
    for entity_name in _requested_frame_entities(frame):
        if entity_type == "track":
            calls.append(
                {
                    "tool_name": "resolve_entity",
                    "params": {"entity_type": "track", "query": entity_name},
                }
            )
            continue
        params = _entity_param(entity_type, entity_name)
        params.update(extra_params)
        calls.append({"tool_name": tool_name, "params": params})
    return calls


def _tool_calls_for_pattern(
    pattern: dict[str, Any],
    *,
    frame: dict[str, Any],
    required_context: dict[str, Any],
) -> list[dict[str, Any]]:
    tool_name = pattern.get("tool_name")
    if not isinstance(tool_name, str) or tool_name not in _ALLOWED_FOLLOWUP_TOOLS:
        return []

    if tool_name == "compare_entities":
        entities = _requested_frame_entities(frame)
        entity_type = str(frame.get("entity_type") or "unknown")
        if entity_type in {"album", "artist", "track"} and len(entities) >= 2:
            return [
                {
                    "tool_name": "compare_entities",
                    "params": {"entity_type": entity_type, "names": entities[:4]},
                }
            ]
        return []

    if tool_name in {"entity_stats", "billboard_entity_detail"}:
        extra_params = {
            key: value
            for key, value in pattern.items()
            if key not in {"tool_name"} and isinstance(key, str)
        }
        return _entity_tool_calls(tool_name, frame, extra_params)

    if tool_name == "analysis_charts":
        context = {**required_context, **{k: v for k, v in pattern.items() if k != "tool_name"}}
        entity = context.get("entity") or context.get("entity_type") or frame.get("entity_type")
        if entity not in {"album", "artist", "track"}:
            entity = "track"
        metric = context.get("metric")
        if metric not in {"plays", "hours"}:
            metric = "plays"
        period_params = _period_params_from_scope(
            context.get("period") or context.get("time_scope") or frame.get("time_scope")
        )
        return [
            {
                "tool_name": "analysis_charts",
                "params": {
                    "entity": entity,
                    "metric": metric,
                    **period_params,
                    "limit": 10,
                },
            }
        ]

    if tool_name == "analysis_stats":
        period = pattern.get("period")
        params = _period_params_from_scope(period) if isinstance(period, str) else {}
        return [{"tool_name": "analysis_stats", "params": params}]

    if tool_name == "listening_hours":
        view = pattern.get("view")
        params = {"view": view} if isinstance(view, str) else {}
        return [{"tool_name": "listening_hours", "params": params}]

    if tool_name in {
        "account_summary",
        "account_collection_insights",
        "search_history",
        "community_feed_search",
        "community_trending",
    }:
        params = {
            key: value
            for key, value in pattern.items()
            if key != "tool_name" and isinstance(key, str)
        }
        return [{"tool_name": tool_name, "params": params}]

    if tool_name == "wrapped_yearly":
        time_scope = frame.get("time_scope")
        if isinstance(time_scope, str) and time_scope.startswith("year:"):
            year = time_scope.split(":", 1)[1]
            if year.isdigit():
                return [{"tool_name": "wrapped_yearly", "params": {"year": int(year)}}]
        return []

    return []


def _call_identity(call: dict[str, Any]) -> tuple[str, str]:
    params = call.get("params") if isinstance(call.get("params"), dict) else {}
    return str(call.get("tool_name")), repr(sorted(params.items()))


def _call_entity_name(call: dict[str, Any]) -> str | None:
    params = call.get("params")
    if not isinstance(params, dict):
        return None
    for key in ("album_name", "artist_name", "track_name", "query"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _call_matches_existing_result(
    call: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> bool:
    if call.get("tool_name") == "compare_entities":
        params = call.get("params")
        if not isinstance(params, dict):
            return False
        names = params.get("names")
        entity_type = params.get("entity_type")
        return isinstance(names, list) and any(
            _compare_item_matches_names(
                item,
                names=[name for name in names if isinstance(name, str)],
                entity_type=entity_type if isinstance(entity_type, str) else None,
            )
            for item in tool_results
        )

    pattern = {"tool_name": call.get("tool_name")}
    params = call.get("params")
    if isinstance(params, dict):
        pattern.update(
            {
                key: params[key]
                for key in (
                    "period",
                    "view",
                    "entity",
                    "entity_type",
                    "metric",
                    "start_date",
                    "end_date",
                )
                if key in params
            }
        )
    entity_name = _call_entity_name(call)
    return any(
        _item_matches_pattern(item, pattern, entity_name=entity_name) for item in tool_results
    )


def _axis_coverage_for(
    axis: str,
    *,
    frame: dict[str, Any],
    recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
) -> str:
    comparison = _compare_data(tool_results, frame)
    family = str(frame.get("family") or recipe.get("family") or "")

    if family == "scoped_ranking":
        if axis in {"scope", "cumulative"}:
            return (
                "covered"
                if _scoped_entity_stats_items(
                    tool_results,
                    frame=frame,
                    recipe=recipe,
                    period="lifetime",
                )
                else "missing"
            )
        if axis == "ranking":
            return (
                "covered"
                if _scoped_rankings_present(tool_results, frame=frame, recipe=recipe)
                else "missing"
            )
        if axis == "recency":
            return (
                "covered"
                if _scoped_entity_stats_items(
                    tool_results,
                    frame=frame,
                    recipe=recipe,
                    period="last_6_months",
                )
                else "missing"
            )

    if axis == "cumulative":
        has_cumulative = (
            _has_tool(tool_results, "compare_entities")
            or _has_tool(tool_results, "entity_stats")
            or _has_tool(tool_results, "analysis_stats")
        )
        return "covered" if has_cumulative else "missing"

    if axis == "recency":
        periods = _required_recent_periods(recipe)
        if periods:
            return (
                "covered"
                if all(
                    _has_required_recent_period(tool_results, frame, period) for period in periods
                )
                else "missing"
            )
        return (
            "covered"
            if any(
                _period_from_item(item) in {"last_6_months", "last_4_weeks"}
                for item in tool_results
            )
            else "missing"
        )

    if axis == "intensity":
        return "covered" if comparison.get("winner_by_intensity") else "missing"

    if axis == "personal_billboard":
        if comparison.get("winner_by_power_score") or comparison.get("winner_by_power_rank"):
            return "covered"
        return "covered" if _has_tool(tool_results, "billboard_entity_detail") else "missing"

    if axis == "fairness":
        notes = comparison.get("fairness_notes")
        return "covered" if isinstance(notes, list) and notes else "partial"

    if axis == "time_of_day":
        return "covered" if _has_late_night_tool(tool_results) else "missing"

    if axis == "collection":
        return (
            "covered"
            if _has_tool(tool_results, "account_collection_insights")
            or _has_tool(tool_results, "account_summary")
            else "missing"
        )

    if axis == "search":
        return "covered" if _has_tool(tool_results, "search_history") else "missing"

    if axis == "community":
        return (
            "covered"
            if _has_tool(tool_results, "community_trending")
            or _has_tool(tool_results, "community_feed_search")
            else "missing"
        )

    if axis == "safety":
        return "covered"

    if axis == "ranking":
        required_context = recipe.get("required_context")
        if not isinstance(required_context, dict):
            required_context = {}
        ranking_patterns = [
            pattern
            for pattern in _required_patterns(recipe)
            if pattern.get("tool_name") in {"analysis_charts", "wrapped_yearly"}
        ]
        if ranking_patterns:
            has_ranking = any(
                _pattern_is_covered(
                    pattern,
                    frame=frame,
                    tool_results=tool_results,
                    required_context=required_context,
                )
                for pattern in ranking_patterns
            )
        else:
            has_ranking = (
                _has_tool(tool_results, "analysis_charts")
                or _has_tool(tool_results, "wrapped_yearly")
                or _has_late_night_tool(tool_results)
            )
        return "covered" if has_ranking else "missing"

    if axis == "trend":
        has_trend = _has_tool(tool_results, "analysis_charts") or any(
            _period_from_item(item) in {"last_6_months", "last_4_weeks"} for item in tool_results
        )
        return "covered" if has_trend else "missing"

    if axis == "period":
        return (
            "covered"
            if _has_tool(tool_results, "wrapped_yearly")
            or _has_tool(tool_results, "analysis_charts")
            else "missing"
        )

    if axis == "behavior":
        return "covered" if _has_tool(tool_results, "listening_hours") else "missing"

    if axis == "detail":
        return (
            "covered"
            if _has_tool(tool_results, "entity_stats")
            or _has_tool(tool_results, "billboard_entity_detail")
            else "missing"
        )

    if axis == "consistency":
        rows = comparison.get("entities")
        if isinstance(rows, list) and rows:
            has_consistency = all(
                isinstance(row, dict) and row.get("weeks_on_chart") is not None for row in rows
            )
            return "covered" if has_consistency else "partial"
        return "missing"

    if axis == "peak":
        rows = comparison.get("entities")
        if isinstance(rows, list) and rows:
            peak_keys = ("peak_position", "power_score", "power_rank", "no1_weeks")
            has_peak = all(
                isinstance(row, dict) and any(row.get(key) is not None for key in peak_keys)
                for row in rows
            )
            return "covered" if has_peak else "partial"
        return "missing"

    return "missing"


def review_evidence_sufficiency(
    *,
    question_frame: dict[str, Any],
    evidence_recipe: dict[str, Any],
    tool_results: list[dict[str, Any]],
    coverage: dict[str, Any],
) -> dict[str, Any]:
    """Review axis-level evidence sufficiency and return bounded read-only follow-ups."""
    frame = _as_dict(question_frame)
    recipe = _as_dict(evidence_recipe)
    normalized_results = _as_tool_results(tool_results)

    required_axes = recipe.get("required_axes")
    if not isinstance(required_axes, list):
        required_axes = []
    conditional_axes = recipe.get("conditional_axes")
    if not isinstance(conditional_axes, list):
        conditional_axes = []
    requested_axes = list(dict.fromkeys([*required_axes, *conditional_axes]))

    axis_coverage = {
        str(axis): _axis_coverage_for(
            str(axis),
            frame=frame,
            recipe=recipe,
            tool_results=normalized_results,
        )
        for axis in requested_axes
    }
    missing_axes = [
        axis
        for axis, status in axis_coverage.items()
        if axis in required_axes and status != "covered"
    ]

    max_followups = int(recipe.get("max_followup_calls") or 4)
    required_context = recipe.get("required_context")
    if not isinstance(required_context, dict):
        required_context = {}

    missing_patterns = [
        pattern
        for pattern in _required_patterns(recipe)
        if not _pattern_is_covered(
            pattern,
            frame=frame,
            tool_results=normalized_results,
            required_context=required_context,
        )
    ]

    reasons = [f"{frame.get('family')} 缺少 {axis} 证据" for axis in missing_axes]
    for pattern in missing_patterns:
        tool_name = pattern.get("tool_name")
        if isinstance(tool_name, str):
            reasons.append(f"{frame.get('family')} 缺少 {tool_name} 工具证据")

    followups: list[dict[str, Any]] = []
    seen_calls: set[tuple[str, str]] = set()

    def add_followup(call: dict[str, Any]) -> None:
        if len(followups) >= max_followups:
            return
        tool_name = call.get("tool_name")
        if not isinstance(tool_name, str) or tool_name not in _ALLOWED_FOLLOWUP_TOOLS:
            return
        if _call_matches_existing_result(call, normalized_results):
            return
        identity = _call_identity(call)
        if identity in seen_calls:
            return
        seen_calls.add(identity)
        followups.append(call)

    for pattern in missing_patterns:
        for call in _tool_calls_for_pattern(
            pattern,
            frame=frame,
            required_context=required_context,
        ):
            add_followup(call)

    if "personal_billboard" in missing_axes:
        for call in _entity_tool_calls("billboard_entity_detail", frame, {}):
            add_followup(call)
    if "time_of_day" in missing_axes:
        add_followup({"tool_name": "listening_hours", "params": {"view": "late_night_tracks"}})
    if "ranking" in missing_axes and frame.get("family") != "scoped_ranking":
        for call in _tool_calls_for_pattern(
            {"tool_name": "analysis_charts"},
            frame=frame,
            required_context=required_context,
        ):
            add_followup(call)

    legacy_review = review_coverage(
        question_intent={
            "task_type": frame.get("task_type"),
            "entity_type": frame.get("entity_type"),
            "entities": frame.get("entities", []),
            "requested_metrics": frame.get("requested_metrics", []),
        },
        coverage=coverage,
    )
    for call in legacy_review.get("followup_tool_calls", []):
        if isinstance(call, dict):
            add_followup(call)
    reasons.extend(str(reason) for reason in legacy_review.get("reasons", []))

    return {
        "sufficient": (
            not missing_axes
            and not missing_patterns
            and bool(legacy_review.get("sufficient", True))
        ),
        "axis_coverage": axis_coverage,
        "missing_axes": missing_axes,
        "reasons": reasons,
        "followup_tool_calls": followups[:max_followups],
    }
