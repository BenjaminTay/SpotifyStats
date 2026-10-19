"""Shared collaboration facts, resolved before recording/composition aggregation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.domains.metadata.track_credits import get_effective_track_credit_frame
from backend.domains.playback.counting import assign_logical_event_id
from backend.domains.playback.logical_timeline import get_listening_duration_frame
from backend.domains.playback.records_helpers import records_duration_frame


@dataclass
class CollaborationFacts:
    total_events: int
    events: pd.DataFrame
    tracks: pd.DataFrame
    albums: pd.DataFrame
    artists: pd.DataFrame
    track_duration: pd.DataFrame
    album_duration: pd.DataFrame
    artist_duration: pd.DataFrame


def _credit_track_ids(frame: pd.DataFrame, *, legacy_raw: bool) -> pd.Series:
    if "representative_track_id" in frame.columns:
        key = frame["representative_track_id"]
    elif legacy_raw and "l1_id" not in frame.columns and "track_id" in frame.columns:
        # Only isolated legacy databases have track_id == raw tracks.track_id.
        key = frame["track_id"]
    else:
        key = pd.Series(None, index=frame.index, dtype=object)
    return pd.to_numeric(key, errors="coerce")


def _credit_key(frame: pd.DataFrame, *, legacy_raw: bool) -> pd.DataFrame:
    result = frame.copy()
    result.attrs = {}
    result["_credit_track_id"] = _credit_track_ids(result, legacy_raw=legacy_raw)
    return result


def _event_projection(frame: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Carry the common event identity through a legacy entity projection.

    Normal service frames already inherit the ID before the project join. A
    legacy caller may omit it; join on actual event facts, never entity-frame
    row ordinals (an album membership join can duplicate or reorder rows).
    """
    if frame.empty:
        return frame
    if "_logical_event_id" in frame.columns:
        return frame[frame["_logical_event_id"].isin(events["_logical_event_id"])].copy()
    keys = [
        key
        for key in ("play_id", "_credit_track_id", "ts", "ms_played")
        if key in frame.columns and key in events.columns
    ]
    if "play_id" not in keys or "_credit_track_id" not in keys:
        return frame.iloc[0:0].assign(_logical_event_id=pd.Series(dtype=object))
    return frame.merge(events[[*keys, "_logical_event_id"]].drop_duplicates(), on=keys)


_DURATION_DEDUPE_COLUMNS = (
    "_credit_track_id",
    "_logical_event_id",
    "play_id",
    "ts",
    "slice_start_at",
    "slice_end_at",
    "interval_start_at",
    "interval_end_at",
    "ms_played",
)


def _duration_dedupe(frame: pd.DataFrame, entity_key: str) -> pd.DataFrame:
    # Membership fan-out may repeat one interval within a single project.
    # Separate listening slices remain separate, including slices of a shared
    # source play_id. Never use play_id alone as the duration identity.
    keys = [entity_key]
    for column in _DURATION_DEDUPE_COLUMNS:
        if column in frame.columns:
            keys.append(column)
    return frame.drop_duplicates(keys)


def _expand_artist_credits(frame, credits, *, deduplicate_events):
    """Fan out keys before taking one owned, full-schema payload result."""
    replaced = ("artist_id", "artist_name", "role")
    overlapping = set(frame.columns).intersection(credits.columns) - {
        "_credit_track_id",
        *replaced,
    }
    if overlapping:
        # Preserve pandas' suffix/error contract for extra caller metadata.
        result = frame.drop(columns=list(replaced), errors="ignore").merge(
            credits, on="_credit_track_id", how="inner"
        )
        return (
            result.drop_duplicates(["_logical_event_id", "artist_id"])
            if deduplicate_events
            else result
        )

    columns = ["_credit_track_id"]
    if deduplicate_events:
        columns.append("_logical_event_id")
    keys = frame[columns].copy()
    position = "_collaboration_row"
    while position in frame.columns or position in credits.columns:
        position += "_"
    keys[position] = range(len(frame))
    matched = keys.merge(credits, on="_credit_track_id", how="inner")
    if deduplicate_events:
        matched = matched.drop_duplicates(["_logical_event_id", "artist_id"])
    result = frame.take(matched[position].to_numpy())
    result.index = matched.index
    result.columns = result.columns.rename(matched.columns.name)
    result.attrs = {}
    # Empty joins can take the right key's dtype rather than the source's.
    result["_credit_track_id"] = matched["_credit_track_id"].array
    for column in replaced:
        if column in result.columns:
            del result[column]
    for column in credits.columns:
        if column != "_credit_track_id":
            result[column] = matched[column].array
    return result


def build_collaboration_facts(event_frame, track_frame, album_frame, artist_frame, conn=None):
    """Resolve effective canonical credits once for this Records build.

    Without a connection, only a canonical artist fan-out with representative
    raw track IDs is accepted. A title or display-name list is not identity
    evidence, and cannot re-add a collaborator removed by manual governance.
    """
    legacy_raw = bool(
        conn is not None
        and conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_identities'"
        ).fetchone()
        is None
    )
    events = _credit_key(assign_logical_event_id(event_frame), legacy_raw=legacy_raw)
    events = events.drop_duplicates("_logical_event_id")
    frames = [event_frame, track_frame, album_frame]
    durations = [records_duration_frame(frame, copy=False) for frame in frames]
    requested = set()
    for frame in [*frames, *durations]:
        # Only the credit IDs are consumed here; keep the wide event/duration
        # copies confined to the later collaboration projections.
        requested.update(
            int(value)
            for value in _credit_track_ids(frame, legacy_raw=legacy_raw).dropna().unique()
        )
    del frames, frame
    if conn is not None and requested:
        credits = get_effective_track_credit_frame(conn, sorted(requested)).rename(
            columns={"track_id": "_credit_track_id"}
        )
    elif (
        "representative_track_id" in artist_frame.columns
        and "artist_name" in artist_frame.columns
        and (
            "canonical_artist_id" in artist_frame.columns or "raw_artist_id" in artist_frame.columns
        )
        and ("artist_id" in artist_frame.columns or "canonical_artist_id" in artist_frame.columns)
    ):
        credits = artist_frame.rename(
            columns={"representative_track_id": "_credit_track_id"}
        ).copy()
        if "canonical_artist_id" in credits.columns:
            credits["artist_id"] = credits["canonical_artist_id"]
    else:
        credits = pd.DataFrame(columns=["_credit_track_id", "artist_id", "artist_name", "role"])
    if "role" not in credits.columns:
        credits["role"] = "primary"
    credits = credits[["_credit_track_id", "artist_id", "artist_name", "role"]].dropna(
        subset=["_credit_track_id", "artist_id"]
    )
    credits["_role_order"] = credits["role"].ne("primary").astype(int)
    credits = credits.sort_values(["_role_order", "artist_id", "artist_name"], kind="stable")
    credits = credits.drop_duplicates(["_credit_track_id", "artist_id"])
    counts = credits.groupby("_credit_track_id")["artist_id"].nunique()
    cooperating = set(counts[counts >= 2].index)

    def select(frame):
        keys = _credit_track_ids(frame, legacy_raw=legacy_raw)
        mask = keys.isin(cooperating)
        selected = frame.loc[mask].copy()
        selected.attrs = {}
        # Keep the dtype inferred from the complete source, including rows
        # excluded by this mask, as in the former full-frame key projection.
        selected["_credit_track_id"] = keys.loc[mask]
        return selected

    selected = select(events)
    tracks = _event_projection(select(track_frame), events)
    albums = _event_projection(select(album_frame), events)
    total_events = len(events)
    # The wide identity projection is no longer needed by credit fan-out.
    del events
    artists = _expand_artist_credits(selected, credits, deduplicate_events=True)
    track_duration = (
        select(durations[1])
        if get_listening_duration_frame(track_frame) is not None
        else tracks.copy()
    )
    album_duration = (
        select(durations[2])
        if get_listening_duration_frame(album_frame) is not None
        else albums.copy()
    )
    artist_duration_source = (
        select(durations[0]) if get_listening_duration_frame(event_frame) is not None else selected
    )
    # Newly exploded hourly tables have no remaining consumer after selection.
    del durations
    artist_duration = _expand_artist_credits(
        artist_duration_source, credits, deduplicate_events=False
    )
    del artist_duration_source

    # The full effective names are attached only to observed collaboration
    # versions. A solo member of an L3 group contributes neither counts nor
    # its duration/credits to this board.
    names = credits.groupby("_credit_track_id", sort=False)["artist_name"].agg(list)
    tracks["artist_names"] = tracks["_credit_track_id"].map(names)
    tracks["artist_name"] = tracks["artist_names"].map(lambda value: value[0] if value else "")
    return CollaborationFacts(
        total_events=total_events,
        events=selected,
        tracks=tracks,
        albums=albums,
        artists=artists,
        track_duration=track_duration,
        album_duration=album_duration,
        artist_duration=artist_duration,
    )


def aggregate_collaboration(frame, duration, identity_col, name_col, entity_type):
    """Count each common logical event once per entity and use exact duration."""
    if frame.empty or identity_col not in frame.columns or name_col not in frame.columns:
        return pd.DataFrame()
    columns = {
        identity_col,
        name_col,
        "_logical_event_id",
        "artist_name",
        "artist_names",
        "_credit_track_id",
        "ms_played",
    }
    frame = frame[[column for column in frame.columns if column in columns]].copy()
    frame["entity_id"] = frame[identity_col].map(entity_id_string)
    frame = frame[frame["entity_id"].notna()]
    events = frame.drop_duplicates(["_logical_event_id", "entity_id"])
    result = events.groupby("entity_id", sort=False).agg(count=("_logical_event_id", "nunique"))
    # Stable display selection does not split one entity when display names
    # changed, or when a song has several credited collaboration versions.
    display = frame.sort_values(
        ["entity_id", name_col, "artist_name"], kind="stable"
    ).drop_duplicates("entity_id")
    display = display.set_index("entity_id")
    result["name"] = display[name_col]
    result["artist_name"] = display["artist_name"]
    result["entity_type"] = entity_type
    if "artist_names" in frame.columns:
        member_names = (
            frame.sort_values(["entity_id", "_credit_track_id"], kind="stable")[
                ["entity_id", "artist_names"]
            ]
            .explode("artist_names")
            .drop_duplicates()
        )
        result["artist_names"] = member_names.groupby("entity_id", sort=False)["artist_names"].agg(
            list
        )
    if not duration.empty and identity_col in duration.columns:
        duration_columns = {identity_col, *_DURATION_DEDUPE_COLUMNS}
        duration = duration[
            [column for column in duration.columns if column in duration_columns]
        ].copy()
        duration["entity_id"] = duration[identity_col].map(entity_id_string)
        duration = _duration_dedupe(duration, "entity_id")
        duration_totals = duration.groupby("entity_id")["ms_played"].sum()
    else:
        duration_totals = events.groupby("entity_id")["ms_played"].sum()
    result["total_ms"] = result.index.map(duration_totals).fillna(0)
    result["value"] = result["count"].astype(float)
    result["unit"] = "次"
    result["total_hours"] = (result["total_ms"] / 3_600_000).round(1)
    return result.reset_index()


def entity_id_string(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value)) if float(value).is_integer() else str(value)
    return str(value)
