#!/usr/bin/env python3
"""只读审计 canonical track、外部 ID 所有权与 L2/L3 关系。

文件名保留为兼容入口；报告语义从 v2 起不再把 Spotify ID 等同于 L1。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

RAW_TABLES = ("plays", "tracks", "track_artists")


def _exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _count(conn: sqlite3.Connection, table: str) -> int:
    return (
        int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        if _exists(conn, table)
        else 0
    )


def _digest(conn: sqlite3.Connection, table: str) -> str | None:
    if not _exists(conn, table):
        return None
    columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')]
    if not columns:
        return hashlib.sha256(b"").hexdigest()
    quoted = ", ".join(f'"{column}"' for column in columns)
    order = ", ".join(str(index + 1) for index in range(len(columns)))
    digest = hashlib.sha256()
    for row in conn.execute(f'SELECT {quoted} FROM "{table}" ORDER BY {order}'):
        digest.update(
            json.dumps(list(row), ensure_ascii=True, separators=(",", ":"), default=str).encode()
        )
        digest.update(b"\n")
    return digest.hexdigest()


def _scalar(conn: sqlite3.Connection, sql: str) -> int:
    return int(conn.execute(sql).fetchone()[0])


def build_audit(conn: sqlite3.Connection, target_name: str | None = None) -> dict[str, Any]:
    conn.row_factory = sqlite3.Row
    raw = {
        table: {"rows": _count(conn, table), "sha256": _digest(conn, table)} for table in RAW_TABLES
    }
    report: dict[str, Any] = {
        "schema_version": "canonical_track_audit_v2",
        "user_version": _scalar(conn, "PRAGMA user_version"),
        "schema_migration_version": (
            _scalar(conn, "SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
            if _exists(conn, "schema_migrations")
            else 0
        ),
        "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
        "foreign_key_violation_count": len(conn.execute("PRAGMA foreign_key_check").fetchall()),
        "raw_tables": raw,
        "canonical_tracks": {
            "available": _exists(conn, "track_l1_identities")
            and _exists(conn, "track_l1_external_ids")
        },
        "groups": {"available": _exists(conn, "track_group_l1_members")},
        "aggregates": {},
    }
    canonical = report["canonical_tracks"]
    if canonical["available"]:
        canonical.update(
            {
                "active_count": _scalar(
                    conn,
                    "SELECT COUNT(*) FROM track_l1_identities WHERE identity_status='active'",
                ),
                "unresolved_count": _scalar(
                    conn,
                    "SELECT COUNT(*) FROM track_l1_identities WHERE identity_status='unresolved'",
                ),
                "superseded_count": _scalar(
                    conn,
                    "SELECT COUNT(*) FROM track_l1_identities WHERE identity_status='superseded'",
                ),
                "spotify_external_id_count": _scalar(
                    conn,
                    "SELECT COUNT(*) FROM track_l1_external_ids WHERE provider='spotify'",
                ),
                "distinct_play_spotify_id_count": _scalar(
                    conn,
                    """SELECT COUNT(DISTINCT COALESCE(NULLIF(p.spotify_track_id_at_play, ''),
                                                        NULLIF(t.spotify_track_id, '')))
                         FROM plays p LEFT JOIN tracks t ON t.track_id=p.track_id""",
                ),
                "duplicate_external_owner_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM (
                           SELECT provider, external_track_id
                             FROM track_l1_external_ids
                            GROUP BY provider, external_track_id
                           HAVING COUNT(DISTINCT l1_id)>1
                       )""",
                ),
                "multi_spotify_id_canonical_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM (
                           SELECT l1_id FROM track_l1_external_ids
                            WHERE provider='spotify'
                            GROUP BY l1_id HAVING COUNT(*)>1
                       )""",
                ),
                "unresolved_play_identity_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM plays p
                         LEFT JOIN tracks t ON t.track_id=p.track_id
                         LEFT JOIN track_l1_external_ids external
                           ON external.provider='spotify'
                          AND external.external_track_id=COALESCE(
                              NULLIF(p.spotify_track_id_at_play, ''),
                              NULLIF(t.spotify_track_id, '')
                          )
                        WHERE COALESCE(NULLIF(p.spotify_track_id_at_play, ''),
                                       NULLIF(t.spotify_track_id, '')) IS NOT NULL
                          AND external.l1_id IS NULL""",
                ),
                "external_owner_orphan_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM track_l1_external_ids external
                         LEFT JOIN track_l1_identities identity ON identity.l1_id=external.l1_id
                        WHERE identity.l1_id IS NULL OR identity.identity_status='superseded'""",
                ),
                "source_link_orphan_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM track_l1_source_links links
                         LEFT JOIN track_l1_identities li ON li.l1_id=links.l1_id
                         LEFT JOIN tracks t ON t.track_id=links.track_id
                        WHERE li.l1_id IS NULL OR t.track_id IS NULL""",
                ),
                "active_representative_missing_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM track_l1_identities
                        WHERE identity_status='active' AND representative_track_id IS NULL""",
                ),
            }
        )
    if report["groups"]["available"]:
        report["groups"].update(
            {
                "active_group_count": _scalar(
                    conn, "SELECT COUNT(*) FROM track_groups WHERE group_status='active'"
                ),
                "archived_group_count": _scalar(
                    conn, "SELECT COUNT(*) FROM track_groups WHERE group_status='archived'"
                ),
                "conflict_group_count": _scalar(
                    conn, "SELECT COUNT(*) FROM track_groups WHERE group_status='conflict'"
                ),
                "active_single_canonical_group_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM (
                           SELECT groups.group_id
                             FROM track_groups groups
                             JOIN track_group_l1_members members ON members.group_id=groups.group_id
                            WHERE groups.group_status='active'
                            GROUP BY groups.group_id HAVING COUNT(DISTINCT members.l1_id)<2
                       )""",
                ),
                "same_scope_overlap_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM (
                           SELECT groups.scope, members.l1_id
                             FROM track_groups groups
                             JOIN track_group_l1_members members ON members.group_id=groups.group_id
                            WHERE groups.group_status='active'
                            GROUP BY groups.scope, members.l1_id HAVING COUNT(DISTINCT groups.group_id)>1
                       )""",
                ),
                "pending_candidate_count": _scalar(
                    conn,
                    "SELECT COUNT(*) FROM track_group_candidates WHERE status='pending'",
                ),
                "active_group_noncanonical_member_count": _scalar(
                    conn,
                    """SELECT COUNT(*)
                         FROM track_group_l1_members members
                         JOIN track_groups groups ON groups.group_id=members.group_id
                        WHERE groups.group_status='active'
                          AND NOT EXISTS (
                              SELECT 1 FROM spotify_track_owners self_owner
                               WHERE self_owner.track_id=members.l1_id
                          )
                          AND (
                              EXISTS (
                                  SELECT 1
                                    FROM tracks source
                                    JOIN spotify_track_owners raw_owner
                                      ON raw_owner.spotify_track_id=source.spotify_track_id
                                   WHERE source.track_id=members.l1_id
                                     AND raw_owner.track_id!=members.l1_id
                              )
                              OR EXISTS (
                                  SELECT 1 FROM track_l1_source_links alias_link
                                   WHERE alias_link.track_id=members.l1_id
                                     AND alias_link.l1_id!=members.l1_id
                              )
                          )""",
                ),
                "active_group_invalid_primary_count": _scalar(
                    conn,
                    """SELECT COUNT(*) FROM track_groups groups
                        WHERE groups.group_status='active'
                          AND (
                              groups.primary_l1_id IS NULL
                              OR NOT EXISTS (
                                  SELECT 1 FROM track_group_l1_members members
                                   WHERE members.group_id=groups.group_id
                                     AND members.l1_id=groups.primary_l1_id
                              )
                          )""",
                ),
                "pending_candidate_noncanonical_reference_count": _scalar(
                    conn,
                    """SELECT COUNT(*)
                         FROM track_group_candidates candidates
                        WHERE candidates.status='pending'
                          AND (
                              (
                                  NOT EXISTS (
                                      SELECT 1 FROM spotify_track_owners left_self
                                       WHERE left_self.track_id=candidates.original_l1_id
                                  )
                                  AND EXISTS (
                                      SELECT 1 FROM tracks source
                                      JOIN spotify_track_owners raw_owner
                                        ON raw_owner.spotify_track_id=source.spotify_track_id
                                     WHERE source.track_id=candidates.original_l1_id
                                       AND raw_owner.track_id!=candidates.original_l1_id
                                  )
                              )
                              OR (
                                  NOT EXISTS (
                                      SELECT 1 FROM spotify_track_owners right_self
                                       WHERE right_self.track_id=candidates.candidate_l1_id
                                  )
                                  AND EXISTS (
                                      SELECT 1 FROM tracks source
                                      JOIN spotify_track_owners raw_owner
                                        ON raw_owner.spotify_track_id=source.spotify_track_id
                                     WHERE source.track_id=candidates.candidate_l1_id
                                       AND raw_owner.track_id!=candidates.candidate_l1_id
                                  )
                              )
                          )""",
                ),
            }
        )
    for table in ("agg_weekly_tracks", "agg_weekly_track_sources"):
        if not _exists(conn, table):
            continue
        columns = {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}
        summary: dict[str, Any] = {
            "rows": _count(conn, table),
            "play_count_sum": _scalar(conn, f"SELECT COALESCE(SUM(play_count), 0) FROM {table}"),
            "total_ms_sum": _scalar(conn, f"SELECT COALESCE(SUM(total_ms), 0) FROM {table}"),
            "grain": "canonical_track" if "l1_id" in columns else "legacy_track",
        }
        if {"filter_id", "week_start_dow", "week_start_hour", "billboard_week", "l1_id"}.issubset(
            columns
        ):
            summary["duplicate_grain_count"] = _scalar(
                conn,
                f"""SELECT COUNT(*) FROM (
                       SELECT filter_id, week_start_dow, week_start_hour, billboard_week, l1_id
                         FROM {table}
                        GROUP BY filter_id, week_start_dow, week_start_hour, billboard_week, l1_id
                       HAVING COUNT(*)>1
                   )""",
            )
        report["aggregates"][table] = summary
    if target_name and canonical["available"]:
        rows = conn.execute(
            """SELECT li.l1_id AS canonical_track_id,
                      GROUP_CONCAT(DISTINCT external.external_track_id) AS spotify_track_ids,
                      t.track_id AS representative_track_id,
                      t.track_name, a.artist_name,
                      COUNT(DISTINCT links.track_id) AS source_record_count
                 FROM track_l1_identities li
                 JOIN tracks t ON t.track_id=li.representative_track_id
                 LEFT JOIN track_l1_external_ids external
                   ON external.l1_id=li.l1_id AND external.provider='spotify'
                 LEFT JOIN artists a ON a.artist_id=t.artist_id
                LEFT JOIN track_l1_source_links links ON links.l1_id=li.l1_id
                WHERE t.track_name=?
                  AND li.identity_status!='superseded'
                  AND (
                      EXISTS (
                          SELECT 1 FROM spotify_track_owners self_owner
                           WHERE self_owner.track_id=li.l1_id
                      )
                      OR (
                          NOT EXISTS (
                              SELECT 1 FROM spotify_track_owners raw_owner
                               WHERE raw_owner.spotify_track_id=t.spotify_track_id
                                 AND raw_owner.track_id!=li.l1_id
                          )
                          AND NOT EXISTS (
                              SELECT 1 FROM track_l1_source_links alias_link
                               WHERE alias_link.track_id=li.l1_id
                                 AND alias_link.l1_id!=li.l1_id
                          )
                      )
                  )
                GROUP BY li.l1_id ORDER BY li.l1_id""",
            (target_name,),
        ).fetchall()
        report["target"] = [dict(row) for row in rows]
    if canonical["available"]:
        blocking = sum(
            int(canonical.get(key, 0))
            for key in (
                "duplicate_external_owner_count",
                "unresolved_play_identity_count",
                "external_owner_orphan_count",
                "source_link_orphan_count",
                "active_representative_missing_count",
            )
        ) + sum(
            int(report["groups"].get(key, 0))
            for key in (
                "active_single_canonical_group_count",
                "same_scope_overlap_count",
                "active_group_noncanonical_member_count",
                "active_group_invalid_primary_count",
                "pending_candidate_noncanonical_reference_count",
            )
        )
        report["status"] = "pass" if blocking == 0 else "fail"
        report["blocking_issue_count"] = blocking
    else:
        report["status"] = "blocked"
        report["blocking_issue_count"] = None
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("db", type=Path)
    parser.add_argument("--target-name")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    uri = f"file:{args.db.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        payload = build_audit(conn, args.target_name)
    finally:
        conn.close()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
