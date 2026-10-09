"""Version explanations with target metadata and published logical weights."""

from __future__ import annotations

from backend.core.access_surface import snapshot_unavailable
from backend.domains.billboard.details import _classify_recording_kind, _version_album_cover_url
from backend.domains.metadata.release_dates import parse_release_date, precision_expression
from backend.domains.playback.track_groups import resolve_track_group_metadata


def attach_published_versions(
    conn, snapshot_key: str, l1_id: int, result: dict, merge_level: int
) -> None:
    if merge_level <= 1:
        return
    group = resolve_track_group_metadata(conn, l1_id, merge_level)
    if group is None:
        return
    # There is deliberately no join to plays. Source weights are the publication
    # authority, including short fragments, duration slices and coverage edges.
    versions = conn.execute(
        f"""SELECT li.l1_id AS track_id, t.track_name, al.album_name, al.album_id,
                    al.image_path, al.image_url, sam.album_type, sam.release_date,
                    {precision_expression(conn, "spotify_album_meta", "sam")} AS release_date_precision,
                    sam.image_url AS album_cover_url
             FROM track_groups groups
             JOIN track_group_l1_members members ON members.group_id=groups.group_id
             JOIN track_l1_identities li ON li.l1_id=members.l1_id
             JOIN tracks t ON t.track_id=li.representative_track_id
             LEFT JOIN albums al ON al.album_id=t.album_id
             LEFT JOIN spotify_album_meta sam ON sam.album_name=al.album_name
            WHERE (groups.group_id=? OR groups.parent_group_id=?) AND groups.group_status='active'
                  AND groups.scope IN ('composition','recording')
            GROUP BY li.l1_id ORDER BY li.l1_id""",
        (group["group_id"], group["group_id"]),
    ).fetchall()
    if len(versions) < 2:
        return
    from backend.domains.music_search.detail_projection import load_detail_source_facts

    source = load_detail_source_facts(
        conn, snapshot_key, l1_ids=[int(v["track_id"]) for v in versions]
    )
    if source is None:
        raise snapshot_unavailable("music_detail_versions")
    counts = (
        source.groupby("track_id")[["play_count", "total_ms"]].sum().to_dict("index")
        if not source.empty
        else {}
    )
    rows = []
    for v in versions:
        data = dict(v)
        weight = counts.get(int(v["track_id"]), {})
        rows.append(
            {
                "track_id": int(v["track_id"]),
                "l1_id": int(v["track_id"]),
                "track_name": v["track_name"],
                "album_name": v["album_name"],
                "plays": int(weight.get("play_count", 0)),
                "total_ms": int(weight.get("total_ms", 0)),
                "is_primary": int(v["track_id"]) == int(group["primary_l1_id"]),
                "recording_kind": _classify_recording_kind(v["track_name"]),
                "album_cover_url": _version_album_cover_url(data),
                "release_date": parse_release_date(
                    v["release_date"], v["release_date_precision"]
                ).display,
            }
        )
    rows.sort(key=lambda v: (-v["plays"], v["track_id"]))
    meta = dict(result.get("meta") or {})
    meta["version_group"] = {
        "group_id": int(group["group_id"]),
        "canonical_name": group["canonical_name"],
        "scope": group["scope"],
        "total_plays": sum(v["plays"] for v in rows),
        "versions": rows,
    }
    result["meta"] = meta
