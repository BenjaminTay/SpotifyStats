"""Target-scoped reads of one exact published detail context.

All builders share a SQLite read transaction.  No missing/corrupt publication
may enter a legacy chart, timeline or statistics builder.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.core.access_surface import snapshot_unavailable
from backend.core.db import get_db
from backend.domains.billboard import detail_summary as summaries
from backend.domains.metadata.artist_identity import resolve_artist_name
from backend.domains.music_search.context import build_music_search_filter_context
from backend.domains.music_search.snapshot_ledger import LedgerFamily


def _document(conn, args, entity, values):
    level = int(values["merge_level"])
    if entity == "track":
        return summaries._active_document(
            conn, kind="track", merge_level=level, track_id=int(args[0])
        )
    if entity == "album":
        return summaries._active_document(
            conn,
            kind="album" if level <= 1 else "album_project",
            merge_level=level,
            name=str(args[0]),
            artist_name=str(args[1]),
        )
    identity = resolve_artist_name(conn, str(args[0]))
    return summaries._active_document(
        conn,
        kind="artist",
        merge_level=level,
        name=identity.display_name if identity else str(args[0]),
    )


def build_published_detail(args: tuple, *, entity: LedgerFamily, view: str) -> dict[str, Any]:
    """Read the default UI publication; unsupported scopes fail explicitly."""
    values = summaries._filter_values(args, album_name=str(args[0]) if entity == "album" else None)
    conn = get_db(readonly=True)
    try:
        conn.execute("BEGIN")
        context = build_music_search_filter_context(conn, values)
        if int(values["merge_level"]) <= 1:
            raise snapshot_unavailable("music_detail", context.source_revision)
        key = summaries._snapshot_key(conn, values)
        if key is None:
            raise snapshot_unavailable("music_detail", context.source_revision)
        meta = conn.execute(
            "SELECT source_revision, filter_fingerprint FROM music_search_snapshot_meta WHERE snapshot_key=?",
            (key,),
        ).fetchone()
        if meta is None or meta["source_revision"] != context.source_revision:
            raise snapshot_unavailable("music_detail", context.source_revision)
        publication = {
            "status": "ready",
            "freshness": "current",
            "snapshot_key": key,
            "source_revision": context.source_revision,
            "filter_fingerprint": context.filter_fingerprint,
        }
        document = _document(conn, args, entity, values)
        if document is None:
            return {
                "found": False,
                "snapshot": publication,
                **summaries.unavailable_year_end_fields(),
            }
        from backend.domains.music_search.detail_projection import (
            validate_detail_entity_context,
            validate_detail_entity_ledger,
        )

        entity_key = str(document["entity_key"])
        if not validate_detail_entity_context(conn, key, entity_key):
            raise snapshot_unavailable("music_detail", context.source_revision)
        if not validate_detail_entity_ledger(conn, key, entity, entity_key):
            raise snapshot_unavailable("music_detail", context.source_revision)
        builder = getattr(summaries, f"build_{entity}_detail_summary")
        result = builder(args, conn=conn)
        if result is None:
            raise snapshot_unavailable("music_detail", context.source_revision)
        result["snapshot"] = publication
        if entity == "album":
            result["album_project_id"] = document["album_project_id"]
            from backend.domains.billboard.detail_project import project_unique_song_count

            result["unique_canonical_songs"] = project_unique_song_count(
                conn, key, document, values
            )
        if view == "summary":
            return result
        if view == "project":
            from backend.domains.billboard.detail_project import published_project

            result["album_project"] = published_project(conn, key, document, values)
            return result
        chart = result.get("summary") if entity == "track" else result.get("chart_summary")
        if entity == "track":
            from backend.domains.billboard.detail_versions import attach_published_versions

            attach_published_versions(conn, key, int(args[0]), result, int(values["merge_level"]))
        else:
            history, _chart_data = summaries._track_history(
                conn,
                snapshot_key=key,
                entity_key=str(document["entity_key"]),
                family=entity,
                top_n=int(values["bb_album_top_n" if entity == "album" else "bb_artist_top_n"]),
                peak_position=int(chart["peak_position"]) if chart else None,
            )
            if not summaries._track_history_matches_summary(chart, history):
                raise snapshot_unavailable("music_detail", context.source_revision)
            result[f"{entity}_weekly_history"] = history
            from backend.domains.music_search.detail_projection import load_detail_overlays

            overlays = load_detail_overlays(
                conn, key, entity=entity, document=document, values=values
            )
            if overlays is None:
                raise snapshot_unavailable("music_detail", context.source_revision)
            # Legacy association rows are emitted in artist/album/week order.
            if entity == "artist":
                overlays.get("week_no1_albums", []).sort(
                    key=lambda row: (row["artist_name"], row["album_name"], row["week"])
                )
            result.update(overlays)
        result.update(
            summaries._year_end_fields(
                conn,
                snapshot_key=key,
                family=entity,
                entity_key=str(document["entity_key"]),
                include_history=True,
            )
        )
        return result
    except sqlite3.DatabaseError:
        raise snapshot_unavailable("music_detail") from None
    finally:
        conn.close()
