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
_CACHE_DEFAULTS = {
    "min_ms": 30000,
    "music_only": True,
    "bb_top_n": 30,
    "bb_album_top_n": 20,
    "bb_artist_top_n": 20,
    "bb_week_start_dow": 4,
    "bb_week_start_hour": 0,
    "year_start": None,
    "year_end": None,
    "merge_level": 2,
    "dynamic_threshold": False,
    "max_merge_gap_minutes": 5,
    "include_compilations": False,
    "merge_enabled": True,
}


def _cache_params(values: dict) -> dict:
    return {name: values.get(name, _CACHE_DEFAULTS[name]) for name in _CACHE_PARAM_NAMES}


def compute_weekly_data(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
    *,
    force_rebuild=False,
):
    values = locals().copy()
    args = tuple(values[name] for name in _CACHE_PARAM_NAMES)
    params = _cache_params(values)
    return get_or_build_billboard_snapshot(
        "weekly",
        params,
        lambda: call_with_billboard_revision_cache(_compute_weekly_data_cached, args),
        force_rebuild=force_rebuild,
    )


def compute_power_scores_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
    *,
    force_rebuild=False,
):
    values = locals().copy()
    args = tuple(values[name] for name in _CACHE_PARAM_NAMES)
    params = _cache_params(values)
    return get_or_build_billboard_snapshot(
        "power_scores",
        params,
        lambda: _compute_power_scores_cached(
            *args[:10],
            dynamic_threshold=args[10],
            max_merge_gap_minutes=args[11],
            include_compilations=args[12],
            merge_enabled=args[13],
        ),
        force_rebuild=force_rebuild,
    )


def compute_summaries_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
    *,
    force_rebuild=False,
):
    values = locals().copy()
    args = tuple(values[name] for name in _CACHE_PARAM_NAMES)
    params = _cache_params(values)
    return get_or_build_billboard_snapshot(
        "summaries",
        params,
        lambda: _compute_summaries_cached(
            *args[:10],
            dynamic_threshold=args[10],
            max_merge_gap_minutes=args[11],
            include_compilations=args[12],
            merge_enabled=args[13],
        ),
        force_rebuild=force_rebuild,
    )


def compute_records_staged(*args, **kwargs):
    """Return the records slice while preserving the cached facade contract."""
    force_rebuild = bool(kwargs.pop("force_rebuild", False))
    values = dict(zip(_CACHE_PARAM_NAMES, args))
    values.update(kwargs)
    params = _cache_params(values)
    return get_or_build_billboard_snapshot(
        "records",
        params,
        lambda: _compute_records_cached(*args, **kwargs),
        force_rebuild=force_rebuild,
    )


def compute_all_time_staged(
    min_ms=30000,
    music_only=True,
    bb_top_n=30,
    bb_album_top_n=20,
    bb_artist_top_n=20,
    bb_week_start_dow=4,
    bb_week_start_hour=0,
    year_start=None,
    year_end=None,
    merge_level=2,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    include_compilations=False,
    merge_enabled=True,
    *,
    force_rebuild=False,
):
    """Return the all-time composition through one durable response snapshot."""
    params = _cache_params(locals())

    def build() -> dict:
        common = dict(params)
        weekly = compute_weekly_data(**common, force_rebuild=force_rebuild)
        power = compute_power_scores_staged(**common, force_rebuild=force_rebuild)
        summaries = compute_summaries_staged(**common, force_rebuild=force_rebuild)
        return {**weekly, **power, **summaries}

    return get_or_build_billboard_snapshot(
        "all_time",
        params,
        build,
        force_rebuild=force_rebuild,
    )


compute_weekly_data.cache_clear = _compute_weekly_data_cached.cache_clear  # type: ignore[attr-defined]
compute_power_scores_staged.cache_clear = _compute_power_scores_cached.cache_clear  # type: ignore[attr-defined]
compute_summaries_staged.cache_clear = _compute_summaries_cached.cache_clear  # type: ignore[attr-defined]
compute_records_staged.cache_clear = _compute_records_cached.cache_clear  # type: ignore[attr-defined]
