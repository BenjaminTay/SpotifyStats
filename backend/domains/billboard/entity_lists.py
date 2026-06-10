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

    album_rows = sorted(
        data["album_power_scores"],
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

    artist_rows = sorted(
        data["artist_power_scores"],
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
