"""Album attribution assembled from target publication components."""

from __future__ import annotations

import pandas as pd

from backend.core.access_surface import snapshot_unavailable
from backend.core.json_helpers import df_to_json
from backend.domains.billboard.details import (
    _build_l3_source_project_explanation,
    _enrich_source_breakdown,
)
from backend.domains.metadata.release_dates import parse_release_date
from backend.domains.playback.album_projects import SOURCE_BUCKET_ORDER, _attach_source_album_bucket


def _components(conn, key, document, values):
    from backend.domains.music_search.detail_projection import (
        load_detail_project_membership,
        load_detail_source_facts,
    )

    project_id = document["album_project_id"]
    if project_id is None or int(values["merge_level"]) <= 1:
        return None, pd.DataFrame(), pd.DataFrame()
    membership = load_detail_project_membership(conn, key, int(project_id))
    if membership is None:
        raise snapshot_unavailable("music_detail_project")
    id_keys = {}
    for row in membership.to_dict("records"):
        for l1_id in row.get("l1_ids", [row["track_id"]]):
            id_keys[int(l1_id)] = str(row["canonical_song_key"])
    source = load_detail_source_facts(conn, key, l1_ids=list(id_keys))
    if source is None:
        raise snapshot_unavailable("music_detail_project")
    if not source.empty:
        source = source.copy()
        source["canonical_song_key"] = source["track_id"].map(id_keys)
        names = {
            str(r["canonical_song_key"]): r.get("canonical_song_name", r.get("track_name", ""))
            for r in membership.to_dict("records")
        }
        source["canonical_song_name"] = source["canonical_song_key"].map(names)
    return int(project_id), membership, source


def project_unique_song_count(conn, key, document, values):
    project_id, _membership, source = _components(conn, key, document, values)
    return (
        int(source["canonical_song_key"].nunique())
        if project_id is not None and not source.empty
        else 0
    )


def published_project(conn, key, document, values):
    project_id, membership, source = _components(conn, key, document, values)
    if project_id is None:
        return None
    project = conn.execute(
        "SELECT * FROM album_projects WHERE project_id=?", (project_id,)
    ).fetchone()
    if project is None:
        raise snapshot_unavailable("music_detail_project")
    if not membership.empty:
        membership = membership.drop(columns=["l1_ids"], errors="ignore").copy()
        membership["_bucket_rank"] = membership["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
        membership = membership.sort_values(["_bucket_rank", "track_id"]).drop(
            columns=["_bucket_rank"]
        )
    breakdown = []
    if not source.empty:
        scoped = _attach_source_album_bucket(source, conn)
        frame = (
            scoped.groupby(["source_album_id", "source_album_name", "source_bucket"], dropna=False)[
                ["play_count", "total_ms"]
            ]
            .sum()
            .reset_index()
        )
        frame["album_project_id"] = project_id
        frame["album_project_name"] = str(document["label"])
        frame = _enrich_source_breakdown(conn, frame)
        frame["_bucket_rank"] = frame["source_bucket"].map(SOURCE_BUCKET_ORDER).fillna(99)
        frame = frame.sort_values(["_bucket_rank", "source_album_name"]).drop(
            columns=["_bucket_rank"]
        )
        breakdown = df_to_json(frame)
    result = {
        "album_project_id": project_id,
        "album_project_name": str(document["label"]),
        "artist_name": str(document["artist_name"]),
        "release_date": parse_release_date(
            project["release_date"], project["release_date_precision"]
        ).display,
        "release_date_raw": str(project["release_date"] or ""),
        "play_count": int(source["play_count"].sum()) if not source.empty else 0,
        "total_ms": int(source["total_ms"].sum()) if not source.empty else 0,
        "unique_canonical_songs": int(source["canonical_song_key"].nunique())
        if not source.empty
        else 0,
        "tracks": df_to_json(membership),
        "source_breakdown": breakdown,
    }
    if int(values["merge_level"]) >= 3:
        from backend.domains.music_search.detail_projection import load_detail_source_facts

        album_ids = [
            int(r[0])
            for r in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=?", (project_id,)
            )
        ]
        physical = load_detail_source_facts(conn, key, source_album_ids=album_ids)
        if physical is None:
            raise snapshot_unavailable("music_detail_project")
        result.update(
            _build_l3_source_project_explanation(conn, physical, project_id, target_only=True)
        )
    return result
