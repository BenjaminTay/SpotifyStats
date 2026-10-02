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


def _credit_key(frame: pd.DataFrame, *, legacy_raw: bool) -> pd.DataFrame:
    result = frame.copy()
    result.attrs = {}
    if "representative_track_id" in result.columns:
        key = result["representative_track_id"]
    elif legacy_raw and "l1_id" not in result.columns and "track_id" in result.columns:
        # Only isolated legacy databases have track_id == raw tracks.track_id.
        key = result["track_id"]
    else:
        key = pd.Series(None, index=result.index, dtype=object)
    result["_credit_track_id"] = pd.to_numeric(key, errors="coerce")
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


def _duration_dedupe(frame: pd.DataFrame, entity_key: str) -> pd.DataFrame:
    # Membership fan-out may repeat one interval within a single project.
    # Separate listening slices remain separate, including slices of a shared
    # source play_id. Never use play_id alone as the duration identity.
    keys = [entity_key]
    for column in (
        "_credit_track_id",
        "_logical_event_id",
        "play_id",
        "ts",
        "slice_start_at",
        "slice_end_at",
        "interval_start_at",
        "interval_end_at",
        "ms_played",
    ):
        if column in frame.columns:
            keys.append(column)
    return frame.drop_duplicates(keys)


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
        keyed = _credit_key(frame, legacy_raw=legacy_raw)
        requested.update(int(value) for value in keyed["_credit_track_id"].dropna().unique())
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
        keyed = _credit_key(frame, legacy_raw=legacy_raw)
        return keyed[keyed["_credit_track_id"].isin(cooperating)].copy()

    selected = select(events)
    tracks = _event_projection(select(track_frame), events)
    albums = _event_projection(select(album_frame), events)
    artists = (
        selected.drop(columns=["artist_id", "artist_name", "role"], errors="ignore")
        .merge(credits, on="_credit_track_id", how="inner")
        .drop_duplicates(["_logical_event_id", "artist_id"])
    )
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
    artist_duration = artist_duration_source.drop(
        columns=["artist_id", "artist_name", "role"], errors="ignore"
    ).merge(credits, on="_credit_track_id", how="inner")

    # The full effective names are attached only to observed collaboration
    # versions. A solo member of an L3 group contributes neither counts nor
    # its duration/credits to this board.
    names = credits.groupby("_credit_track_id", sort=False)["artist_name"].agg(list)
    tracks["artist_names"] = tracks["_credit_track_id"].map(names)
    tracks["artist_name"] = tracks["artist_names"].map(lambda value: value[0] if value else "")
    return CollaborationFacts(
        total_events=len(events),
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
    frame = frame.copy()
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
        duration = duration.copy()
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
