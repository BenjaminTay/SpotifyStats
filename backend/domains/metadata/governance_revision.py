"""Exact transactional source counters for governance result publications.

The trigger/counter/epoch protocol matches Archive; readers fail closed on
schema drift. Display fields are excluded from the duration fact dependencies.
"""

from __future__ import annotations

import sqlite3
import uuid

from backend.core.access_surface import public_readonly_db_guard_active
from backend.services.analysis_snapshot_store import digest

SOURCES = {
    "plays": (
        "plays",
        "play_id ts ts_date ms_played track_id source_album_id spotify_track_id_at_play content_type",
    ),
    "tracks": ("tracks", "track_id artist_id spotify_track_id"),
    "duration": ("spotify_track_meta", "spotify_track_id duration_ms"),
    "identity": (
        "track_l1_identities",
        "l1_id fallback_track_id representative_track_id identity_status",
    ),
    "external_ids": ("track_l1_external_ids", "l1_id provider external_track_id"),
    "aliases": ("artist_identity_aliases", "alias_artist_id canonical_artist_id"),
    "attribution": ("artist_metadata_attribution_overrides", "track_id artist_id"),
    "artists": ("artists", "artist_id artist_name"),
    "genre_spotify": ("spotify_artist_meta", "artist_name spotify_artist_id genres"),
    "genre_override": (
        "artist_genre_overrides",
        "artist_name normalized_genres_json primary_genre language region confidence note",
    ),
    "genre_sources": (
        "artist_genre_sources",
        "source_id artist_name normalized_genres_json primary_genre language region source status confidence evidence_url evidence_summary",
    ),
    "language": (
        "artist_language_sources",
        "source_id artist_id classification primary_language_code language_variant origin status",
    ),
}
FACTS = ("plays", "tracks", "duration", "identity", "external_ids", "aliases", "attribution")
GENRE = (*FACTS, "artists", "genre_spotify", "genre_override", "genre_sources")
FAMILIES = {
    "primary_artist_ms": FACTS,
    "genre_coverage": GENRE,
    "genre_taxonomy": GENRE,
    "genre_axis_gaps": GENRE,
    "language_coverage": (*FACTS, "artists", "language"),
}
# Fields consumed by the existing health SQL and Album Project eligibility.
HEALTH_TABLES = {
    "plays": SOURCES["plays"][1],
    "tracks": "track_id artist_id album_id spotify_track_id",
    "albums": "album_id album_name artist_id",
    "artists": "artist_id artist_name",
    "track_artists": "track_id artist_id role",
    "spotify_track_meta": "spotify_track_id spotify_album_id",
    "spotify_album_meta": "spotify_album_id album_name album_artists album_type total_tracks image_url",
    "album_spotify_links": "album_id spotify_album_id play_count",
    "album_projects": "project_id",
    "album_project_albums": "album_id project_id",
    "album_project_tracks": "project_id track_id",
    "track_albums": "track_id album_id",
    "track_l1_identities": SOURCES["identity"][1],
    "track_l1_external_ids": "*",
    "track_l1_source_links": "l1_id track_id",
    "spotify_track_owners": "spotify_track_id track_id",
    "track_groups": "group_id group_status scope primary_l1_id",
    "track_group_l1_members": "group_id l1_id",
    "track_group_candidates": "*",
    "track_identity_state": "*",
    "agg_weekly_tracks": "",
    "agg_weekly_albums": "",
    "agg_weekly_artists": "",
    "schema_migrations": "*",
}


class GovernanceRevisionUnavailableError(ValueError):
    pass


def install_revision_tracking(conn):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot install governance revisions")
    old_schema = conn.execute("PRAGMA schema_version").fetchone()[0]
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    recorded = None
    if "governance_revision_schema" in tables:
        recorded = conn.execute(
            "SELECT schema_version FROM governance_revision_schema WHERE singleton=1"
        ).fetchone()
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS governance_source_revisions(domain TEXT PRIMARY KEY, epoch TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>=1))"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS governance_revision_schema(singleton INTEGER PRIMARY KEY CHECK(singleton=1),schema_version INTEGER NOT NULL)"
    )
    if recorded is not None and recorded[0] != old_schema:
        # A schema backfill must refresh FK field dependencies on existing
        # tables as well as install triggers for newly added tables.
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'governance_rev_%'"
        ).fetchall():
            conn.execute('DROP TRIGGER "' + row[0].replace('"', '""') + '"')
    sources = dict(SOURCES)
    health = dict(HEALTH_TABLES)
    # The health report includes PRAGMA foreign_key_check: track both referenced
    # keys and child FK fields, including non-music historical orphan records.
    for table in sorted(tables):
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")'):
            parent, child_col, parent_col = fk[2], fk[3], fk[4]
            for target, col in ((table, child_col), (parent, parent_col)):
                if target not in tables:
                    continue
                if col is None:
                    col = " ".join(
                        r[1] for r in conn.execute(f'PRAGMA table_info("{target}")') if r[5]
                    )
                if health.get(target) != "*":
                    health[target] = " ".join(
                        sorted(set((health.get(target, "") + " " + (col or "")).split()))
                    )
    sources.update({"health_" + t: (t, c) for t, c in health.items()})
    for domain, (table, requested) in sources.items():
        conn.execute(
            "INSERT OR IGNORE INTO governance_source_revisions VALUES(?,?,1)",
            (domain, uuid.uuid4().hex),
        )
        if table not in tables:
            continue
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        selected = sorted(columns if requested == "*" else columns.intersection(requested.split()))
        increment = (
            f"UPDATE governance_source_revisions SET revision=revision+1 WHERE domain='{domain}';"
        )
        for op in ("INSERT", "DELETE", "UPDATE"):
            if op == "UPDATE" and not selected:
                continue
            suffix = " OF " + ",".join(f'"{c}"' for c in selected) if op == "UPDATE" else ""
            when = (
                " WHEN " + " OR ".join(f'NEW."{c}" IS NOT OLD."{c}"' for c in selected)
                if op == "UPDATE"
                else ""
            )
            conn.execute(
                f'CREATE TRIGGER IF NOT EXISTS governance_rev_{domain}_{op.lower()} AFTER {op}{suffix} ON "{table}"{when} BEGIN {increment} END'
            )
    if recorded is None or recorded[0] != old_schema:
        conn.execute(
            "UPDATE governance_source_revisions SET epoch=?,revision=1", (uuid.uuid4().hex,)
        )
    version = conn.execute("PRAGMA schema_version").fetchone()[0]
    conn.execute("INSERT OR REPLACE INTO governance_revision_schema VALUES(1,?)", (version,))


def revision_vector(conn, family):
    try:
        marker = conn.execute(
            "SELECT schema_version FROM governance_revision_schema WHERE singleton=1"
        ).fetchone()
        if marker is None or marker[0] != conn.execute("PRAGMA schema_version").fetchone()[0]:
            raise GovernanceRevisionUnavailableError(
                "Governance revision schema requires local backfill"
            )
        if family == "import_health":
            rows = conn.execute(
                "SELECT domain,epoch,revision FROM governance_source_revisions WHERE domain LIKE 'health_%' ORDER BY domain"
            ).fetchall()
            required = {"health_" + t for t in HEALTH_TABLES}
            # Installation records the FK domain inventory, so missing a dynamic
            # counter must fail too (its trigger still names the missing domain).
            trigger_domains = {
                r[0].split("governance_rev_", 1)[1].rsplit("_", 1)[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'governance_rev_health_%'"
                )
            }
            required |= trigger_domains
        else:
            required = set(FAMILIES[family])
            rows = conn.execute(
                f"SELECT domain,epoch,revision FROM governance_source_revisions WHERE domain IN ({','.join('?' for _ in required)})",
                sorted(required),
            ).fetchall()
        if not required.issubset({r[0] for r in rows}) or any(not r[1] or r[2] < 1 for r in rows):
            raise GovernanceRevisionUnavailableError("Governance source counter missing")
        return {r[0]: f"{r[1]}:{r[2]}" for r in rows}
    except sqlite3.Error as exc:
        raise GovernanceRevisionUnavailableError("Run local governance revision backfill") from exc


def family_revision(conn, family):
    return digest(revision_vector(conn, family))
