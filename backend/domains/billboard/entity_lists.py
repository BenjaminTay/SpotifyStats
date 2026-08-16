"""Billboard entity lists for versus search selector."""

from backend.domains.billboard.chart_compute import compute_billboard_data


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

    detail_album_keys = {
        (row["album_name"], row["artist_name"]) for row in data["album_track_counts"]
    }
    album_rows = sorted(
        [
            row
            for row in data["album_power_scores"]
            if (row["album_name"], row["artist_name"]) in detail_album_keys
        ],
        key=lambda r: r.get("power_score") or 0,
        reverse=True,
    )
    albums = [
        {
            "display": f"{r['album_name']} — {r['artist_name']}",
            "album_name": r["album_name"],
            "artist_name": r["artist_name"],
        }
        for r in album_rows
    ]

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
