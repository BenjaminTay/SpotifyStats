"""Billboard entity lists for versus search selector."""

from backend.core.db import get_db
from backend.domains.billboard.chart_compute import compute_billboard_data
from backend.domains.playback.album_project_identity import normalize_album_project_lookup


def get_billboard_entity_lists(
    min_ms,
    music_only,
    bb_top_n,
    bb_album_top_n,
    bb_artist_top_n,
    bb_week_start_dow,
    bb_week_start_hour,
    year_start,
    year_end,
    search=None,
    dynamic_threshold=False,
    max_merge_gap_minutes=5,
    merge_level=2,
    include_compilations=False,
    merge_enabled=True,
):
    """Return entity lists for versus search pickers (tracks, albums, artists)."""
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
        dynamic_threshold=dynamic_threshold,
        max_merge_gap_minutes=max_merge_gap_minutes,
        merge_level=merge_level,
        include_compilations=include_compilations,
        merge_enabled=merge_enabled,
    )

    track_rows = sorted(
        data["track_summary"],
        key=lambda r: r.get("total_chart_plays") or 0,
        reverse=True,
    )
    tracks = [
        {"display": f"{r['track_name']} — {r['artist_name']}", "track_id": r["track_id"]}
        for r in track_rows
    ]

    def album_key(row):
        return (
            row["album_project_id"]
            if "album_project_id" in row
            else (row["album_name"], row["artist_name"])
        )

    detail_album_keys = {album_key(row) for row in data["album_track_counts"]}
    album_rows = sorted(
        [row for row in data["album_power_scores"] if album_key(row) in detail_album_keys],
        key=lambda r: r.get("power_score") or 0,
        reverse=True,
    )
    albums = [
        {
            "display": f"{r['album_name']} — {r['artist_name']}",
            "album_name": r["album_name"],
            "artist_name": r["artist_name"],
            **(
                {"project_id": int(r["album_project_id"])}
                if r.get("album_project_id") is not None
                else {}
            ),
        }
        for r in album_rows
    ]
    # Only colliding labels need extra edition context. IDs always come from
    # the selected published chart, never a second name-based resolution.
    groups = {}
    for item in albums:
        key = (
            normalize_album_project_lookup(item["artist_name"]),
            normalize_album_project_lookup(item["album_name"]),
        )
        groups.setdefault(key, []).append(item)
    colliding = [
        item
        for group in groups.values()
        if len({a.get("project_id") for a in group}) > 1
        for item in group
    ]
    if colliding:
        from backend.domains.metadata.release_dates import release_anchor_sources

        conn = get_db(readonly=True)
        try:
            for item in colliding:
                pid = item.get("project_id")
                project = conn.execute(
                    "SELECT primary_album_id,release_date FROM album_projects WHERE project_id=?",
                    (pid,),
                ).fetchone()
                if not project:
                    continue
                sources = release_anchor_sources(conn, project[0], project_id=pid)
                ids = tuple(row["spotify_album_id"] for row in sources)
                kinds = (
                    {
                        row[0]
                        for row in conn.execute(
                            f"SELECT album_type FROM spotify_album_meta WHERE spotify_album_id IN ({','.join('?' for _ in ids)})",
                            ids,
                        )
                    }
                    if ids
                    else set()
                )
                kind = "单曲" if kinds == {"single"} else "专辑"
                year = str(project[1] or "")[:4]
                item["display"] = f"{item['album_name']} · {year} {kind} — {item['artist_name']}"
        finally:
            conn.close()

    detail_artist_names = {row["artist_name"] for row in data["artist_track_counts"]}
    artist_rows = sorted(
        [row for row in data["artist_power_scores"] if row["artist_name"] in detail_artist_names],
        key=lambda r: r.get("power_score") or 0,
        reverse=True,
    )
    artists = [{"display": r["artist_name"], "artist_name": r["artist_name"]} for r in artist_rows]

    if search:
        q = search.lower()
        tracks = [t for t in tracks if q in t["display"].lower()]
        albums = [a for a in albums if q in a["display"].lower()]
        artists = [a for a in artists if q in a["display"].lower()]

    return {"tracks": tracks, "albums": albums, "artists": artists}
