"""Billboard track/artist/album detail endpoints."""

from __future__ import annotations

import sqlite3
import unicodedata

import pandas as pd

from backend.core.db import (
    fan_out_weekly_for_artists,
    get_db,
    get_track_artist_names_map,
)
from backend.core.json_helpers import df_to_json
from backend.domains.billboard.chart_compute import compute_billboard_data
from backend.domains.metadata.album_detail_meta import resolve_album_detail_meta
from backend.domains.metadata.artist_genres import resolve_artist_genres
from backend.domains.metadata.artist_spotify_meta import resolve_artist_spotify_meta
from backend.domains.metadata.track_presentation import resolve_track_presentation


def _stable_detail_track_sort(
    frame: pd.DataFrame,
    *,
    primary_columns: tuple[str, ...],
    primary_ascending: tuple[bool, ...],
) -> pd.DataFrame:
    result = frame.copy()
    result["_stable_track_name"] = (
        result["track_name"]
        .fillna("")
        .map(lambda value: unicodedata.normalize("NFKC", str(value)).casefold())
    )
    return result.sort_values(
        [*primary_columns, "track_id", "_stable_track_name", "track_name"],
        ascending=[*primary_ascending, True, True, True],
        kind="stable",
    ).drop(columns=["_stable_track_name"])


def _track_primary_artist_name(track_id: int, fallback: str) -> str:
    """Return the canonical primary credit used to resolve album ownership."""
    conn = get_db()
    try:
        representative_track_id = _representative_track_id(conn, track_id)
        row = conn.execute(
            "SELECT artist_id FROM tracks WHERE track_id=?", (representative_track_id,)
        ).fetchone()
        if row is None:
            return fallback
        from backend.domains.metadata.artist_identity import resolve_artist_id

        return resolve_artist_id(conn, int(row[0])).display_name
    finally:
        conn.close()


def _representative_track_id(conn: sqlite3.Connection, l1_id: int) -> int:
    has_l1 = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_identities'"
    ).fetchone()
    if has_l1:
        row = conn.execute(
            "SELECT representative_track_id FROM track_l1_identities WHERE l1_id=?",
            (int(l1_id),),
        ).fetchone()
        if row is not None and row[0] is not None:
            return int(row[0])
    return int(l1_id)


def _track_identity_fields(l1_id: int) -> dict[str, int]:
    conn = get_db()
    try:
        return {
            "l1_id": int(l1_id),
            "representative_track_id": _representative_track_id(conn, int(l1_id)),
        }
    finally:
        conn.close()


def _load_detail_access_stats(
    kind: str,
    *,
    min_ms: int,
    music_only: bool,
    merge_enabled: bool,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    track_id: int | None = None,
    album_name: str | None = None,
    artist_name: str | None = None,
    merge_level: int = 2,
) -> dict:
    """Resolve detail-page eligibility through the effective-play pipeline.

    Billboard summaries are Top-N qualified and therefore cannot be used as an
    entity-existence test. Versus pickers intentionally remain chart-qualified;
    detail routes instead fall back to the same effective-play facts used by
    global search and personal entity statistics.
    """
    from backend.services.entity_stats_service import (
        get_album_stats,
        get_artist_stats,
        get_track_stats,
    )

    conn = get_db()
    try:
        common = (
            min_ms,
            music_only,
            merge_enabled,
            "lifetime",
            None,
            None,
            dynamic_threshold,
            max_merge_gap_minutes,
        )
        if kind == "track" and track_id is not None:
            return get_track_stats(
                conn,
                track_id,
                *common,
                merge_level=merge_level,
                include_rank_context=False,
            )
        if kind == "album" and album_name is not None:
            return get_album_stats(
                conn,
                album_name,
                artist_name,
                *common,
                merge_level=merge_level,
                include_rank_context=False,
            )
        if kind == "artist" and artist_name is not None:
            return get_artist_stats(conn, artist_name, *common, include_rank_context=False)
        return {"found": False}
    finally:
        conn.close()


def _effective_play_count(stats: dict) -> int:
    return int((stats.get("summary") or {}).get("total_plays") or 0)


def _load_detail_weighted_frame(
    *,
    min_ms: int,
    music_only: bool,
    week_start_dow: int,
    week_start_hour: int,
    dynamic_threshold: bool,
    max_merge_gap_minutes: int | None,
    merge_enabled: bool,
) -> pd.DataFrame | None:
    """Load the same logical-event weighted frame used by Billboard charts."""
    from backend.domains.billboard.data_loader import load_billboard_raw
    from backend.domains.playback.logical_timeline import get_billboard_weighted_frame

    events = load_billboard_raw(
        min_ms,
        music_only,
        week_start_dow,
        week_start_hour,
        dynamic_threshold,
        max_merge_gap_minutes,
        merge_enabled,
    )
    return get_billboard_weighted_frame(events)


def _compute_change_column(hist_df):
    """Compute NEW/RE/▲n/▼n/─ change column for a sorted weekly history DataFrame."""
    hist = hist_df.sort_values("billboard_week").copy()
    week_dt = pd.to_datetime(hist["billboard_week"])
    hist["prev_rank"] = hist["rank"].shift(1)
    changes = []
    for i, (_, r) in enumerate(hist.iterrows()):
        p = r["prev_rank"]
        cur = r["rank"]
        if pd.isna(p):
            changes.append("NEW")
        else:
            cw = week_dt.iloc[i]
            pw = week_dt.iloc[i - 1]
            if (cw - pw).days > 8:
                changes.append("RE")
            else:
                diff = int(p) - int(cur)
                if diff > 0:
                    changes.append(f"▲{diff}")
                elif diff < 0:
                    changes.append(f"▼{abs(diff)}")
                else:
                    changes.append("─")
    hist["change"] = changes
    return hist


def _build_gapped_chart_data(hist_df):
    """Build x/y arrays with None gaps for >9 day breaks in chart history."""
    chart_data = hist_df.sort_values("billboard_week")[
        ["billboard_week", "rank", "play_count"]
    ].copy()
    chart_data["week_dt"] = pd.to_datetime(chart_data["billboard_week"])

    x_vals, y_vals, texts = [], [], []
    for i, (_, row) in enumerate(chart_data.iterrows()):
        if i > 0:
            gap_days = (row["week_dt"] - chart_data.iloc[i - 1]["week_dt"]).days
            if gap_days > 9:
                x_vals.append(None)
                y_vals.append(None)
                texts.append(None)
        x_vals.append(str(row["billboard_week"]))
        y_vals.append(int(row["rank"]))
        texts.append(f"#{int(row['rank'])} · {int(row['play_count'])}次")
    return x_vals, y_vals, texts


def _get_track_spotify_meta(track_id, merge_level=2, weighted_frame=None):
    """Fetch Spotify metadata for a canonical L1 identity."""
    conn = get_db()
    has_l1 = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_l1_identities'"
    ).fetchone()
    row = (
        conn.execute(
            """SELECT stm.duration_ms, stm.popularity, stm.explicit,
                  stm.track_number, stm.disc_number,
                  sam.album_name AS spotify_album_name
           FROM track_l1_identities li
           JOIN tracks t ON t.track_id=li.representative_track_id
           LEFT JOIN track_l1_external_ids external
             ON external.l1_id=li.l1_id
            AND external.provider='spotify' AND external.is_primary=1
           JOIN spotify_track_meta stm ON stm.spotify_track_id=COALESCE(
                external.external_track_id, t.spotify_track_id
           )
           LEFT JOIN spotify_album_meta sam ON stm.spotify_album_id = sam.spotify_album_id
           WHERE li.l1_id = ?
           LIMIT 1""",
            (track_id,),
        ).fetchone()
        if has_l1
        else None
    )

    if not row:
        representative_track_id = _representative_track_id(conn, int(track_id))
        row = conn.execute(
            """SELECT stm.duration_ms, stm.popularity, stm.explicit,
                      stm.track_number, stm.disc_number,
                      sam.album_name AS spotify_album_name
                 FROM tracks t
                 JOIN spotify_track_meta stm ON t.spotify_track_id=stm.spotify_track_id
                 LEFT JOIN spotify_album_meta sam
                   ON stm.spotify_album_id=sam.spotify_album_id
                WHERE t.track_id=? LIMIT 1""",
            (representative_track_id,),
        ).fetchone()

    if not row:
        conn.close()
        return None

    meta = {}
    if row["duration_ms"] is not None:
        meta["duration_ms"] = row["duration_ms"]
    if row["popularity"] is not None:
        meta["popularity"] = row["popularity"]
    meta["explicit"] = bool(row["explicit"])
    if row["track_number"] is not None:
        meta["track_number"] = row["track_number"]
    if row["disc_number"] is not None:
        meta["disc_number"] = row["disc_number"]
    if row["spotify_album_name"]:
        meta["spotify_album_name"] = row["spotify_album_name"]

    # Version group: if this track belongs to a track_group, include all versions
    _attach_track_version_group(conn, track_id, meta, merge_level, weighted_frame)

    conn.close()
    return meta if meta else None


def _get_track_presentation_fields(track_id: int, merge_level: int) -> dict:
    conn = get_db(readonly=True)
    try:
        presentation = resolve_track_presentation(conn, track_id, merge_level=merge_level)
        return {
            "cover_url": presentation.cover_url,
            "album_attribution": presentation.payload(),
        }
    finally:
        conn.close()


def _classify_recording_kind(track_name: str) -> str | None:
    """Classify a track version's recording type from its name suffix (R30)."""
    import re

    name = track_name.lower()
    # Order matters: more specific patterns first
    if re.search(r"\bremaster(ed)?\b", name):
        return "remastered"
    if re.search(r"\bacoustic\b", name):
        return "acoustic"
    if re.search(r"\blive\b", name):
        return "live"
    if re.search(r"\bremix\b", name):
        return "remix"
    if re.search(r"\binstrumental\b", name):
        return "instrumental"
    if re.search(r"\bradio.?edit\b", name, re.IGNORECASE):
        return "radio_edit"
    if re.search(r"\bdemo\b", name):
        return "demo"
    if re.search(r"\bclean\b", name) or re.search(r"\bexplicit\b", name):
        return "clean_explicit"
    if re.search(r"\bdeluxe\b", name) or re.search(r"\bexpanded\b", name):
        return "deluxe"
    return None


def _attach_track_version_group(
    conn,
    track_id,
    meta,
    merge_level=2,
    weighted_frame: pd.DataFrame | None = None,
):
    """If the track belongs to a track_group, attach version_group to meta.

    merge_level=1: no version group (R31 L1)
    merge_level=2: recording scope only (R31 L2, default)
    merge_level=3: composition scope with parent-child expansion (R31 L3, R6)
    """
    if merge_level <= 1:
        return

    has_l1_members = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='track_group_l1_members'"
    ).fetchone()
    if has_l1_members:
        _attach_l1_track_version_group(conn, track_id, meta, merge_level, weighted_frame)
        return

    if merge_level >= 3:
        # L3: resolve effective group via parent_group_id → composition parent,
        # matching load_track_group_keys() resolution (R6 child-group expansion).
        group_row = conn.execute(
            """SELECT COALESCE(parent_tg.group_id, tg.group_id) AS effective_group_id,
                      COALESCE(parent_tg.canonical_name, tg.canonical_name) AS canonical_name,
                      CASE WHEN parent_tg.group_id IS NOT NULL THEN 'composition'
                           ELSE tg.scope END AS scope,
                      COALESCE(parent_tg.primary_track_id, tg.primary_track_id) AS primary_track_id
               FROM track_group_members tgm
               JOIN track_groups tg ON tgm.group_id = tg.group_id
               LEFT JOIN track_groups parent_tg
                 ON tg.parent_group_id = parent_tg.group_id
                AND parent_tg.scope = 'composition'
               WHERE tgm.track_id = ? AND tg.scope IN ('composition', 'recording')
               LIMIT 1""",
            (track_id,),
        ).fetchone()
    else:
        group_row = conn.execute(
            """SELECT tg.group_id AS effective_group_id, tg.canonical_name, tg.scope,
                      tg.primary_track_id
               FROM track_group_members tgm
               JOIN track_groups tg ON tgm.group_id = tg.group_id
               WHERE tgm.track_id = ? AND tg.scope = 'recording'
               LIMIT 1""",
            (track_id,),
        ).fetchone()

    if not group_row:
        return

    effective_group_id = group_row["effective_group_id"]

    if merge_level >= 3:
        versions = conn.execute(
            """SELECT t.track_id, t.track_name, al.album_name, al.album_id,
                      COUNT(p.play_id) AS plays,
                      COALESCE(SUM(p.ms_played), 0) AS total_ms,
                      sam.album_type, sam.release_date,
                      sam.image_url AS album_cover_url
               FROM track_group_members tgm
               JOIN track_groups tg ON tgm.group_id = tg.group_id
               LEFT JOIN track_groups parent_tg
                 ON tg.parent_group_id = parent_tg.group_id
                AND parent_tg.scope = 'composition'
               JOIN tracks t ON tgm.track_id = t.track_id
               LEFT JOIN albums al ON t.album_id = al.album_id
               LEFT JOIN spotify_album_meta sam ON sam.album_name = al.album_name
               LEFT JOIN plays p ON p.track_id = t.track_id AND p.ms_played >= 30000
               WHERE COALESCE(parent_tg.group_id, tg.group_id) = ?
                 AND tg.scope IN ('composition', 'recording')
               GROUP BY t.track_id
               ORDER BY plays DESC""",
            (effective_group_id,),
        ).fetchall()
    else:
        versions = conn.execute(
            """SELECT t.track_id, t.track_name, al.album_name, al.album_id,
                      COUNT(p.play_id) AS plays,
                      COALESCE(SUM(p.ms_played), 0) AS total_ms,
                      sam.album_type, sam.release_date,
                      sam.image_url AS album_cover_url
               FROM track_group_members tgm
               JOIN tracks t ON tgm.track_id = t.track_id
               LEFT JOIN albums al ON t.album_id = al.album_id
               LEFT JOIN spotify_album_meta sam ON sam.album_name = al.album_name
               LEFT JOIN plays p ON p.track_id = t.track_id AND p.ms_played >= 30000
               WHERE tgm.group_id = ?
               GROUP BY t.track_id
               ORDER BY plays DESC""",
            (effective_group_id,),
        ).fetchall()

    if len(versions) < 2:
        return

    versions = [dict(version) for version in versions]
    if weighted_frame is not None and {"track_id", "play_count", "total_ms"}.issubset(
        weighted_frame.columns
    ):
        version_ids = {int(version["track_id"]) for version in versions}
        scoped = weighted_frame[weighted_frame["track_id"].isin(version_ids)]
        weighted_counts = (
            scoped.groupby("track_id", dropna=False)[["play_count", "total_ms"]]
            .sum()
            .to_dict("index")
            if not scoped.empty
            else {}
        )
        for version in versions:
            counts = weighted_counts.get(int(version["track_id"]), {})
            version["plays"] = int(counts.get("play_count", 0))
            version["total_ms"] = int(counts.get("total_ms", 0))

    total_plays = sum(v["plays"] for v in versions)
    meta["version_group"] = {
        "group_id": effective_group_id,
        "canonical_name": group_row["canonical_name"],
        "scope": group_row["scope"],
        "total_plays": total_plays,
        "versions": [
            {
                "track_id": v["track_id"],
                "track_name": v["track_name"],
                "album_name": v["album_name"],
                "plays": v["plays"],
                "total_ms": v["total_ms"],
                "is_primary": v["track_id"] == group_row["primary_track_id"],
                "recording_kind": _classify_recording_kind(v["track_name"]),
                "album_cover_url": v["album_cover_url"]
                or (f"/covers/albums/{v['album_id']}.jpg" if v["album_id"] else None),
                "release_date": v["release_date"],
            }
            for v in versions
        ],
    }


def _attach_l1_track_version_group(
    conn: sqlite3.Connection,
    l1_id: int,
    meta: dict,
    merge_level: int,
    weighted_frame: pd.DataFrame | None,
) -> None:
    scope_filter = "('composition', 'recording')" if merge_level >= 3 else "('recording')"
    group_row = conn.execute(
        f"""SELECT COALESCE(parent.group_id, groups.group_id) AS effective_group_id,
                   COALESCE(parent.canonical_name, groups.canonical_name) AS canonical_name,
                   CASE WHEN parent.group_id IS NOT NULL THEN 'composition'
                        ELSE groups.scope END AS scope,
                   COALESCE(parent.primary_l1_id, groups.primary_l1_id) AS primary_l1_id
              FROM track_group_l1_members members
              JOIN track_groups groups ON groups.group_id=members.group_id
              LEFT JOIN track_groups parent
                ON groups.parent_group_id=parent.group_id
               AND parent.scope='composition'
               AND parent.group_status='active'
             WHERE members.l1_id=?
               AND groups.group_status='active'
               AND groups.scope IN {scope_filter}
             ORDER BY CASE WHEN parent.group_id IS NOT NULL THEN 0 ELSE 1 END,
                      groups.group_id
             LIMIT 1""",
        (int(l1_id),),
    ).fetchone()
    if group_row is None:
        return
    effective_group_id = int(group_row["effective_group_id"])
    versions = conn.execute(
        """SELECT li.l1_id AS track_id, t.track_name, al.album_name, al.album_id,
                  COUNT(DISTINCT p.play_id) AS plays,
                  COALESCE(SUM(p.ms_played), 0) AS total_ms,
                  sam.album_type, sam.release_date,
                  sam.image_url AS album_cover_url
             FROM track_groups groups
             JOIN track_group_l1_members members ON members.group_id=groups.group_id
             JOIN track_l1_identities li ON li.l1_id=members.l1_id
             JOIN tracks t ON t.track_id=li.representative_track_id
             LEFT JOIN albums al ON al.album_id=t.album_id
             LEFT JOIN spotify_album_meta sam ON sam.album_name=al.album_name
             LEFT JOIN plays p
               ON EXISTS (
                    SELECT 1 FROM track_l1_external_ids external
                     WHERE external.l1_id=li.l1_id
                       AND external.provider='spotify'
                       AND external.external_track_id=COALESCE(
                           NULLIF(p.spotify_track_id_at_play, ''),
                           (SELECT NULLIF(source.spotify_track_id, '')
                              FROM tracks source WHERE source.track_id=p.track_id)
                       )
                  )
               OR (li.fallback_track_id=p.track_id)
            WHERE (groups.group_id=? OR groups.parent_group_id=?)
              AND groups.group_status='active'
              AND groups.scope IN ('composition', 'recording')
            GROUP BY li.l1_id
            ORDER BY plays DESC, li.l1_id""",
        (effective_group_id, effective_group_id),
    ).fetchall()
    if len(versions) < 2:
        return
    versions = [dict(version) for version in versions]
    if weighted_frame is not None and "track_id" in weighted_frame.columns:
        counts = (
            weighted_frame[weighted_frame["track_id"].isin([v["track_id"] for v in versions])]
            .groupby("track_id", dropna=False)[["play_count", "total_ms"]]
            .sum()
            .to_dict("index")
        )
        for version in versions:
            values = counts.get(int(version["track_id"]), {})
            version["plays"] = int(values.get("play_count", 0))
            version["total_ms"] = int(values.get("total_ms", 0))
    meta["version_group"] = {
        "group_id": effective_group_id,
        "canonical_name": group_row["canonical_name"],
        "scope": group_row["scope"],
        "total_plays": sum(int(version["plays"]) for version in versions),
        "versions": [
            {
                "track_id": int(version["track_id"]),
                "l1_id": int(version["track_id"]),
                "track_name": version["track_name"],
                "album_name": version["album_name"],
                "plays": int(version["plays"]),
                "total_ms": int(version["total_ms"]),
                "is_primary": int(version["track_id"]) == int(group_row["primary_l1_id"]),
                "recording_kind": _classify_recording_kind(version["track_name"]),
                "album_cover_url": version["album_cover_url"]
                or (f"/covers/albums/{version['album_id']}.jpg" if version["album_id"] else None),
                "release_date": version["release_date"],
            }
            for version in versions
        ],
    }


def _get_artist_spotify_meta(artist_name):
    """Fetch Spotify metadata for an artist through its canonical identity."""
    conn = get_db()
    try:
        provider = resolve_artist_spotify_meta(conn, artist_name)
        resolved_genres = resolve_artist_genres(conn, artist_name)
    finally:
        conn.close()

    meta = {}
    provider_meta = provider.metadata or {}
    if provider_meta.get("popularity") is not None:
        meta["popularity"] = provider_meta["popularity"]
    if provider_meta.get("followers") is not None:
        meta["followers"] = provider_meta["followers"]
    if provider_meta.get("genres"):
        meta["genres"] = provider_meta["genres"]
        meta["genre_source"] = "spotify"
        meta["genre_confidence"] = 1.0
    elif resolved_genres.genres:
        meta["genres"] = resolved_genres.genres
        meta["genre_source"] = resolved_genres.source
        meta["genre_confidence"] = resolved_genres.confidence
    if provider.has_conflict:
        meta["provider_metadata_conflict"] = {
            "provider": "spotify",
            "external_ids": list(provider.conflict_external_ids),
            "source": provider.source,
        }

    return meta if meta else None


def _get_album_spotify_meta(
    album_name,
    artist_name,
    merge_level=2,
    weighted_frame: pd.DataFrame | None = None,
    album_project_id: int | None = None,
    album_id: int | None = None,
):
    """Fetch Spotify metadata for an album by name + artist."""
    conn = get_db()
    meta = (
        resolve_album_detail_meta(
            conn,
            album_name,
            artist_name,
            merge_level=merge_level,
            album_project_id=album_project_id,
            album_id=album_id,
        )
        or {}
    )

    # Release group: if this album belongs to a release_group, include all versions
    _attach_album_release_group(
        conn,
        album_name,
        artist_name,
        meta,
        merge_level,
        weighted_frame,
    )

    conn.close()
    return meta if meta else None


def _attach_album_release_group(
    conn,
    album_name,
    artist_name,
    meta,
    merge_level=2,
    weighted_frame: pd.DataFrame | None = None,
):
    """If the album belongs to a release_group, attach release_group to meta.

    merge_level=1: no release group (R31 L1)
    merge_level=2: release scope only (R31 L2, default)
    merge_level=3: composition scope with parent-child expansion (R31 L3, R10)
    """
    if merge_level <= 1:
        return

    if merge_level >= 3:
        group_row = conn.execute(
            """SELECT COALESCE(parent_rg.group_id, rg.group_id) AS effective_group_id,
                      COALESCE(parent_rg.canonical_name, rg.canonical_name) AS canonical_name,
                      CASE WHEN parent_rg.group_id IS NOT NULL THEN 'composition'
                           ELSE rg.scope END AS scope,
                      COALESCE(parent_rg.primary_album_id, rg.primary_album_id) AS primary_album_id
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               JOIN albums al ON rgm.album_id = al.album_id
               JOIN artists a ON al.artist_id = a.artist_id
               LEFT JOIN release_groups parent_rg
                 ON rg.parent_group_id = parent_rg.group_id
                AND parent_rg.scope = 'composition'
               WHERE al.album_name = ? AND a.artist_name = ?
                 AND rg.scope IN ('composition', 'release')
               LIMIT 1""",
            (album_name, artist_name),
        ).fetchone()
    else:
        group_row = conn.execute(
            """SELECT rg.group_id AS effective_group_id, rg.canonical_name, rg.scope,
                      rg.primary_album_id
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               JOIN albums al ON rgm.album_id = al.album_id
               JOIN artists a ON al.artist_id = a.artist_id
               WHERE al.album_name = ? AND a.artist_name = ?
                 AND rg.scope = 'release'
               LIMIT 1""",
            (album_name, artist_name),
        ).fetchone()

    if not group_row:
        return

    effective_group_id = group_row["effective_group_id"]

    if merge_level >= 3:
        versions = conn.execute(
            """SELECT al.album_id, al.album_name, ar.artist_name,
                      COUNT(DISTINCT p.track_id) AS unique_tracks,
                      COUNT(p.play_id) AS plays,
                      COALESCE(SUM(p.ms_played), 0) AS total_ms,
                      sam.album_type, sam.release_date, sam.total_tracks,
                      sam.image_url AS album_cover_url
               FROM release_group_members rgm
               JOIN release_groups rg ON rgm.group_id = rg.group_id
               LEFT JOIN release_groups parent_rg
                 ON rg.parent_group_id = parent_rg.group_id
                AND parent_rg.scope = 'composition'
               JOIN albums al ON rgm.album_id = al.album_id
               JOIN artists ar ON al.artist_id = ar.artist_id
               LEFT JOIN spotify_album_meta sam ON sam.album_name = al.album_name
               LEFT JOIN plays p ON p.source_album_id = al.album_id AND p.ms_played >= 30000
               WHERE COALESCE(parent_rg.group_id, rg.group_id) = ?
                 AND rg.scope IN ('composition', 'release')
               GROUP BY al.album_id
               ORDER BY plays DESC""",
            (effective_group_id,),
        ).fetchall()
    else:
        versions = conn.execute(
            """SELECT al.album_id, al.album_name, ar.artist_name,
                      COUNT(DISTINCT p.track_id) AS unique_tracks,
                      COUNT(p.play_id) AS plays,
                      COALESCE(SUM(p.ms_played), 0) AS total_ms,
                      sam.album_type, sam.release_date, sam.total_tracks,
                      sam.image_url AS album_cover_url
               FROM release_group_members rgm
               JOIN albums al ON rgm.album_id = al.album_id
               JOIN artists ar ON al.artist_id = ar.artist_id
               LEFT JOIN spotify_album_meta sam ON sam.album_name = al.album_name
               LEFT JOIN plays p ON p.source_album_id = al.album_id AND p.ms_played >= 30000
               WHERE rgm.group_id = ?
               GROUP BY al.album_id
               ORDER BY plays DESC""",
            (effective_group_id,),
        ).fetchall()

    if len(versions) < 2:
        return

    versions = [dict(version) for version in versions]
    if weighted_frame is not None and {"source_album_id", "play_count", "total_ms"}.issubset(
        weighted_frame.columns
    ):
        album_id_set = {int(version["album_id"]) for version in versions}
        scoped = weighted_frame.copy()
        scoped["_detail_album_id"] = pd.to_numeric(scoped["source_album_id"], errors="coerce")
        scoped = scoped[scoped["_detail_album_id"].isin(album_id_set)]
        weighted_counts = (
            scoped.groupby("_detail_album_id", dropna=False)[["play_count", "total_ms"]]
            .sum()
            .to_dict("index")
            if not scoped.empty
            else {}
        )
        for version in versions:
            counts = weighted_counts.get(float(version["album_id"]), {})
            if not counts:
                counts = weighted_counts.get(int(version["album_id"]), {})
            version["plays"] = int(counts.get("play_count", 0))
            version["total_ms"] = int(counts.get("total_ms", 0))

    # Track coverage matrix: which tracks appear in which version (R30.3/R30.4)
    album_ids = [v["album_id"] for v in versions]
    placeholders = ",".join("?" for _ in album_ids)
    track_rows = conn.execute(
        f"""SELECT ta.album_id, t.track_id, t.track_name
            FROM track_albums ta
            JOIN tracks t ON ta.track_id = t.track_id
            WHERE ta.album_id IN ({placeholders})
            ORDER BY t.track_name""",
        [int(aid) for aid in album_ids],
    ).fetchall()

    # Build track → set of album_ids for coverage computation
    track_albums_map: dict[int, set[int]] = {}
    track_id_to_name: dict[int, str] = {}
    for tr in track_rows:
        tid = tr["track_id"]
        track_id_to_name[tid] = tr["track_name"]
        track_albums_map.setdefault(tid, set()).add(tr["album_id"])

    # Coverage matrix: each row = one track, columns = per-version presence
    track_coverage = []
    for tid, albums in sorted(track_albums_map.items(), key=lambda x: x[0]):
        track_coverage.append(
            {
                "track_id": tid,
                "track_name": track_id_to_name[tid],
                "album_ids": sorted(albums),
                "is_exclusive": len(albums) == 1,
            }
        )

    total_plays = sum(v["plays"] for v in versions)
    meta["release_group"] = {
        "group_id": effective_group_id,
        "canonical_name": group_row["canonical_name"],
        "scope": group_row["scope"],
        "total_plays": total_plays,
        "versions": [
            {
                "album_id": v["album_id"],
                "album_name": v["album_name"],
                "artist_name": v["artist_name"],
                "plays": v["plays"],
                "unique_tracks": v["unique_tracks"],
                "total_ms": v["total_ms"],
                "is_primary": v["album_id"] == group_row["primary_album_id"],
                "album_cover_url": v["album_cover_url"] or f"/covers/albums/{v['album_id']}.jpg",
                "release_date": v["release_date"],
                "album_type": v["album_type"],
                "total_tracks": v["total_tracks"],
            }
            for v in versions
        ],
        "track_coverage": track_coverage,
    }


def _enrich_source_breakdown(conn: sqlite3.Connection, df: pd.DataFrame) -> pd.DataFrame:
    """Add album_cover_url, release_date, track_count to source breakdown rows."""
    if df.empty:
        return df

    album_ids = [int(i) for i in df["source_album_id"].dropna().unique().tolist()]
    if not album_ids:
        return df

    placeholders = ",".join("?" for _ in album_ids)
    meta_rows = conn.execute(
        f"""SELECT a.album_id,
                  a.album_name,
                  ar.artist_name,
                  sam.release_date,
                  (SELECT COUNT(*) FROM track_albums ta
                   WHERE ta.album_id = a.album_id) AS track_count
           FROM albums a
           LEFT JOIN artists ar ON ar.artist_id = a.artist_id
           LEFT JOIN spotify_album_meta sam
             ON sam.spotify_album_id = (
               SELECT stm.spotify_album_id FROM spotify_track_meta stm
               JOIN tracks t ON t.spotify_track_id = stm.spotify_track_id
               JOIN track_albums ta ON ta.track_id = t.track_id
               WHERE ta.album_id = a.album_id
               LIMIT 1
             )
           WHERE a.album_id IN ({placeholders})""",
        album_ids,
    ).fetchall()

    meta_by_id: dict[int, dict] = {}
    for r in meta_rows:
        meta_by_id[r["album_id"]] = {
            "release_date": r["release_date"],
            "track_count": r["track_count"] or 0,
            "album_name": r["album_name"],
            "artist_name": r["artist_name"],
        }

    from backend.services.play_service import _album_cover_lookup

    cover_map = _album_cover_lookup(conn)

    def enrich_row(row):
        aid = row.get("source_album_id")
        meta = meta_by_id.get(int(aid)) if aid is not None and pd.notna(aid) else None
        if meta:
            row["album_cover_url"] = cover_map.get((meta["album_name"], meta["artist_name"]))
            row["release_date"] = meta["release_date"] or row.get("release_date")
            row["track_count"] = meta["track_count"]
        else:
            row["album_cover_url"] = None
            row["track_count"] = 0
        return row

    return df.apply(enrich_row, axis=1)


def _get_album_project_payload(
    album_name: str,
    artist_name: str,
    df: pd.DataFrame,
    merge_level: int,
) -> dict | None:
    """Build the album-project explanation payload for album details."""
    if merge_level <= 1 or df.empty:
        return None

    from backend.domains.playback.album_projects import (
        SOURCE_BUCKET_ORDER,
        compute_album_project_plays,
        compute_album_source_breakdown,
        ensure_album_projects,
        load_album_project_membership,
    )

    conn = get_db()
    try:
        ensure_album_projects(conn)
        totals = compute_album_project_plays(
            df,
            conn,
            merge_level=merge_level,
            include_compilations=True,
        )
        if totals.empty:
            return None

        match = totals[
            (totals["album_project_name"] == album_name) & (totals["artist_name"] == artist_name)
        ]
        if match.empty:
            project_ids = _resolve_album_project_ids(conn, album_name, artist_name)
            if project_ids:
                match = totals[totals["album_project_id"].isin(project_ids)]
        if match.empty:
            return None

        match = match.sort_values(["play_count", "total_ms"], ascending=[False, False])
        row = match.iloc[0]
        project_id = int(row["album_project_id"])

        membership = load_album_project_membership(
            conn,
            merge_level=merge_level,
            include_compilations=True,
        )
        project_tracks = membership[membership["project_id"] == project_id].copy()
        if not project_tracks.empty:
            project_tracks["_bucket_rank"] = (
                project_tracks["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
            )
            project_tracks = project_tracks.sort_values(
                ["_bucket_rank", "track_id"], ascending=[True, True]
            ).drop(columns=["_bucket_rank"])

        breakdown = compute_album_source_breakdown(df, conn, merge_level=merge_level)
        project_breakdown = breakdown[breakdown["album_project_id"] == project_id].copy()
        if not project_breakdown.empty:
            project_breakdown = _enrich_source_breakdown(conn, project_breakdown)
            project_breakdown["_bucket_rank"] = (
                project_breakdown["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
            )
            project_breakdown = project_breakdown.sort_values(
                ["_bucket_rank", "source_album_name"], ascending=[True, True]
            ).drop(columns=["_bucket_rank"])

        return {
            "album_project_id": project_id,
            "album_project_name": str(row["album_project_name"]),
            "artist_name": str(row["artist_name"]),
            "release_date": str(row.get("release_date") or ""),
            "play_count": int(row["play_count"]),
            "total_ms": int(row["total_ms"]),
            "unique_canonical_songs": int(row["unique_canonical_songs"]),
            "tracks": df_to_json(project_tracks),
            "source_breakdown": df_to_json(project_breakdown),
        }
    finally:
        conn.close()


def _resolve_album_project_ids(
    conn,
    album_name: str,
    artist_name: str,
) -> set[int]:
    from backend.domains.metadata.artist_identity import (
        get_artist_identity_map,
        resolve_artist_name,
    )

    identity = resolve_artist_name(conn, artist_name)
    if identity is None:
        group = conn.execute(
            """SELECT canonical_artist_id FROM artist_identity_groups
               WHERE status='active' AND lower(display_name)=lower(?)
               ORDER BY identity_id LIMIT 1""",
            (artist_name,),
        ).fetchone()
        canonical_artist_id = int(group[0]) if group else None
    else:
        canonical_artist_id = identity.canonical_artist_id
    artist_ids: set[int] = set()
    if canonical_artist_id is not None:
        artist_ids = {
            raw_id
            for raw_id, resolved in get_artist_identity_map(conn).items()
            if resolved.canonical_artist_id == canonical_artist_id
        }
    if not artist_ids:
        rows = conn.execute(
            "SELECT artist_id FROM artists WHERE lower(artist_name)=lower(?)",
            (artist_name,),
        ).fetchall()
        artist_ids = {int(row[0]) for row in rows}
    if not artist_ids:
        return set()
    placeholders = ",".join("?" for _ in artist_ids)
    rows = conn.execute(
        f"""SELECT DISTINCT ap.project_id
           FROM album_projects ap
           JOIN album_project_albums apa ON apa.project_id = ap.project_id
           JOIN albums al ON al.album_id = apa.album_id
          WHERE al.album_name = ?
            AND al.artist_id IN ({placeholders})""",
        (album_name, *sorted(artist_ids)),
    ).fetchall()
    return {int(row["project_id"]) for row in rows}


def _load_album_project_detail_events(
    min_ms,
    music_only,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_enabled=True,
) -> pd.DataFrame:
    from backend.domains.billboard.data_loader import _try_load_from_agg, load_billboard_raw

    _, album_sources, _ = _try_load_from_agg(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )
    if album_sources is not None and "track_id" in album_sources.columns:
        df = album_sources.copy()
    else:
        df = load_billboard_raw(
            min_ms,
            music_only,
            bb_week_start_dow,
            bb_week_start_hour,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_enabled=merge_enabled,
        )
    if df.empty:
        return df
    out = df.copy()
    out["_year"] = out["billboard_week"].apply(lambda x: x.year)
    if year_start is not None:
        out = out[out["_year"] >= year_start]
    if year_end is not None:
        out = out[out["_year"] <= year_end]
    return out


def get_track_history(
    track_id,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_enabled=True,
    merge_level=2,
    include_compilations=False,
):
    """Get detailed track chart history with change column and gapped chart data."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
        merge_enabled=merge_enabled,
    )
    weekly = pd.DataFrame(data["weekly"])
    track_summary = pd.DataFrame(data["track_summary"])
    power_scores = pd.DataFrame(data["power_scores"])
    detail_weighted_frame = _load_detail_weighted_frame(
        min_ms=min_ms,
        music_only=music_only,
        week_start_dow=bb_week_start_dow,
        week_start_hour=bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )

    track_hist = weekly[weekly["track_id"] == track_id]
    if track_hist.empty:
        stats = _load_detail_access_stats(
            "track",
            track_id=track_id,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_level=merge_level,
        )
        if not stats.get("found"):
            return {"found": False, "meta": None}
        entity = stats["entity"]
        presentation_fields = _get_track_presentation_fields(track_id, merge_level)
        return {
            "found": True,
            "chart_status": "not_charted",
            "effective_play_count": _effective_play_count(stats),
            "track_id": int(entity["track_id"]),
            **_track_identity_fields(int(entity["track_id"])),
            "track_name": str(entity["track_name"]),
            "artist_name": str(entity["artist_name"]),
            "artist_names": list(entity.get("artist_names") or [entity["artist_name"]]),
            "primary_artist_name": _track_primary_artist_name(
                int(entity["track_id"]), str(entity["artist_name"])
            ),
            "cover_url": presentation_fields["cover_url"] or entity.get("cover_url"),
            "album_attribution": presentation_fields["album_attribution"],
            "meta": _get_track_spotify_meta(track_id, merge_level, detail_weighted_frame),
            "summary": None,
            "history": [],
            "chart_data": {"x": [], "y": [], "texts": [], "top_n": bb_top_n},
        }

    track_hist = track_hist.sort_values("billboard_week")
    ts_row = track_summary[track_summary["track_id"] == track_id]
    info = ts_row.iloc[0].to_dict() if not ts_row.empty else {}

    tp = power_scores[power_scores["track_id"] == track_id]
    power_score = int(tp.iloc[0]["power_score"]) if not tp.empty else 0
    power_scores_sorted = power_scores.sort_values("power_score", ascending=False).reset_index(
        drop=True
    )
    power_rank = (
        int(power_scores_sorted[power_scores_sorted["track_id"] == track_id].index[0]) + 1
        if not tp.empty
        else None
    )

    # Change column
    hist_with_change = _compute_change_column(track_hist)

    # Gapped chart data
    x_vals, y_vals, texts = _build_gapped_chart_data(track_hist)

    cover_url = track_hist.iloc[0].get("cover_url") if "cover_url" in track_hist.columns else None

    primary_artist = str(track_hist.iloc[0]["artist_name"])
    all_artists = get_track_artist_names_map()
    artist_names = all_artists.get(track_id, [primary_artist])
    display_artist = ", ".join(artist_names) if len(artist_names) > 1 else primary_artist

    presentation_fields = _get_track_presentation_fields(track_id, merge_level)
    return {
        "found": True,
        "chart_status": "charted",
        "track_id": track_id,
        **_track_identity_fields(int(track_id)),
        "track_name": str(track_hist.iloc[0]["track_name"]),
        "artist_name": display_artist,
        "artist_names": artist_names,
        "primary_artist_name": _track_primary_artist_name(track_id, primary_artist),
        "cover_url": presentation_fields["cover_url"]
        or (cover_url if pd.notna(cover_url) else None),
        "album_attribution": presentation_fields["album_attribution"],
        "meta": _get_track_spotify_meta(track_id, merge_level, detail_weighted_frame),
        "summary": {
            "peak_position": int(info.get("peak_position", 0)),
            "weeks_on_chart": int(info.get("weeks_on_chart", 0)),
            "weeks_at_peak": int(info.get("weeks_at_peak", 0)),
            "first_week": str(info.get("first_week", "")),
            "last_week": str(info.get("last_week", "")),
            "first_peak_week": str(info.get("first_peak_week", ""))
            if pd.notna(info.get("first_peak_week"))
            else None,
            "total_chart_plays": int(info.get("total_chart_plays", 0)),
            "total_plays": int(info.get("total_plays", 0)),
            "weeks_at_no1": int(info.get("weeks_at_no1", 0)),
            "power_score": power_score,
            "power_rank": power_rank,
        },
        "history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in hist_with_change.iterrows()
        ],
        "chart_data": {
            "x": x_vals,
            "y": y_vals,
            "texts": texts,
            "top_n": bb_top_n,
            "peak_position": int(info.get("peak_position", 0)),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Artist Chart Detail
# ═══════════════════════════════════════════════════════════════════════════


def get_artist_chart_detail(
    artist_name,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_enabled=True,
    merge_level=2,
    include_compilations=False,
):
    """Get detailed artist chart data: history, track/album performances, trend."""
    identity_conn = get_db()
    try:
        from backend.domains.metadata.artist_identity import resolve_artist_name

        identity = resolve_artist_name(identity_conn, artist_name)
        if identity is not None:
            artist_name = identity.display_name
    finally:
        identity_conn.close()
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
        merge_enabled=merge_enabled,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_artist = pd.DataFrame(data["weekly_artist"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    artist_track_counts = pd.DataFrame(data["artist_track_counts"])
    artist_summary = pd.DataFrame(data["artist_summary"])
    track_summary = pd.DataFrame(data["track_summary"])
    power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])
    artist_power_scores = pd.DataFrame(data["artist_power_scores"])

    # Resolve the three artist score families independently.  Artist-chart,
    # track-chart and album-chart facts may exist in any combination.
    weekly_fanned = fan_out_weekly_for_artists(weekly)
    artist_chart_data = weekly_artist[weekly_artist["artist_name"] == artist_name]
    artist_weekly = weekly_fanned[weekly_fanned["artist_name"] == artist_name]
    artist_albums_all = weekly_album[weekly_album["artist_name"] == artist_name]
    art_rows = artist_track_counts[artist_track_counts["artist_name"] == artist_name]
    art_row = art_rows.iloc[0] if not art_rows.empty else None
    if (
        art_row is None
        and artist_chart_data.empty
        and artist_weekly.empty
        and artist_albums_all.empty
    ):
        stats = _load_detail_access_stats(
            "artist",
            artist_name=artist_name,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_level=merge_level,
        )
        if not stats.get("found"):
            return {"found": False, "meta": None}
        entity = stats["entity"]
        canonical_name = str(entity["artist_name"])
        return {
            "found": True,
            "chart_status": "not_charted",
            "track_chart_status": "not_charted",
            "album_chart_status": "not_charted",
            "effective_play_count": _effective_play_count(stats),
            "artist_name": canonical_name,
            "cover_url": entity.get("cover_url"),
            "meta": _get_artist_spotify_meta(canonical_name),
            "info": None,
            "chart_summary": None,
            "artist_weekly_history": [],
            "artist_no1_by_week": [],
            "week_no1_albums": [],
            "best_singles_overlay": [],
            "best_albums_overlay": [],
            "tracks": [],
            "albums": [],
        }

    # Artist power score/rank
    aps_sorted = artist_power_scores.sort_values("power_score", ascending=False).reset_index(
        drop=True
    )
    ap_row = aps_sorted[aps_sorted["artist_name"] == artist_name]
    artist_power_score = int(ap_row.iloc[0]["power_score"]) if not ap_row.empty else 0
    artist_power_rank = int(ap_row.iloc[0].name) + 1 if not ap_row.empty else None
    artist_power_metrics = ap_row.iloc[0] if not ap_row.empty else None

    def _optional_int(row, column):
        if row is None or column not in row.index or pd.isna(row[column]):
            return None
        return int(row[column])

    # Track power scores for this artist — match by track_id from fanned summary
    artist_track_ids = set(artist_summary[artist_summary["artist_name"] == artist_name]["track_id"])
    track_power = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    track_power["power_rank"] = track_power.index + 1
    artist_track_power = track_power[track_power["track_id"].isin(artist_track_ids)]

    # Album power scores for this artist
    album_power = album_power_scores.sort_values("power_score", ascending=False).reset_index(
        drop=True
    )
    album_power["power_rank"] = album_power.index + 1
    artist_album_power = album_power[album_power["artist_name"] == artist_name]

    # Charting tracks with power scores
    art_tracks = artist_summary[artist_summary["artist_name"] == artist_name].copy()
    art_tracks = art_tracks.merge(
        track_summary[["track_id", "weeks_at_no1", "first_peak_week"]], on="track_id", how="left"
    )
    art_tracks["weeks_at_no1"] = art_tracks["weeks_at_no1"].fillna(0).astype(int)
    art_tracks = art_tracks.merge(
        artist_track_power[["track_id", "power_score", "power_rank"]], on="track_id", how="left"
    )
    art_tracks["power_score"] = art_tracks["power_score"].fillna(0).astype(int)
    art_tracks["power_rank"] = art_tracks["power_rank"].fillna(0).astype(int)
    art_tracks = _stable_detail_track_sort(
        art_tracks,
        primary_columns=("peak_position", "weeks_on_chart"),
        primary_ascending=(True, False),
    ).drop_duplicates("track_id")

    # Track cover_url lookup
    track_cover_map = {}
    if "cover_url" in weekly.columns:
        for _, r in weekly[["track_id", "cover_url"]].drop_duplicates("track_id").iterrows():
            if pd.notna(r["cover_url"]):
                track_cover_map[int(r["track_id"])] = r["cover_url"]

    detail_track_ids = [int(value) for value in art_tracks.get("track_id", [])]
    detail_artist_names: dict[int, list[str]] = {}
    if detail_track_ids:
        from backend.domains.metadata.track_credits import (
            canonical_artist_names_for_effective_tracks,
        )

        credit_conn = get_db()
        try:
            detail_artist_names = canonical_artist_names_for_effective_tracks(
                credit_conn, detail_track_ids
            )
        finally:
            credit_conn.close()

    # Best singles rank per week (for overlay chart)
    best_singles_idx = artist_weekly.groupby("billboard_week")["rank"].idxmin()
    best_singles = artist_weekly.loc[
        best_singles_idx, ["billboard_week", "rank", "track_name"]
    ].sort_values("billboard_week")

    # Best albums rank per week (for overlay chart)
    artist_albums_weekly = weekly_album[weekly_album["artist_name"] == artist_name]
    best_albums_idx = artist_albums_weekly.groupby("billboard_week")["rank"].idxmin()
    best_albums = (
        (
            artist_albums_weekly.loc[
                best_albums_idx, ["billboard_week", "rank", "album_name"]
            ].sort_values("billboard_week")
        )
        if not artist_albums_weekly.empty
        else pd.DataFrame()
    )

    # Artist weekly history with change column and #1 info
    artist_no1 = (
        artist_weekly[artist_weekly["rank"] == 1]
        .groupby("billboard_week")
        .agg(
            no1_track_names=("track_name", lambda x: "、".join(dict.fromkeys(x))),
            no1_track_id=("track_id", "first"),
            no1_count=("track_id", "nunique"),
        )
        .reset_index()
    )

    # #1 album per week
    week_no1_albums = weekly_album[weekly_album["rank"] == 1][
        ["billboard_week", "album_name", "artist_name"]
    ].copy()

    artist_wk_history = (
        _compute_change_column(artist_chart_data) if not artist_chart_data.empty else pd.DataFrame()
    )

    # Artist chart summary
    chart_summary = {}
    if not artist_chart_data.empty:
        art_peak = int(artist_chart_data["rank"].min())
        chart_summary = {
            "peak_position": art_peak,
            "weeks_on_chart": int(artist_chart_data["billboard_week"].nunique()),
            "first_week": str(artist_chart_data["billboard_week"].min()),
            "first_peak_week": str(
                artist_chart_data.loc[artist_chart_data["rank"] == art_peak, "billboard_week"].min()
            ),
            "latest_week": str(artist_chart_data["billboard_week"].max()),
            "no1_weeks": int((artist_chart_data["rank"] == 1).sum()),
            "peak_weeks": int((artist_chart_data["rank"] == art_peak).sum()),
            "power_score": artist_power_score,
            "power_rank": artist_power_rank,
        }

    # Album chart performance summary
    album_perf = []
    album_total_weeks = 0
    album_top5 = 0
    album_count = 0
    if not artist_albums_all.empty:
        album_summary = (
            artist_albums_all.groupby("album_name")
            .agg(
                peak=("rank", "min"),
                pk_wks=("rank", lambda x: (x == x.min()).sum()),
                weeks=("billboard_week", "nunique"),
                first_week=("billboard_week", "min"),
                last_week=("billboard_week", "max"),
                total_plays=("play_count", "sum"),
            )
            .reset_index()
            .sort_values(["peak", "pk_wks", "weeks"], ascending=[True, False, False])
        )
        album_count = int(len(album_summary))
        album_total_weeks = int(album_summary["weeks"].sum())
        album_top5 = int((album_summary["peak"] <= 5).sum())
        album_summary = album_summary.merge(
            artist_album_power[["album_name", "power_score", "power_rank"]],
            on="album_name",
            how="left",
        )
        album_summary["power_score"] = album_summary["power_score"].fillna(0).astype(int)
        album_summary["power_rank"] = album_summary["power_rank"].fillna(0).astype(int)

        # Album cover_url + first_peak_week lookup
        album_cover_map = {}
        album_peak_map = {}
        if "cover_url" in weekly_album.columns:
            for _, r in weekly_album[weekly_album["artist_name"] == artist_name][
                ["album_name", "cover_url", "rank"]
            ].iterrows():
                aname = r["album_name"]
                if aname not in album_cover_map and pd.notna(r["cover_url"]):
                    album_cover_map[aname] = r["cover_url"]
                # Track first week this album hit its peak
                if aname not in album_peak_map:
                    album_peak_map[aname] = r

        album_perf = [
            {
                "album_name": r["album_name"],
                "peak": int(r["peak"]),
                "weeks": int(r["weeks"]),
                "pk_wks": int(r["pk_wks"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(
                    artist_albums_all[
                        (artist_albums_all["album_name"] == r["album_name"])
                        & (artist_albums_all["rank"] == int(r["peak"]))
                    ]["billboard_week"].min()
                ),
                "last_week": str(r["last_week"]),
                "total_plays": int(r["total_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": album_cover_map.get(r["album_name"]),
            }
            for _, r in album_summary.iterrows()
        ]

    # Detail access and the hero's effective-play total use the personal-play
    # pipeline, regardless of whether the artist also qualifies for the chart.
    # Loading this only for uncharted artists made charted detail responses
    # incorrectly report ``effective_play_count=0``.
    access_stats = _load_detail_access_stats(
        "artist",
        artist_name=artist_name,
        min_ms=min_ms,
        music_only=music_only,
        merge_enabled=merge_enabled,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
    )

    # Artist cover URL from weekly_artist data, falling back to personal facts
    artist_cover_url = None
    if not artist_chart_data.empty and "cover_url" in artist_chart_data.columns:
        first_cover = artist_chart_data.iloc[0].get("cover_url")
        if pd.notna(first_cover):
            artist_cover_url = first_cover
    if artist_cover_url is None and access_stats and access_stats.get("found"):
        artist_cover_url = (access_stats.get("entity") or {}).get("cover_url")

    return {
        "found": True,
        "chart_status": "charted" if not artist_chart_data.empty else "not_charted",
        "track_chart_status": "charted" if not art_tracks.empty else "not_charted",
        "album_chart_status": "charted" if album_perf else "not_charted",
        "effective_play_count": _effective_play_count(access_stats or {}),
        "artist_name": artist_name,
        "cover_url": artist_cover_url,
        "meta": _get_artist_spotify_meta(artist_name),
        "info": {
            "total_tracks": int(art_row["total_tracks"]) if art_row is not None else 0,
            "best_peak": int(art_row["best_peak"]) if art_row is not None else 0,
            "total_weeks": int(art_row["total_weeks"]) if art_row is not None else 0,
            "avg_weeks": round(float(art_row["avg_weeks"]), 1) if art_row is not None else 0.0,
            "top1": int(art_row["top1"]) if art_row is not None else 0,
            "top5": int(art_row["top5"]) if art_row is not None else 0,
            "top10": int(art_row["top10"]) if art_row is not None else 0,
            "weeks_at_no1": int(art_row["weeks_at_no1"]) if art_row is not None else 0,
            "num_no1_albums": int(
                artist_albums_all.loc[artist_albums_all["rank"] == 1, "album_name"].nunique()
            ),
            "total_albums": album_count,
            "album_top5": album_top5,
            "album_no1_weeks": int(
                artist_albums_all.loc[artist_albums_all["rank"] == 1, "billboard_week"].nunique()
            ),
            "total_album_weeks": album_total_weeks,
            "total_track_power": int(artist_track_power["power_score"].sum()),
            "total_album_power": int(artist_album_power["power_score"].sum()),
            "track_power_rank": _optional_int(artist_power_metrics, "track_power_rank"),
            "album_power_rank": _optional_int(artist_power_metrics, "album_power_rank"),
        },
        "chart_summary": chart_summary or None,
        "artist_weekly_history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "tracks_count": int(r.get("tracks_count", 0)),
                "albums_count": int(r.get("albums_count", 0)),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in artist_wk_history.iterrows()
        ]
        if not artist_wk_history.empty
        else [],
        "artist_no1_by_week": [
            {
                "week": str(r["billboard_week"]),
                "no1_track_names": r["no1_track_names"],
                "no1_track_id": int(r["no1_track_id"]) if pd.notna(r.get("no1_track_id")) else None,
                "no1_count": int(r["no1_count"]),
            }
            for _, r in artist_no1.iterrows()
        ],
        "week_no1_albums": [
            {
                "week": str(r["billboard_week"]),
                "album_name": r["album_name"],
                "artist_name": r["artist_name"],
            }
            for _, r in week_no1_albums.iterrows()
        ],
        "best_singles_overlay": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "track_name": r["track_name"],
            }
            for _, r in best_singles.iterrows()
        ]
        if not best_singles.empty
        else [],
        "best_albums_overlay": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "album_name": r["album_name"],
            }
            for _, r in best_albums.iterrows()
        ]
        if not best_albums.empty
        else [],
        "tracks": [
            {
                "track_id": r["track_id"],
                "track_name": r["track_name"],
                "artist_names": detail_artist_names.get(int(r["track_id"]), [artist_name]),
                "peak_position": int(r["peak_position"]),
                "weeks_on_chart": int(r["weeks_on_chart"]),
                "weeks_at_peak": int(r["weeks_at_peak"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(r.get("first_peak_week", "")),
                "last_week": str(r["last_week"]),
                "total_chart_plays": int(r["total_chart_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": track_cover_map.get(int(r["track_id"])),
            }
            for _, r in art_tracks.iterrows()
        ],
        "albums": album_perf,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Album Chart Detail
# ═══════════════════════════════════════════════════════════════════════════


def get_album_chart_detail(
    album_name,
    artist_name,
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_enabled=True,
    merge_level=2,
    include_compilations=False,
):
    """Get detailed album chart data: history, track performances, trend."""
    data = compute_billboard_data(
        min_ms,
        music_only,
        bb_top_n,
        bb_album_top_n,
        bb_artist_top_n,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        merge_level=merge_level,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        include_compilations=include_compilations,
        merge_enabled=merge_enabled,
    )
    weekly = pd.DataFrame(data["weekly"])
    weekly_album = pd.DataFrame(data["weekly_album"])
    album_track_counts = pd.DataFrame(data["album_track_counts"])
    track_per_album = pd.DataFrame(data["track_per_album"])
    power_scores = pd.DataFrame(data["power_scores"])
    album_power_scores = pd.DataFrame(data["album_power_scores"])

    # Resolve the album-chart identity independently from charting singles. An
    # album can enter the album Top N through distributed project plays even if
    # none of its member tracks enters the track Top N.
    album_mask = weekly_album["album_name"] == album_name
    if artist_name:
        album_mask &= weekly_album["artist_name"] == artist_name
    album_chart_data = weekly_album[album_mask]
    if album_chart_data.empty and artist_name and "album_project_id" in weekly_album.columns:
        conn = get_db(readonly=True)
        try:
            project_ids = _resolve_album_project_ids(conn, album_name, artist_name)
        finally:
            conn.close()
        if project_ids:
            album_chart_data = weekly_album[weekly_album["album_project_id"].isin(project_ids)]

    stats = {}
    if not artist_name:
        stats = _load_detail_access_stats(
            "album",
            album_name=album_name,
            artist_name=artist_name or None,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_level=merge_level,
        )
        if stats.get("found") and not album_chart_data.empty:
            stats_artist = str(stats["entity"]["artist_name"])
            album_chart_data = album_chart_data[album_chart_data["artist_name"] == stats_artist]
    if album_chart_data.empty and not stats.get("found"):
        stats = _load_detail_access_stats(
            "album",
            album_name=album_name,
            artist_name=artist_name or None,
            min_ms=min_ms,
            music_only=music_only,
            merge_enabled=merge_enabled,
            dynamic_threshold=dynamic_threshold,
            max_merge_gap_minutes=max_merge_gap_minutes,
            merge_level=merge_level,
        )

    if not album_chart_data.empty:
        identity_row = album_chart_data.sort_values(
            ["play_count", "total_ms"], ascending=[False, False]
        ).iloc[0]
        resolved_album = str(identity_row["album_name"])
        resolved_artist = str(identity_row["artist_name"])
    elif stats.get("found"):
        entity = stats["entity"]
        resolved_album = str(entity["album_name"])
        resolved_artist = str(entity["artist_name"])
    else:
        return {"found": False, "meta": None}

    mask = album_track_counts["album_name"] == resolved_album
    if resolved_artist:
        mask &= album_track_counts["artist_name"] == resolved_artist
    alb_rows = album_track_counts[mask]
    alb_row = (
        alb_rows.sort_values("total_tracks", ascending=False).iloc[0]
        if not alb_rows.empty
        else None
    )

    # Album power score/rank
    aps_sorted = album_power_scores.sort_values("power_score", ascending=False).reset_index(
        drop=True
    )
    ap_row = aps_sorted[
        (aps_sorted["album_name"] == resolved_album)
        & (aps_sorted["artist_name"] == resolved_artist)
    ]
    album_power_score = int(ap_row.iloc[0]["power_score"]) if not ap_row.empty else 0
    album_power_rank = int(ap_row.iloc[0].name) + 1 if not ap_row.empty else None
    album_power_metrics = ap_row.iloc[0] if not ap_row.empty else None

    # Album's charting tracks
    alb_track_ids = set(
        track_per_album[
            (track_per_album["album_name"] == resolved_album)
            & (track_per_album["artist_name"] == resolved_artist)
        ]["track_id"].tolist()
    )
    track_power = power_scores.sort_values("power_score", ascending=False).reset_index(drop=True)
    track_power["power_rank"] = track_power.index + 1
    album_track_power = track_power[track_power["track_id"].isin(alb_track_ids)]

    alb_tracks = track_per_album[
        (track_per_album["album_name"] == resolved_album)
        & (track_per_album["artist_name"] == resolved_artist)
    ].copy()
    alb_tracks = alb_tracks.merge(
        album_track_power[["track_id", "power_score", "power_rank"]], on="track_id", how="left"
    )
    alb_tracks["power_score"] = alb_tracks["power_score"].fillna(0).astype(int)
    alb_tracks["power_rank"] = alb_tracks["power_rank"].fillna(0).astype(int)
    alb_tracks = _stable_detail_track_sort(
        alb_tracks,
        primary_columns=("peak_position", "weeks_on_chart"),
        primary_ascending=(True, False),
    )

    # Track cover_url lookup
    album_track_cover_map = {}
    if "cover_url" in weekly.columns:
        for _, r in weekly[["track_id", "cover_url"]].drop_duplicates("track_id").iterrows():
            if pd.notna(r["cover_url"]):
                album_track_cover_map[int(r["track_id"])] = r["cover_url"]

    # Singles weekly for this album (for overlay chart)
    album_weekly = weekly[weekly["track_id"].isin(alb_track_ids)]
    best_singles_idx = album_weekly.groupby("billboard_week")["rank"].idxmin()
    best_singles = album_weekly.loc[
        best_singles_idx, ["billboard_week", "rank", "track_name"]
    ].sort_values("billboard_week")

    # #1 track info per week
    album_no1 = (
        album_weekly[album_weekly["rank"] == 1]
        .groupby("billboard_week")
        .agg(
            no1_track_names=("track_name", lambda x: "、".join(dict.fromkeys(x))),
            no1_track_id=("track_id", "first"),
            no1_count=("track_id", "nunique"),
        )
        .reset_index()
    )

    # Album weekly history with change column
    album_wk_history = (
        _compute_change_column(album_chart_data) if not album_chart_data.empty else pd.DataFrame()
    )

    # Chart summary
    chart_summary = {}
    if not album_chart_data.empty:
        alb_peak = int(album_chart_data["rank"].min())
        chart_summary = {
            "peak_position": alb_peak,
            "weeks_on_chart": int(album_chart_data["billboard_week"].nunique()),
            "first_week": str(album_chart_data["billboard_week"].min()),
            "first_peak_week": str(
                album_chart_data.loc[album_chart_data["rank"] == alb_peak, "billboard_week"].min()
            ),
            "latest_week": str(album_chart_data["billboard_week"].max()),
            "no1_weeks": int((album_chart_data["rank"] == 1).sum()),
            "peak_weeks": int((album_chart_data["rank"] == alb_peak).sum()),
            "power_score": album_power_score,
            "power_rank": album_power_rank,
        }

    # Album cover URL from weekly_album data, falling back to personal facts
    album_cover_url = None
    if not album_chart_data.empty and "cover_url" in album_chart_data.columns:
        first_cover = album_chart_data.iloc[0].get("cover_url")
        if pd.notna(first_cover):
            album_cover_url = first_cover
    if album_cover_url is None and stats.get("found"):
        album_cover_url = (stats.get("entity") or {}).get("cover_url")

    album_project_events = _load_album_project_detail_events(
        min_ms,
        music_only,
        bb_week_start_dow,
        bb_week_start_hour,
        year_start,
        year_end,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )
    album_project = _get_album_project_payload(
        resolved_album,
        resolved_artist,
        album_project_events,
        merge_level,
    )
    detail_weighted_frame = _load_detail_weighted_frame(
        min_ms=min_ms,
        music_only=music_only,
        week_start_dow=bb_week_start_dow,
        week_start_hour=bb_week_start_hour,
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_enabled=merge_enabled,
    )

    return {
        "found": True,
        "chart_status": "charted" if not album_chart_data.empty else "not_charted",
        "track_chart_status": "charted" if not alb_tracks.empty else "not_charted",
        "effective_play_count": max(
            _effective_play_count(stats),
            int((album_project or {}).get("play_count") or 0),
        ),
        "album_name": resolved_album,
        "artist_name": resolved_artist,
        "cover_url": album_cover_url,
        "meta": _get_album_spotify_meta(
            resolved_album,
            resolved_artist,
            merge_level,
            detail_weighted_frame,
            album_project_id=(album_project or {}).get("album_project_id"),
        ),
        "info": (
            {
                "total_tracks": int(alb_row["total_tracks"]),
                "best_peak": int(alb_row["best_peak"]),
                "total_weeks": int(alb_row["total_weeks"]),
                "avg_weeks": round(float(alb_row["avg_weeks"]), 1),
                "top1": int(alb_row["top1"]),
                "top5": int(alb_row["top5"]),
                "top10": int(alb_row["top10"]),
                "weeks_at_no1": int(alb_row["weeks_at_no1"]),
                "album_chart_no1_weeks": int(alb_row.get("album_chart_no1_weeks", 0)),
                "total_track_power": int(
                    album_power_metrics["track_power_sum"]
                    if album_power_metrics is not None
                    and "track_power_sum" in album_power_metrics.index
                    and pd.notna(album_power_metrics["track_power_sum"])
                    else album_track_power["power_score"].sum()
                ),
                "track_power_rank": (
                    int(album_power_metrics["track_power_rank"])
                    if album_power_metrics is not None
                    and "track_power_rank" in album_power_metrics.index
                    and pd.notna(album_power_metrics["track_power_rank"])
                    else None
                ),
            }
            if alb_row is not None
            else None
        ),
        "chart_summary": chart_summary or None,
        "album_project": album_project,
        "album_weekly_history": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "play_count": int(r["play_count"]),
                "tracks_count": int(r.get("tracks_count", 0)),
                "change": r["change"],
                "running_peak": int(r.get("running_peak", r["rank"])),
                "running_wks": int(r.get("running_wks", 1)),
                "running_peak_wks": int(r.get("running_peak_wks", 0)),
            }
            for _, r in album_wk_history.iterrows()
        ]
        if not album_wk_history.empty
        else [],
        "album_no1_by_week": [
            {
                "week": str(r["billboard_week"]),
                "no1_track_names": r["no1_track_names"],
                "no1_track_id": int(r["no1_track_id"]) if pd.notna(r.get("no1_track_id")) else None,
                "no1_count": int(r["no1_count"]),
            }
            for _, r in album_no1.iterrows()
        ],
        "best_singles_overlay": [
            {
                "week": str(r["billboard_week"]),
                "rank": int(r["rank"]),
                "track_name": r["track_name"],
            }
            for _, r in best_singles.iterrows()
        ]
        if not best_singles.empty
        else [],
        "tracks": [
            {
                "track_id": r["track_id"],
                "track_name": r["track_name"],
                "peak_position": int(r["peak_position"]),
                "weeks_on_chart": int(r["weeks_on_chart"]),
                "weeks_at_peak": int(r["weeks_at_peak"]),
                "first_week": str(r["first_week"]),
                "first_peak_week": str(r.get("first_peak_week", "")),
                "last_week": str(r["last_week"]),
                "total_chart_plays": int(r["total_chart_plays"]),
                "power_score": int(r["power_score"]),
                "power_rank": int(r["power_rank"]) if r["power_rank"] > 0 else None,
                "cover_url": album_track_cover_map.get(int(r["track_id"])),
            }
            for _, r in alb_tracks.iterrows()
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Versus
# ═══════════════════════════════════════════════════════════════════════════
