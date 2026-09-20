from backend.domains.billboard.chart_load_rank import call_with_billboard_revision_cache
from backend.domains.billboard.chart_staged_cache import (
    _compute_power_scores_cached,
    _compute_records_cached,
    _compute_summaries_cached,
    _compute_weekly_data_cached,
)
from backend.domains.billboard.persistent_cache import get_or_build_billboard_snapshot

_CACHE_PARAM_NAMES = (
    "min_ms",
    "music_only",
    "bb_top_n",
    "bb_album_top_n",
    "bb_artist_top_n",
    "bb_week_start_dow",
    "bb_week_start_hour",
    "year_start",
    "year_end",
    "merge_level",
    "dynamic_threshold",
    "max_merge_gap_minutes",
    "include_compilations",
    "merge_enabled",
)
_CACHE_DEFAULTS = (30000, True, 30, 20, 20, 4, 0, None, None, 2, False, 5, False, True)


def _resolve(args: tuple, kwargs: dict) -> tuple[tuple, dict]:
    if len(args) > len(_CACHE_PARAM_NAMES):
        raise TypeError("too many positional Billboard parameters")
    values = list(_CACHE_DEFAULTS)
    values[: len(args)] = args
    for name, value in kwargs.items():
        if name not in _CACHE_PARAM_NAMES:
            raise TypeError(f"unexpected Billboard parameter: {name}")
        values[_CACHE_PARAM_NAMES.index(name)] = value
    resolved = tuple(values)
    return resolved, dict(zip(_CACHE_PARAM_NAMES, resolved))


def _run(family, builder, args=(), kwargs=None, force_rebuild=False, *, _build_context=None):
    values, params = _resolve(args, kwargs or {})

    def build():
        if _build_context is not None:
            return _build_context.compute(family, params, builder)
        if family == "weekly":
            return call_with_billboard_revision_cache(builder, values)
        return builder(*values)

    return get_or_build_billboard_snapshot(family, params, build, force_rebuild=force_rebuild)


def compute_weekly_data(*args, force_rebuild=False, _build_context=None, **kwargs):
    return _run(
        "weekly",
        _compute_weekly_data_cached,
        args,
        kwargs,
        force_rebuild,
        _build_context=_build_context,
    )


def compute_power_scores_staged(*args, force_rebuild=False, _build_context=None, **kwargs):
    return _run(
        "power_scores",
        _compute_power_scores_cached,
        args,
        kwargs,
        force_rebuild,
        _build_context=_build_context,
    )


def compute_summaries_staged(*args, force_rebuild=False, _build_context=None, **kwargs):
    return _run(
        "summaries",
        _compute_summaries_cached,
        args,
        kwargs,
        force_rebuild,
        _build_context=_build_context,
    )


def compute_records_staged(*args, force_rebuild=False, _build_context=None, **kwargs):
    """Return the records slice while preserving the cached facade contract."""
    return _run(
        "records",
        _compute_records_cached,
        args,
        kwargs,
        force_rebuild,
        _build_context=_build_context,
    )


def compute_all_time_staged(*args, force_rebuild=False, _build_context=None, **kwargs):
    """Return the all-time composition through one durable response snapshot."""
    values, params = _resolve(args, kwargs)

    def build():
        weekly = _run(
            "weekly",
            _compute_weekly_data_cached,
            values,
            force_rebuild=force_rebuild,
            _build_context=_build_context,
        )
        power = _run(
            "power_scores",
            _compute_power_scores_cached,
            values,
            force_rebuild=force_rebuild,
            _build_context=_build_context,
        )
        summaries = _run(
            "summaries",
            _compute_summaries_cached,
            values,
            force_rebuild=force_rebuild,
            _build_context=_build_context,
        )
        return {**weekly, **power, **summaries}

    return get_or_build_billboard_snapshot("all_time", params, build, force_rebuild=force_rebuild)


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]
