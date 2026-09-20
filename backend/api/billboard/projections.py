"""Read-only projections of published Billboard facts; never build or publish."""

from __future__ import annotations

from collections import defaultdict

from backend.core.access_surface import (
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
    snapshot_unavailable,
)
from backend.domains.billboard import persistent_cache as cache

WEEKLY = {"tracks": "weekly", "albums": "weekly_album", "artists": "weekly_artist"}
POWER = {"tracks": "power_scores", "albums": "album_power_scores", "artists": "artist_power_scores"}


def published(families: tuple[str, ...], params: dict) -> list[dict]:
    """Same normalized filters, builder and source/target across all families.

    Revision is sampled before and after reads, so a concurrent publication or
    source change can only return one generation or fail closed. Private reads
    use the same read-only path; maintenance retains its existing entrypoints.
    """
    token = set_public_readonly_db_guard(True)
    try:
        try:
            contexts = [cache.build_cache_context(f, params) for f in families]
            payloads = [cache.load_persisted_snapshot(c, include_read_state=True) for c in contexts]
            stable = contexts == [cache.build_cache_context(f, params) for f in families]
        except Exception:
            raise snapshot_unavailable(families[0]) from None
        if not stable or any(p is None for p in payloads):
            raise snapshot_unavailable(families[0], contexts[0]["source_revision"])
        states = [p["snapshot"] for p in payloads]
        if any(s != states[0] for s in states[1:]):
            raise snapshot_unavailable(families[0], contexts[0]["source_revision"])
        return payloads
    finally:
        reset_public_readonly_db_guard(token)


def identity(row: dict, entity: str):
    if entity == "tracks":
        return row["track_id"]
    if entity == "albums":
        return row["album_name"], row["artist_name"]
    return row["artist_name"]


def weekly_projection(data: dict, week: str | None, entity: str) -> dict:
    weeks = data["meta"]["all_weeks_desc"]
    selected = week if week in weeks else (weeks[0] if weeks else "")
    index = weeks.index(selected) if selected else 0
    previous = weeks[index + 1] if index + 1 < len(weeks) else None
    history = set(weeks[index + 1 :])
    rows = data[WEEKLY[entity]]
    current = sorted((r for r in rows if r["billboard_week"] == selected), key=lambda r: r["rank"])
    wanted = {identity(r, entity) for r in current}
    seen = {identity(r, entity) for r in rows if r["billboard_week"] in history}
    # One identity-bearing current row per returning entity is sufficient for
    # the existing frontend's historical membership test. No historical arrays.
    historical = [r for r in current if identity(r, entity) in seen & wanted]
    return {
        "snapshot": data["snapshot"],
        "meta": data["meta"],
        "selected_week": selected,
        "entity": entity,
        "current": current,
        "previous": [r for r in rows if r["billboard_week"] == previous],
        "historical": [
            {k: r[k] for k in ("track_id", "album_name", "artist_name") if k in r}
            for r in historical
        ],
    }


def cover_maps(data: dict) -> dict:
    covers: dict[str, dict] = {"track": {}, "artist": {}, "album": {}}
    for field, kind, key in [
        ("weekly", "track", "track_id"),
        ("weekly_artist", "artist", "artist_name"),
        ("weekly", "artist", "artist_name"),
        ("weekly_album", "album", "album_name"),
    ]:
        for row in data[field]:
            if row.get("cover_url"):
                covers[kind].setdefault(row[key], row["cover_url"])
    return covers


def records_projection(records: dict, summaries: dict, weekly: dict) -> dict:
    rows = summaries["track_summary"]
    groups = defaultdict(list)
    for row in rows:
        groups[row["track_name"].lower()].append(row)
    # Keep tied candidates; the frontend retains its localeCompare tie-breaks.
    lengths = [len(r["track_name"].encode("utf-16-le")) // 2 for r in rows]
    dates = [r["first_week"] for r in rows if r.get("first_week")]
    selected = {
        r["track_id"]
        for group in groups.values()
        if len({r["artist_name"] for r in group}) >= 2
        for r in group
    }
    length_edges = {min(lengths), max(lengths)} if lengths else set()
    date_edges = {min(dates), max(dates)} if dates else set()
    for row, length in zip(rows, lengths):
        if length in length_edges or row.get("first_week") in date_edges:
            selected.add(row["track_id"])
    tracks = [
        {
            k: r[k]
            for k in (
                "track_id",
                "track_name",
                "artist_name",
                "artist_names",
                "first_week",
                "peak_position",
            )
            if k in r
        }
        for r in rows
        if r["track_id"] in selected
    ]
    artist_counts = summaries["artist_track_counts"]
    top_counts = sorted((r["total_tracks"] for r in artist_counts), reverse=True)
    cutoff = top_counts[min(19, len(top_counts) - 1)] if top_counts else 0
    counts = [
        {
            k: r[k]
            for k in (
                "artist_name",
                "total_tracks",
                "top1",
                "total_weeks",
                "weeks_at_no1",
                "best_peak",
                "best_peak_track",
            )
        }
        for r in artist_counts
        if r["total_tracks"] >= cutoff or (r["total_tracks"] == 1 and r["top1"] >= 1)
    ]
    # Only cover identities reachable in the records and curiosity facts.
    values = set()

    def visit(value):
        if isinstance(value, dict):
            for k, v in value.items():
                values.add(k)
                visit(v)
        elif isinstance(value, list):
            for v in value:
                visit(v)
        elif isinstance(value, (str, int)):
            values.add(value)

    visit(records["records"])
    visit(tracks)
    visit(counts)
    covers = {
        kind: {k: v for k, v in mapping.items() if k in values}
        for kind, mapping in cover_maps(weekly).items()
    }
    # URL interning avoids repeating the same cover for track/album/artist.
    urls = list(dict.fromkeys(v for mapping in covers.values() for v in mapping.values()))
    indices = {url: i for i, url in enumerate(urls)}
    return {
        "snapshot": records["snapshot"],
        "records": records["records"],
        "curiosity_tracks": tracks,
        "artist_track_counts": counts,
        "covers": {
            "urls": urls,
            **{
                kind: [[k, indices[v]] for k, v in mapping.items()]
                for kind, mapping in covers.items()
            },
        },
    }


def number_ones_projection(data: dict) -> dict:
    result = {"snapshot": data["snapshot"]}
    for entity, field in WEEKLY.items():
        result[field] = [r for r in data[field] if r["rank"] == 1]
        wanted = {identity(r, entity) for r in result[field]}
        keys = {
            "tracks": ("track_id",),
            "albums": ("album_name", "artist_name"),
            "artists": ("artist_name",),
        }[entity]
        result[POWER[entity]] = [
            {k: r[k] for k in (*keys, "power_score")}
            for r in data[POWER[entity]]
            if identity(r, entity) in wanted
        ]
    return result


def all_time_projection(data: dict, entity: str) -> dict:
    """Equivalent to buildAllTimeRows, restricted to the requested entity."""
    weekly = data[WEEKLY[entity]]
    groups = defaultdict(list)
    covers: dict = {}
    for row in weekly:
        key = identity(row, entity)
        groups[key].append(row)
        if row.get("cover_url"):
            covers.setdefault(key, row["cover_url"])
    summaries = {r["track_id"]: r for r in data["track_summary"]} if entity == "tracks" else {}
    counts = (
        {
            identity(r, entity): r
            for r in data[
                {"albums": "album_track_counts", "artists": "artist_track_counts"}[entity]
            ]
        }
        if entity != "tracks"
        else {}
    )
    album_peaks: dict[tuple[str, str], int] = {}
    if entity == "artists":
        for row in data["weekly_album"]:
            key = (row["album_name"], row["artist_name"])
            album_peaks[key] = min(album_peaks.get(key, row["rank"]), row["rank"])
    rows = []
    for score in data[POWER[entity]]:
        key = identity(score, entity)
        history = groups[key]
        row = {
            k: score[k]
            for k in (
                "track_id",
                "track_name",
                "artist_name",
                "artist_names",
                "album_name",
                "weeks_on_chart",
                "peak_position",
                "power_score",
                "power_rank",
            )
            if k in score
        }
        row["cover_url"] = covers.get(key)
        if entity == "tracks":
            summary = summaries.get(key, {})
            row.update(
                album_name=summary.get("album_name", ""),
                weeks_at_peak=summary.get("weeks_at_peak", 0),
                weeks_top5=score.get("weeks_top5"),
                weeks_top10=score.get("weeks_top10"),
                total_chart_plays=summary.get("total_chart_plays", 0),
                is_debut_no1=summary.get("is_debut_no1", False),
            )
        else:
            peak = min((r["rank"] for r in history), default=0)
            first = min((r["billboard_week"] for r in history), default="")
            count = counts.get(key, {})
            row.update(
                weeks_at_peak=sum(r["rank"] == peak for r in history),
                weeks_top5=sum(r["rank"] <= 5 for r in history),
                weeks_top10=sum(r["rank"] <= 10 for r in history),
                total_tracks=count.get("total_tracks", 0),
                top1_tracks=count.get("top1", 0),
                top5_tracks=count.get("top5", 0),
                top10_tracks=count.get("top10", 0),
                track_power_sum=score.get("track_power_sum") or 0,
                track_power_rank=score.get("track_power_rank"),
                total_plays=sum(r["play_count"] for r in history),
                is_debut_no1=score["peak_position"] == 1
                and any(r["billboard_week"] == first and r["rank"] == 1 for r in history),
            )
            if entity == "albums" and score.get("total_plays") is not None:
                row["total_plays"] = score["total_plays"]
            if entity == "artists":
                row.update(
                    num_no1_albums=count.get("num_no1_albums", 0),
                    top5_albums=sum(
                        artist == key and peak <= 5 for (_, artist), peak in album_peaks.items()
                    ),
                    top10_albums=sum(
                        artist == key and peak <= 10 for (_, artist), peak in album_peaks.items()
                    ),
                    album_power_sum=score.get("album_power_sum") or 0,
                    album_power_rank=score.get("album_power_rank"),
                )
        rows.append(row)
    return {"snapshot": data["snapshot"], "entity": entity, "rows": rows}
