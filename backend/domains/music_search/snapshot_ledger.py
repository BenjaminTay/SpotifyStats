"""Pure reconstruction of music-search context rows from a compact chart ledger."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import date
from typing import Any, Literal, Optional, cast

import pandas as pd

from backend.domains.billboard.chart_power_score import (
    compute_album_power_scores,
    compute_artist_power_scores,
    compute_power_scores,
)
from backend.domains.music_search.contracts import (
    MusicSearchEntityKeyKind,
    parse_music_search_entity_key,
)

LedgerFamily = Literal["track", "album", "artist"]
WeeklyLedgerRow = tuple[str, str, str, int, int, int, str]
ContextRow = tuple[
    str,
    int,
    int,
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[int],
    Optional[str],
    Optional[str],
    Optional[str],
]

_FAMILY_KINDS: dict[LedgerFamily, set[MusicSearchEntityKeyKind]] = {
    "track": {"track"},
    "album": {"album", "album_project"},
    "artist": {"artist"},
}
_PAYLOAD_KEYS: dict[LedgerFamily, set[str]] = {
    "track": {"entity_id", "track_name", "artist_name"},
    "album": {"entity_id", "album_name", "artist_name"},
    "artist": {"entity_id", "artist_name"},
}
_KIND_ORDER = {"track": 0, "album": 1, "album_project": 1, "artist": 2}


class WeeklyLedgerValidationError(ValueError):
    """Raised when a compact weekly ledger cannot prove exact reconstruction."""


def _strict_int(value: Any, *, label: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise WeeklyLedgerValidationError(f"invalid {label}")
    return value


def _validated_week(value: Any) -> str:
    if not isinstance(value, str):
        raise WeeklyLedgerValidationError("invalid ledger week")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise WeeklyLedgerValidationError("invalid ledger week") from exc
    if parsed.isoformat() != value:
        raise WeeklyLedgerValidationError("ledger week is not canonical ISO date")
    return value


def _validated_payload(
    family: LedgerFamily,
    raw_payload: Any,
    *,
    entity_id: int,
) -> dict[str, Any]:
    if not isinstance(raw_payload, str):
        raise WeeklyLedgerValidationError("invalid ledger stable payload")
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError) as exc:
        raise WeeklyLedgerValidationError("invalid ledger stable payload") from exc
    if not isinstance(payload, dict) or set(payload) != _PAYLOAD_KEYS[family]:
        raise WeeklyLedgerValidationError("invalid ledger stable payload fields")
    if _strict_int(payload.get("entity_id"), label="payload entity id", minimum=1) != entity_id:
        raise WeeklyLedgerValidationError("ledger entity key and payload disagree")
    for key, value in payload.items():
        if key != "entity_id" and value is not None and not isinstance(value, str):
            raise WeeklyLedgerValidationError("invalid ledger display identity")
    return payload


def _validated_entity_key(value: Any) -> tuple[str, MusicSearchEntityKeyKind, int]:
    if not isinstance(value, str):
        raise WeeklyLedgerValidationError("invalid ledger entity key")
    try:
        parsed = parse_music_search_entity_key(value)
    except ValueError as exc:
        raise WeeklyLedgerValidationError("invalid ledger entity key") from exc
    return value, parsed.kind, parsed.entity_id


def _validated_metrics(
    lifetime_metrics: Mapping[str, tuple[int, int]],
    candidate_keys: set[str],
) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    for entity_key, values in lifetime_metrics.items():
        key, _kind, _entity_id = _validated_entity_key(entity_key)
        if key not in candidate_keys:
            raise WeeklyLedgerValidationError("lifetime metric is not an active candidate")
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes)) or len(values) != 2:
            raise WeeklyLedgerValidationError("invalid lifetime metric pair")
        play_events = _strict_int(values[0], label="lifetime play events", minimum=0)
        total_ms = _strict_int(values[1], label="lifetime total milliseconds", minimum=0)
        result[key] = (play_events, total_ms)
    return result


def _validate_album_identity(kinds: Collection[MusicSearchEntityKeyKind]) -> None:
    album_kinds = {kind for kind in kinds if kind in {"album", "album_project"}}
    if len(album_kinds) > 1:
        raise WeeklyLedgerValidationError("mixed L1 and L2/L3 album identities")


def _validated_frames(
    weekly_rows: Iterable[WeeklyLedgerRow],
    candidate_keys: set[str],
    *,
    top_n_by_family: Mapping[LedgerFamily, int],
) -> dict[LedgerFamily, pd.DataFrame]:
    records: dict[LedgerFamily, list[dict[str, Any]]] = {
        "track": [],
        "album": [],
        "artist": [],
    }
    identities: dict[str, dict[str, Any]] = {}
    seen_facts: set[tuple[LedgerFamily, str, str]] = set()
    ranks_by_week: dict[tuple[LedgerFamily, str], set[int]] = defaultdict(set)
    facts_by_week: dict[tuple[LedgerFamily, str], list[tuple[int, int, int, int]]] = defaultdict(
        list
    )
    observed_kinds: set[MusicSearchEntityKeyKind] = set()

    for raw_row in weekly_rows:
        if not isinstance(raw_row, Sequence) or isinstance(raw_row, (str, bytes)):
            raise WeeklyLedgerValidationError("invalid weekly ledger row")
        if len(raw_row) != 7:
            raise WeeklyLedgerValidationError("invalid weekly ledger row width")
        family_value, week_value, key_value, rank_value, plays_value, ms_value, payload_value = (
            raw_row
        )
        if family_value not in _FAMILY_KINDS:
            raise WeeklyLedgerValidationError("invalid ledger family")
        family = cast(LedgerFamily, family_value)
        week = _validated_week(week_value)
        entity_key, kind, entity_id = _validated_entity_key(key_value)
        observed_kinds.add(kind)
        if kind not in _FAMILY_KINDS[family]:
            raise WeeklyLedgerValidationError("ledger family and entity kind disagree")
        if entity_key not in candidate_keys:
            raise WeeklyLedgerValidationError("ledger entity is not an active candidate")
        rank = _strict_int(rank_value, label="ledger rank", minimum=1)
        if rank > top_n_by_family[family]:
            raise WeeklyLedgerValidationError("ledger rank exceeds configured chart limit")
        play_count = _strict_int(plays_value, label="ledger play count", minimum=1)
        total_ms = _strict_int(ms_value, label="ledger total milliseconds", minimum=0)
        payload = _validated_payload(family, payload_value, entity_id=entity_id)

        fact_key = (family, week, entity_key)
        if fact_key in seen_facts:
            raise WeeklyLedgerValidationError("duplicate ledger entity-week fact")
        seen_facts.add(fact_key)
        week_key = (family, week)
        if rank in ranks_by_week[week_key]:
            raise WeeklyLedgerValidationError("duplicate ledger weekly rank")
        ranks_by_week[week_key].add(rank)
        facts_by_week[week_key].append((rank, play_count, total_ms, entity_id))
        existing_payload = identities.setdefault(entity_key, payload)
        if existing_payload != payload:
            raise WeeklyLedgerValidationError("ledger display identity changed across weeks")

        record = {
            "billboard_week": week,
            "entity_key": entity_key,
            "entity_id": entity_id,
            "rank": rank,
            "play_count": play_count,
            "total_ms": total_ms,
            **payload,
        }
        records[family].append(record)

    _validate_album_identity(observed_kinds)
    for ranks in ranks_by_week.values():
        if sorted(ranks) != list(range(1, len(ranks) + 1)):
            raise WeeklyLedgerValidationError("ledger weekly ranks are not contiguous")
    for facts in facts_by_week.values():
        expected = sorted(facts, key=lambda item: (-item[1], -item[2], item[3]))
        if any(fact[0] != position for position, fact in enumerate(expected, start=1)):
            raise WeeklyLedgerValidationError("ledger weekly rank disagrees with ranking facts")

    frames: dict[LedgerFamily, pd.DataFrame] = {}
    for family, family_records in records.items():
        frame = pd.DataFrame(family_records)
        if not frame.empty:
            frame = frame.sort_values(["billboard_week", "entity_id"], kind="stable").reset_index(
                drop=True
            )
        frames[family] = frame
    return frames


def _power_maps(
    frames: Mapping[LedgerFamily, pd.DataFrame],
    *,
    top_n_by_family: Mapping[LedgerFamily, int],
) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    track = frames["track"]
    if not track.empty:
        track_frame = track.rename(columns={"entity_id": "track_id"})
        scored = compute_power_scores(track_frame, top_n_by_family["track"])
        key_by_id = {
            int(cast(Any, row.entity_id)): str(row.entity_key)
            for row in track.itertuples(index=False)
        }
        for row in scored.itertuples(index=False):
            result[key_by_id[int(row.track_id)]] = (int(row.power_score), int(row.power_rank))

    album = frames["album"]
    if not album.empty:
        album_frame = album.copy()
        album_frame["album_project_id"] = album_frame["entity_id"]
        album_frame["album_name"] = album_frame["entity_id"].map(lambda value: f"{int(value):020d}")
        album_frame["artist_name"] = ""
        scored = compute_album_power_scores(album_frame, top_n_by_family["album"])
        key_by_surrogate = {
            f"{int(cast(Any, row.entity_id)):020d}": str(row.entity_key)
            for row in album.itertuples(index=False)
        }
        for row in scored.itertuples(index=False):
            result[key_by_surrogate[str(row.album_name)]] = (
                int(row.power_score),
                int(row.power_rank),
            )

    artist = frames["artist"]
    if not artist.empty:
        artist_frame = artist.copy()
        artist_frame["artist_id"] = artist_frame["entity_id"]
        artist_frame["artist_name"] = artist_frame["entity_id"].map(
            lambda value: f"{int(value):020d}"
        )
        scored = compute_artist_power_scores(artist_frame, top_n_by_family["artist"])
        key_by_surrogate = {
            f"{int(cast(Any, row.entity_id)):020d}": str(row.entity_key)
            for row in artist.itertuples(index=False)
        }
        for row in scored.itertuples(index=False):
            result[key_by_surrogate[str(row.artist_name)]] = (
                int(row.power_score),
                int(row.power_rank),
            )
    return result


def _chart_values(
    frames: Mapping[LedgerFamily, pd.DataFrame],
) -> dict[str, tuple[int, int, int, int, str, str, str]]:
    result: dict[str, tuple[int, int, int, int, str, str, str]] = {}
    for frame in frames.values():
        if frame.empty:
            continue
        for entity_key, group in frame.groupby("entity_key", sort=False):
            peak = int(group["rank"].min())
            peak_rows = group[group["rank"] == peak]
            result[str(entity_key)] = (
                peak,
                int(len(peak_rows)),
                int(group["billboard_week"].nunique()),
                int((group["rank"] == 1).sum()),
                str(group["billboard_week"].min()),
                str(group["billboard_week"].max()),
                str(peak_rows["billboard_week"].min()),
            )
    return result


def rebuild_context_rows_from_weekly_ledger(
    weekly_rows: Iterable[WeeklyLedgerRow],
    lifetime_metrics: Mapping[str, tuple[int, int]],
    candidate_keys: Collection[str],
    *,
    track_top_n: int,
    album_top_n: int,
    artist_top_n: int,
) -> list[ContextRow]:
    """Rebuild exact search context rows from complete ranked weekly facts.

    Power scores are recomputed across every entity in each chart family. Album
    and artist scoring use numeric entity IDs as their grouping and tie keys, so
    duplicate display names cannot merge otherwise distinct search entities.
    """
    top_n_by_family: dict[LedgerFamily, int] = {
        "track": _strict_int(track_top_n, label="track chart limit", minimum=1),
        "album": _strict_int(album_top_n, label="album chart limit", minimum=1),
        "artist": _strict_int(artist_top_n, label="artist chart limit", minimum=1),
    }
    validated_candidates: set[str] = set()
    for value in candidate_keys:
        entity_key, _kind, _entity_id = _validated_entity_key(value)
        validated_candidates.add(entity_key)
    metrics = _validated_metrics(lifetime_metrics, validated_candidates)
    frames = _validated_frames(
        weekly_rows,
        validated_candidates,
        top_n_by_family=top_n_by_family,
    )
    fact_kinds = {
        parse_music_search_entity_key(entity_key).kind
        for entity_key in set(metrics)
        | {
            str(entity_key)
            for frame in frames.values()
            if not frame.empty
            for entity_key in frame["entity_key"].unique()
        }
    }
    _validate_album_identity(fact_kinds)
    powers = _power_maps(frames, top_n_by_family=top_n_by_family)
    charts = _chart_values(frames)

    result: list[ContextRow] = []
    entity_keys = set(metrics) | set(charts)
    for entity_key in sorted(
        entity_keys,
        key=lambda value: (
            _KIND_ORDER[parse_music_search_entity_key(value).kind],
            parse_music_search_entity_key(value).entity_id,
        ),
    ):
        play_events, total_ms = metrics.get(entity_key, (0, 0))
        chart = charts.get(entity_key)
        if play_events <= 0 and chart is None:
            continue
        if chart is None:
            result.append(
                (
                    entity_key,
                    play_events,
                    total_ms,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                )
            )
            continue
        power_score, power_rank = powers[entity_key]
        peak, peak_weeks, weeks, no1_weeks, first_week, latest_week, first_peak = chart
        result.append(
            (
                entity_key,
                play_events,
                total_ms,
                peak,
                peak_weeks,
                weeks,
                no1_weeks,
                power_score,
                power_rank,
                first_week,
                latest_week,
                first_peak,
            )
        )
    return result
