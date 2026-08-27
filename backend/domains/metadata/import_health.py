"""Read-only health checks for imported and derived Spotify data."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date, timedelta
from typing import Any


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    if not _table_exists(conn, table_name):
        return False
    return any(row[1] == column_name for row in conn.execute(f"PRAGMA table_info({table_name})"))


def _count(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row else 0


def _foreign_key_issue_breakdown(conn: sqlite3.Connection) -> dict[str, int]:
    """Return FK issues grouped by child table and referenced parent table."""
    breakdown: dict[str, int] = {}
    for row in conn.execute("PRAGMA foreign_key_check").fetchall():
        child_table = str(row[0])
        parent_table = str(row[2]) if len(row) > 2 and row[2] else "unknown"
        key = f"{child_table} -> {parent_table}"
        breakdown[key] = breakdown.get(key, 0) + 1
    return dict(sorted(breakdown.items(), key=lambda item: (-item[1], item[0])))


def _setting_bool(conn: sqlite3.Connection, key: str) -> bool:
    if not _table_exists(conn, "settings"):
        return False
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return False
    return str(row[0]).lower() in {"1", "true", "yes", "on"}


def _state_snapshot(conn: sqlite3.Connection, table_name: str) -> dict[str, Any]:
    default = {
        "current_revision": 0,
        "active_aggregate_revision": 0,
        "rebuild_status": "ready",
        "last_error": None,
    }
    if not _table_exists(conn, table_name):
        return default
    row = conn.execute(
        f"""SELECT current_revision, active_aggregate_revision, rebuild_status,
                    last_error
               FROM {table_name}
              WHERE state_id = 1"""
    ).fetchone()
    if not row:
        return default
    return {
        "current_revision": int(row[0] or 0),
        "active_aggregate_revision": int(row[1] or 0),
        "rebuild_status": row[2] or "ready",
        "last_error": row[3],
    }


def _default_since_date(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT MAX(ts_date) FROM plays").fetchone()
    latest = row[0] if row and row[0] else None
    if not latest:
        return "1900-01-01"
    try:
        return (date.fromisoformat(str(latest)) - timedelta(days=90)).isoformat()
    except ValueError:
        return "1900-01-01"


def _recent_album_project_health(
    conn: sqlite3.Connection,
    since_date: str,
) -> dict[str, int]:
    """Count only recent source albums that share builder eligibility rules."""

    from backend.domains.playback.album_projects import (
        resolve_album_project_eligibility,
    )

    if not _table_exists(conn, "plays"):
        return {
            "unresolved_recent_albums": 0,
            "recent_album_project_eligible": 0,
            "recent_album_project_not_required": 0,
        }
    rows = conn.execute(
        """SELECT p.source_album_id AS album_id,
                  COUNT(DISTINCT p.track_id) AS local_tracks
             FROM plays p
            WHERE p.ts_date > ?
              AND p.content_type = 'audio'
              AND p.track_id IS NOT NULL
              AND p.source_album_id IS NOT NULL
            GROUP BY p.source_album_id""",
        (since_date,),
    ).fetchall()
    memberships = (
        {
            int(row[0])
            for row in conn.execute("SELECT DISTINCT album_id FROM album_project_albums").fetchall()
        }
        if _table_exists(conn, "album_project_albums")
        else set()
    )
    name_match_types: dict[int, str | None] = {}
    if all(
        _table_exists(conn, table) for table in ("albums", "artists", "spotify_album_meta")
    ) and all(
        (
            _column_exists(conn, "albums", "album_name"),
            _column_exists(conn, "artists", "artist_name"),
            _column_exists(conn, "spotify_album_meta", "album_name"),
            _column_exists(conn, "spotify_album_meta", "album_artists"),
        )
    ):
        for row in conn.execute(
            """SELECT al.album_id,
                      (SELECT sam.album_type
                         FROM spotify_album_meta sam
                        WHERE lower(sam.album_name) = lower(al.album_name)
                          AND (sam.album_artists IS NULL
                               OR ar.artist_name IS NULL
                               OR instr(lower(sam.album_artists), lower(ar.artist_name)) > 0)
                        ORDER BY CASE sam.album_type
                                   WHEN 'album' THEN 0
                                   WHEN 'ep' THEN 1
                                   WHEN 'single' THEN 2
                                   ELSE 3
                                 END
                        LIMIT 1) AS album_type
                 FROM albums al
                 LEFT JOIN artists ar ON ar.artist_id = al.artist_id"""
        ).fetchall():
            name_match_types[int(row[0])] = str(row[1]) if row[1] else None

    eligible = 0
    unresolved = 0
    not_required = 0
    for row in rows:
        album_id = int(row[0])
        result = resolve_album_project_eligibility(
            conn,
            album_id,
            name_match_type=name_match_types.get(album_id),
            local_tracks=int(row[1] or 0),
        )
        if not result.eligible:
            not_required += 1
            continue
        eligible += 1
        if album_id not in memberships:
            unresolved += 1
    return {
        "unresolved_recent_albums": unresolved,
        "recent_album_project_eligible": eligible,
        "recent_album_project_not_required": not_required,
    }


def _build_database_health(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "plays"):
        return {
            "play_count": 0,
            "audio_play_count": 0,
            "video_play_count": 0,
            "valid_audio_play_count": 0,
            "active_day_count": 0,
            "first_play_date": None,
            "last_play_date": None,
            "null_track_audio_count": 0,
            "negative_duration_count": 0,
            "sqlite_integrity": "missing_plays_table",
            "foreign_key_issue_count": 0,
            "foreign_key_issue_breakdown": {},
            "artist_count": _count(conn, "SELECT COUNT(*) FROM artists")
            if _table_exists(conn, "artists")
            else 0,
            "album_count": _count(conn, "SELECT COUNT(*) FROM albums")
            if _table_exists(conn, "albums")
            else 0,
            "track_count": _count(conn, "SELECT COUNT(*) FROM tracks")
            if _table_exists(conn, "tracks")
            else 0,
        }

    bounds = conn.execute(
        "SELECT MIN(ts_date), MAX(ts_date), COUNT(DISTINCT ts_date) FROM plays"
    ).fetchone()
    integrity_row = conn.execute("PRAGMA integrity_check").fetchone()
    integrity = str(integrity_row[0]) if integrity_row else "unknown"
    foreign_key_issue_breakdown = _foreign_key_issue_breakdown(conn)
    foreign_key_issues = sum(foreign_key_issue_breakdown.values())
    has_duration = _column_exists(conn, "plays", "ms_played")
    return {
        "play_count": _count(conn, "SELECT COUNT(*) FROM plays"),
        "audio_play_count": _count(conn, "SELECT COUNT(*) FROM plays WHERE content_type = 'audio'"),
        "video_play_count": _count(conn, "SELECT COUNT(*) FROM plays WHERE content_type = 'video'"),
        "valid_audio_play_count": _count(
            conn,
            """SELECT COUNT(*) FROM plays
               WHERE content_type = 'audio' AND track_id IS NOT NULL AND ms_played >= 30000""",
        )
        if has_duration
        else 0,
        "active_day_count": int(bounds[2] or 0) if bounds else 0,
        "first_play_date": bounds[0] if bounds else None,
        "last_play_date": bounds[1] if bounds else None,
        "null_track_audio_count": _count(
            conn,
            "SELECT COUNT(*) FROM plays WHERE content_type = 'audio' AND track_id IS NULL",
        ),
        "negative_duration_count": _count(conn, "SELECT COUNT(*) FROM plays WHERE ms_played < 0")
        if has_duration
        else 0,
        "sqlite_integrity": integrity,
        "foreign_key_issue_count": foreign_key_issues,
        "foreign_key_issue_breakdown": foreign_key_issue_breakdown,
        "artist_count": _count(conn, "SELECT COUNT(*) FROM artists")
        if _table_exists(conn, "artists")
        else 0,
        "album_count": _count(conn, "SELECT COUNT(*) FROM albums")
        if _table_exists(conn, "albums")
        else 0,
        "track_count": _count(conn, "SELECT COUNT(*) FROM tracks")
        if _table_exists(conn, "tracks")
        else 0,
    }


def _build_relationship_health(conn: sqlite3.Connection) -> dict[str, int]:
    relationships = {
        "orphan_play_track_count": 0,
        "orphan_play_album_count": 0,
        "tracks_without_primary_credit_count": 0,
        "orphan_track_artist_track_count": 0,
        "orphan_track_artist_artist_count": 0,
        "tracks_missing_artist_count": 0,
        "albums_missing_artist_count": 0,
        "tracks_missing_album_count": 0,
        "affected_play_count_tracks_missing_artist": 0,
        "affected_play_count_albums_missing_artist": 0,
        "affected_play_count_tracks_missing_album": 0,
        "affected_play_count_without_primary_credit": 0,
    }
    if _table_exists(conn, "plays") and _table_exists(conn, "tracks"):
        relationships["orphan_play_track_count"] = _count(
            conn,
            """SELECT COUNT(*) FROM plays p
               LEFT JOIN tracks t ON t.track_id = p.track_id
               WHERE p.track_id IS NOT NULL AND t.track_id IS NULL""",
        )
    if _table_exists(conn, "plays") and _table_exists(conn, "albums"):
        relationships["orphan_play_album_count"] = _count(
            conn,
            """SELECT COUNT(*) FROM plays p
               LEFT JOIN albums a ON a.album_id = p.source_album_id
               WHERE p.source_album_id IS NOT NULL AND a.album_id IS NULL""",
        )
    if _table_exists(conn, "tracks") and _table_exists(conn, "track_artists"):
        relationships["tracks_without_primary_credit_count"] = _count(
            conn,
            """SELECT COUNT(*) FROM tracks t
               WHERE NOT EXISTS (
                 SELECT 1 FROM track_artists ta
                  WHERE ta.track_id = t.track_id AND ta.role = 'primary'
               )""",
        )
        if _table_exists(conn, "artists"):
            relationships["tracks_missing_artist_count"] = _count(
                conn,
                """SELECT COUNT(*) FROM tracks t
                   LEFT JOIN artists a ON a.artist_id = t.artist_id
                  WHERE a.artist_id IS NULL""",
            )
            relationships["orphan_track_artist_artist_count"] = _count(
                conn,
                """SELECT COUNT(*) FROM track_artists ta
                   LEFT JOIN artists a ON a.artist_id = ta.artist_id
                  WHERE a.artist_id IS NULL""",
            )
            relationships["orphan_track_artist_track_count"] = _count(
                conn,
                """SELECT COUNT(*) FROM track_artists ta
                   LEFT JOIN tracks t ON t.track_id = ta.track_id
                  WHERE t.track_id IS NULL""",
            )
            if _table_exists(conn, "plays"):
                relationships["affected_play_count_tracks_missing_artist"] = _count(
                    conn,
                    """SELECT COUNT(*) FROM plays p
                       JOIN tracks t ON t.track_id = p.track_id
                       LEFT JOIN artists a ON a.artist_id = t.artist_id
                      WHERE a.artist_id IS NULL""",
                )
                relationships["affected_play_count_without_primary_credit"] = _count(
                    conn,
                    """SELECT COUNT(*) FROM plays p
                       JOIN tracks t ON t.track_id = p.track_id
                      WHERE NOT EXISTS (
                        SELECT 1 FROM track_artists ta
                         WHERE ta.track_id = t.track_id AND ta.role = 'primary'
                      )""",
                )
    if _table_exists(conn, "albums") and _table_exists(conn, "artists"):
        relationships["albums_missing_artist_count"] = _count(
            conn,
            """SELECT COUNT(*) FROM albums al
               LEFT JOIN artists a ON a.artist_id = al.artist_id
              WHERE a.artist_id IS NULL""",
        )
        if _table_exists(conn, "plays"):
            relationships["affected_play_count_albums_missing_artist"] = _count(
                conn,
                """SELECT COUNT(*) FROM plays p
                   JOIN albums al ON al.album_id = p.source_album_id
                   LEFT JOIN artists a ON a.artist_id = al.artist_id
                  WHERE a.artist_id IS NULL""",
            )
    if (
        _table_exists(conn, "tracks")
        and _table_exists(conn, "albums")
        and _column_exists(conn, "tracks", "album_id")
    ):
        relationships["tracks_missing_album_count"] = _count(
            conn,
            """SELECT COUNT(*) FROM tracks t
               LEFT JOIN albums al ON al.album_id = t.album_id
              WHERE t.album_id IS NOT NULL AND al.album_id IS NULL""",
        )
        if _table_exists(conn, "plays"):
            relationships["affected_play_count_tracks_missing_album"] = _count(
                conn,
                """SELECT COUNT(*) FROM plays p
                   JOIN tracks t ON t.track_id = p.track_id
                   LEFT JOIN albums al ON al.album_id = t.album_id
                  WHERE t.album_id IS NOT NULL AND al.album_id IS NULL""",
            )
    return relationships


def _build_derived_health(conn: sqlite3.Connection) -> dict[str, Any]:
    tables = (
        ("agg_weekly_tracks", "weekly_track_rows"),
        ("agg_weekly_albums", "weekly_album_rows"),
        ("agg_weekly_artists", "weekly_artist_rows"),
        ("album_projects", "album_project_count"),
    )
    derived: dict[str, Any] = {
        key: _count(conn, f"SELECT COUNT(*) FROM {table}") if _table_exists(conn, table) else 0
        for table, key in tables
    }
    derived["rebuild_pending"] = _setting_bool(conn, "rebuild_pending")
    derived["artist_identity"] = _state_snapshot(conn, "artist_identity_state")
    derived["track_credits"] = _state_snapshot(conn, "track_credit_state")
    identity_tables_ready = all(
        _table_exists(conn, table)
        for table in (
            "track_l1_identities",
            "track_l1_external_ids",
            "track_l1_source_links",
            "track_identity_state",
        )
    )
    identity_required = any(
        _table_exists(conn, table)
        for table in (
            "track_l1_identities",
            "track_l1_external_ids",
            "track_l1_source_links",
            "track_identity_state",
        )
    )
    if identity_tables_ready:
        from backend.domains.metadata.track_identity import (
            validate_track_identity_invariants,
        )

        identity_health = validate_track_identity_invariants(conn)
        state = conn.execute(
            """SELECT current_revision, policy_version
                 FROM track_identity_state WHERE state_id=1"""
        ).fetchone()
        active_group_scope_overlap_count = (
            _count(
                conn,
                """SELECT COUNT(*) FROM (
                       SELECT members.l1_id, groups.scope
                         FROM track_group_l1_members members
                         JOIN track_groups groups ON groups.group_id=members.group_id
                        WHERE groups.group_status='active'
                        GROUP BY members.l1_id, groups.scope
                       HAVING COUNT(DISTINCT groups.group_id)>1
                   )""",
            )
            if _table_exists(conn, "track_group_l1_members") and _table_exists(conn, "track_groups")
            else 0
        )
        derived["canonical_track_identity"] = {
            "required": True,
            "available": True,
            "current_revision": int(state[0]) if state else 0,
            "policy_version": str(state[1]) if state else None,
            "duplicate_external_owner_count": identity_health.duplicate_spotify_identity_count,
            "unresolved_play_identity_count": identity_health.unresolved_play_identity_count,
            "source_link_orphan_count": identity_health.source_link_orphan_count,
            "representative_missing_count": identity_health.representative_missing_count,
            "external_owner_orphan_count": identity_health.external_owner_orphan_count,
            "active_group_noncanonical_member_count": (
                identity_health.active_group_noncanonical_member_count
            ),
            "active_group_too_small_count": identity_health.active_group_too_small_count,
            "active_group_invalid_primary_count": (
                identity_health.active_group_invalid_primary_count
            ),
            "pending_candidate_noncanonical_reference_count": (
                identity_health.pending_candidate_noncanonical_reference_count
            ),
            "active_group_scope_overlap_count": active_group_scope_overlap_count,
        }
    else:
        derived["canonical_track_identity"] = {
            "required": identity_required,
            "available": False,
            "current_revision": 0,
            "policy_version": None,
            "duplicate_external_owner_count": 0,
            "unresolved_play_identity_count": 0,
            "source_link_orphan_count": 0,
            "representative_missing_count": 0,
            "external_owner_orphan_count": 0,
            "active_group_noncanonical_member_count": 0,
            "active_group_too_small_count": 0,
            "active_group_invalid_primary_count": 0,
            "pending_candidate_noncanonical_reference_count": 0,
            "active_group_scope_overlap_count": 0,
        }
    derived["album_projects_ready"] = derived["album_project_count"] > 0
    derived["billboard_aggregates_ready"] = bool(
        derived["weekly_track_rows"]
        or derived["weekly_album_rows"]
        or derived["weekly_artist_rows"]
    )
    derived["stale_revision_count"] = sum(
        1
        for state in (derived["artist_identity"], derived["track_credits"])
        if state["current_revision"] != state["active_aggregate_revision"]
        or state["rebuild_status"] != "ready"
    )
    return derived


def _build_health_issues(
    database: dict[str, Any],
    relationships: dict[str, int],
    metadata: dict[str, Any],
    derived: dict[str, Any],
) -> list[dict[str, Any]]:
    """Turn raw checks into a small, actionable issue list for the UI."""
    issues: list[dict[str, Any]] = []

    def add(
        *,
        code: str,
        category: str,
        severity: str,
        title: str,
        count: int,
        affected_play_count: int = 0,
        impact: str,
        recommended_action: str,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        blocking_codes = {
            "no_play_records",
            "sqlite_integrity_failed",
            "orphan_play_tracks",
            "orphan_play_albums",
            "canonical_track_identity_invalid",
        }
        if code in blocking_codes:
            impact_scope = "current_stats"
            user_status = "blocking"
            action = "review"
        elif code == "audio_without_track":
            impact_scope = "source_exclusion"
            user_status = "info"
            action = "no_action"
        elif code == "foreign_key_orphans":
            impact_scope = "non_music"
            user_status = "maintenance"
            action = "preview_cleanup"
        elif category == "relationship" and affected_play_count == 0:
            impact_scope = "historical_only"
            user_status = "maintenance"
            action = "preview_cleanup"
        elif category in {"metadata", "derived"}:
            impact_scope = "current_stats" if affected_play_count else "historical_only"
            user_status = "action_required" if severity in {"critical", "high"} else "maintenance"
            action = "retry" if category == "derived" else "review"
        else:
            impact_scope = "current_stats"
            user_status = "action_required"
            action = "review"
        issues.append(
            {
                "code": code,
                "category": category,
                "severity": severity,
                "title": title,
                "count": int(count),
                "affected_play_count": int(affected_play_count),
                "impact": impact,
                "recommended_action": recommended_action,
                "evidence": evidence or {},
                "impact_scope": impact_scope,
                "user_status": user_status,
                "user_title": title,
                "user_explanation": impact,
                "action": action,
            }
        )

    if database["play_count"] == 0:
        add(
            code="no_play_records",
            category="database",
            severity="critical",
            title="数据库中没有播放记录",
            count=0,
            impact="无法生成播放统计、排行或年度总结。",
            recommended_action="先通过导入前检查确认 Streaming History 文件，再执行串流数据导入。",
        )
    if database["sqlite_integrity"] != "ok":
        add(
            code="sqlite_integrity_failed",
            category="database",
            severity="critical",
            title="SQLite 完整性检查未通过",
            count=1,
            impact="数据库文件可能存在结构损坏，当前统计结果不应视为可信。",
            recommended_action="暂停导入和重建，先备份数据库并执行 SQLite 文件恢复检查。",
            evidence={"sqlite_integrity": database["sqlite_integrity"]},
        )

    for key, code, title, action in (
        (
            "orphan_play_track_count",
            "orphan_play_tracks",
            "播放记录引用了不存在的曲目",
            "先修复播放记录与曲目的关系，再继续导入或重建聚合。",
        ),
        (
            "orphan_play_album_count",
            "orphan_play_albums",
            "播放记录引用了不存在的专辑",
            "先修复播放记录与专辑的关系，再继续导入或重建聚合。",
        ),
    ):
        count = relationships[key]
        if count:
            add(
                code=code,
                category="relationship",
                severity="critical",
                title=title,
                count=count,
                affected_play_count=count,
                impact="会直接影响对应曲目/专辑的播放统计和下游排行。",
                recommended_action=action,
            )

    relationship_issue_specs = (
        (
            "tracks_missing_artist_count",
            "artist_dimension_orphans",
            "曲目引用了不存在的艺人实体",
            "high" if relationships["affected_play_count_tracks_missing_artist"] else "medium",
            "不会影响当前播放统计"
            if relationships["affected_play_count_tracks_missing_artist"] == 0
            else "会影响部分播放记录的艺人归属。",
            "先导出缺失艺人样本，确认是历史残留还是身份治理迁移，再做可回滚修复。",
            {
                "affected_play_count": relationships["affected_play_count_tracks_missing_artist"],
                "track_credit_orphans": relationships["orphan_track_artist_artist_count"],
                "foreign_key_rows": database["foreign_key_issue_breakdown"].get(
                    "tracks -> artists", 0
                ),
                "track_credit_foreign_key_rows": database["foreign_key_issue_breakdown"].get(
                    "track_artists -> artists", 0
                ),
            },
        ),
        (
            "albums_missing_artist_count",
            "album_artist_dimension_orphans",
            "专辑引用了不存在的艺人实体",
            "high" if relationships["affected_play_count_albums_missing_artist"] else "medium",
            "不会影响当前播放统计"
            if relationships["affected_play_count_albums_missing_artist"] == 0
            else "会影响部分播放记录的专辑艺人归属。",
            "先导出缺失艺人样本，确认来源后再做可回滚修复。",
            {"affected_play_count": relationships["affected_play_count_albums_missing_artist"]},
        ),
        (
            "tracks_missing_album_count",
            "track_album_dimension_orphans",
            "曲目引用了不存在的专辑实体",
            "high" if relationships["affected_play_count_tracks_missing_album"] else "medium",
            "不会影响当前播放统计"
            if relationships["affected_play_count_tracks_missing_album"] == 0
            else "会影响部分播放记录的专辑统计。",
            "先确认专辑是否是已删除的历史维度，再进行可回滚修复。",
            {"affected_play_count": relationships["affected_play_count_tracks_missing_album"]},
        ),
    )
    for (
        count_key,
        code,
        title,
        severity,
        impact,
        action,
        evidence,
    ) in relationship_issue_specs:
        count = relationships[count_key]
        if count:
            add(
                code=code,
                category="relationship",
                severity=severity,
                title=title,
                count=count,
                affected_play_count=evidence.get("affected_play_count", 0),
                impact=impact,
                recommended_action=action,
                evidence=evidence,
            )

    explicit_foreign_key_relations = {
        "tracks -> artists",
        "track_artists -> artists",
        "albums -> artists",
        "tracks -> albums",
    }
    secondary_foreign_key_breakdown = {
        key: count
        for key, count in database["foreign_key_issue_breakdown"].items()
        if key not in explicit_foreign_key_relations
    }
    if secondary_foreign_key_breakdown:
        secondary_foreign_key_count = sum(secondary_foreign_key_breakdown.values())
        add(
            code="foreign_key_orphans",
            category="relationship",
            severity="medium",
            title="数据库存在其他历史外键关系残留",
            count=secondary_foreign_key_count,
            affected_play_count=0,
            impact="这些任务记录或会话记录残留当前未连接到播放事实，核心播放统计暂未受到直接影响。",
            recommended_action="先保留数据库不变，导出关系明细和样本；确认来源后再设计可回滚清理任务。",
            evidence=secondary_foreign_key_breakdown,
        )

    if relationships["tracks_without_primary_credit_count"]:
        add(
            code="tracks_without_primary_credit",
            category="relationship",
            severity="high"
            if relationships["affected_play_count_without_primary_credit"]
            else "medium",
            title="曲目缺少主艺人署名",
            count=relationships["tracks_without_primary_credit_count"],
            affected_play_count=relationships["affected_play_count_without_primary_credit"],
            impact="可能导致艺人排行、流派和语言统计漏计或归属不完整。",
            recommended_action="通过音乐源数据管理补齐有效曲目署名，不要直接改写原始播放事实。",
        )

    if database["negative_duration_count"]:
        add(
            code="negative_duration",
            category="database",
            severity="medium",
            title="存在负播放时长记录",
            count=database["negative_duration_count"],
            affected_play_count=database["negative_duration_count"],
            impact="会污染播放时长和有效播放判定。",
            recommended_action="保留原始记录，后续在有效播放过滤层明确排除并保留审计数量。",
        )
    if database["null_track_audio_count"]:
        add(
            code="audio_without_track",
            category="database",
            severity="low",
            title="音频播放记录缺少曲目",
            count=database["null_track_audio_count"],
            affected_play_count=database["null_track_audio_count"],
            impact="这些记录无法进入曲目、艺人或专辑排行；其中一部分可能是 Spotify 无曲目元数据的记录。",
            recommended_action="先按原始字段和 content_type 分层确认，不要仅凭数量自动删除。",
        )

    if metadata.get("unresolved_recent_tracks"):
        add(
            code="unresolved_recent_tracks",
            category="metadata",
            severity="medium",
            title="近期曲目缺少 Spotify 元数据",
            count=metadata["unresolved_recent_tracks"],
            impact="近期曲目可能缺少封面、专辑和外部元数据，影响详情页和年度展示。",
            recommended_action="运行现有的 Spotify 元数据维护流程，并在外部服务不可用时保留 partial 状态。",
            evidence={"since_date": metadata["since_date"]},
        )
    if metadata.get("unresolved_recent_albums"):
        add(
            code="unresolved_recent_albums",
            category="metadata",
            severity="medium",
            title="近期专辑缺少 Album Project",
            count=metadata["unresolved_recent_albums"],
            impact="专辑榜、专辑详情和发行项目统计可能无法完整归并。",
            recommended_action="运行现有 Album Project 维护流程，完成后重新检查健康报告。",
            evidence={"since_date": metadata["since_date"]},
        )

    if derived["rebuild_pending"] or derived["stale_revision_count"]:
        add(
            code="derived_revision_stale",
            category="derived",
            severity="high",
            title="派生统计或元数据 revision 尚未同步",
            count=max(derived["stale_revision_count"], 1 if derived["rebuild_pending"] else 0),
            impact="页面可能继续读取旧的聚合结果，与当前治理事实不一致。",
            recommended_action="等待当前 Job 完成；若持续 stale，再执行受控的 shadow rebuild。",
            evidence={
                "rebuild_pending": derived["rebuild_pending"],
                "stale_revision_count": derived["stale_revision_count"],
            },
        )
    canonical = derived["canonical_track_identity"]
    canonical_problem_count = sum(
        int(canonical[key])
        for key in (
            "duplicate_external_owner_count",
            "unresolved_play_identity_count",
            "source_link_orphan_count",
            "representative_missing_count",
            "external_owner_orphan_count",
            "active_group_scope_overlap_count",
        )
    )
    if (canonical["required"] and not canonical["available"]) or canonical_problem_count:
        add(
            code="canonical_track_identity_invalid",
            category="relationship",
            severity="critical",
            title="基础曲目身份唯一性未通过",
            count=max(canonical_problem_count, 1),
            impact="同一个 Spotify Track ID 可能被重复计入，或 L2/L3 分组可能产生多重归属。",
            recommended_action="停止发布派生统计，先修复外部 ID 唯一归属、来源映射和同层级分组冲突。",
            evidence=canonical,
        )
    if database["play_count"] and not derived["billboard_aggregates_ready"]:
        add(
            code="billboard_aggregates_empty",
            category="derived",
            severity="high",
            title="存在播放记录，但 Billboard 预聚合为空",
            count=database["play_count"],
            affected_play_count=database["play_count"],
            impact="Billboard 页面可能显示空结果或与播放记录不一致。",
            recommended_action="先确认导入维护 Job 状态，再执行受控聚合重建。",
        )

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(issues, key=lambda issue: (severity_order[issue["severity"]], issue["code"]))


def build_import_health_report(
    conn: sqlite3.Connection,
    since_date: str | None = None,
) -> dict[str, Any]:
    """Build a compact, read-only report while keeping legacy flat keys."""

    effective_since_date = since_date or (
        _default_since_date(conn) if _table_exists(conn, "plays") else "1900-01-01"
    )
    database = _build_database_health(conn)
    relationships = _build_relationship_health(conn)
    derived = _build_derived_health(conn)

    row = (
        conn.execute(
            """
        WITH recent_plays AS (
          SELECT p.play_id, p.track_id, p.source_album_id, p.spotify_track_id_at_play
          FROM plays p
          WHERE p.ts_date > ?
            AND p.content_type = 'audio'
            AND p.track_id IS NOT NULL
        ),
        recent_tracks AS (
          SELECT DISTINCT
            rp.track_id,
            COALESCE(NULLIF(rp.spotify_track_id_at_play, ''), t.spotify_track_id) AS spotify_track_id
          FROM recent_plays rp
          JOIN tracks t ON t.track_id = rp.track_id
        ),
        recent_albums AS (
          SELECT DISTINCT source_album_id AS album_id
          FROM recent_plays
          WHERE source_album_id IS NOT NULL
        )
        SELECT
          (SELECT COUNT(*) FROM recent_plays) AS recent_plays,
          (SELECT COUNT(*) FROM recent_tracks) AS recent_tracks,
          (SELECT COUNT(*) FROM recent_albums) AS recent_source_albums,
          (SELECT COUNT(*)
             FROM recent_tracks rt
             LEFT JOIN spotify_track_meta stm ON stm.spotify_track_id = rt.spotify_track_id
             LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = stm.spotify_album_id
            WHERE stm.spotify_track_id IS NULL OR sam.spotify_album_id IS NULL
               OR COALESCE(sam.image_url, '') = '') AS unresolved_recent_tracks
        """,
            (effective_since_date,),
        ).fetchone()
        if _table_exists(conn, "plays")
        else None
    )
    metadata: dict[str, Any] = (
        {key: int(row[key] or 0) for key in row.keys()}
        if row
        else {
            "recent_plays": 0,
            "recent_tracks": 0,
            "recent_source_albums": 0,
            "unresolved_recent_tracks": 0,
        }
    )
    metadata.update(_recent_album_project_health(conn, effective_since_date))
    metadata["since_date"] = effective_since_date

    blockers: list[str] = []
    warnings: list[str] = []
    if database["play_count"] == 0:
        blockers.append("数据库中没有播放记录")
    if database["sqlite_integrity"] != "ok":
        blockers.append(f"SQLite 完整性检查结果为 {database['sqlite_integrity']}")
    if relationships["orphan_play_track_count"] or relationships["orphan_play_album_count"]:
        blockers.append("播放记录引用了不存在的曲目或专辑")
    canonical = derived["canonical_track_identity"]
    canonical_problem_count = sum(
        int(canonical[key])
        for key in (
            "duplicate_external_owner_count",
            "unresolved_play_identity_count",
            "source_link_orphan_count",
            "representative_missing_count",
            "external_owner_orphan_count",
            "active_group_scope_overlap_count",
        )
    )
    if canonical["required"] and not canonical["available"]:
        blockers.append("基础曲目身份表缺失")
    elif canonical_problem_count:
        blockers.append(f"基础曲目身份唯一性检查发现 {canonical_problem_count} 个问题")
    if database["foreign_key_issue_count"]:
        breakdown = database["foreign_key_issue_breakdown"]
        top_issues = "、".join(f"{key} {count} 条" for key, count in list(breakdown.items())[:3])
        warnings.append(
            f"发现 {database['foreign_key_issue_count']} 个数据库外键关系问题"
            + (f"（主要是：{top_issues}）" if top_issues else "")
        )
    if database["negative_duration_count"]:
        warnings.append(f"发现 {database['negative_duration_count']} 条负播放时长记录")
    if database["null_track_audio_count"]:
        warnings.append(f"发现 {database['null_track_audio_count']} 条无曲目音频记录")
    for key, label in (
        ("tracks_without_primary_credit_count", "曲目缺少主艺人署名"),
        ("orphan_track_artist_track_count", "曲目署名引用了不存在的曲目"),
        ("orphan_track_artist_artist_count", "曲目署名引用了不存在的艺人"),
        ("unresolved_recent_tracks", "近期曲目缺少 Spotify 元数据"),
        ("unresolved_recent_albums", "近期专辑缺少 Album Project"),
    ):
        count = relationships.get(key, metadata.get(key, 0))
        if count:
            warnings.append(f"{label}：{count} 个")
    if derived["rebuild_pending"] or derived["stale_revision_count"]:
        warnings.append("部分派生统计或元数据 revision 尚未同步")
    if database["play_count"] and not derived["billboard_aggregates_ready"]:
        warnings.append("存在播放记录，但 Billboard 预聚合为空")

    issues = _build_health_issues(database, relationships, metadata, derived)

    if blockers:
        status = "blocked"
    elif derived["rebuild_pending"] or derived["stale_revision_count"]:
        status = "stale"
    elif warnings:
        status = "partial"
    else:
        status = "healthy"

    safe_to_use = not blockers
    historical_issue_count = sum(
        1 for issue in issues if issue["impact_scope"] in {"historical_only", "non_music"}
    )
    current_stats_issues = [issue for issue in issues if issue["impact_scope"] == "current_stats"]
    informational_count = sum(1 for issue in issues if issue["user_status"] == "info")
    if not safe_to_use:
        headline = "当前统计需要先处理关键问题"
    elif current_stats_issues:
        headline = "核心统计可用，但有数据项需要复核"
    elif historical_issue_count:
        headline = "核心统计正常，有历史数据可整理"
    else:
        headline = "数据状态良好，核心统计可以正常使用"
    summary = {
        "safe_to_use": safe_to_use,
        "headline": headline,
        "current_stats_issue_count": len(current_stats_issues),
        "current_stats_affected_play_count": sum(
            int(issue["affected_play_count"]) for issue in current_stats_issues
        ),
        "historical_issue_count": historical_issue_count,
        "informational_count": informational_count,
        "recommended_action": (
            "先处理阻断问题，再重新检查"
            if not safe_to_use
            else "可继续使用；历史残留可在方便时预览整理"
            if historical_issue_count
            else "无需操作"
        ),
    }

    return {
        "status": status,
        "database": database,
        "relationships": relationships,
        "metadata": metadata,
        "derived": derived,
        "summary": summary,
        "issues": issues,
        "blockers": blockers,
        "warnings": warnings,
        # Compatibility for the existing maintenance response and tests.
        **metadata,
        "unresolved_recent_tracks": metadata.get("unresolved_recent_tracks", 0),
        "unresolved_recent_albums": metadata.get("unresolved_recent_albums", 0),
    }


def _sample_rows(
    conn: sqlite3.Connection,
    sql: str,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    cursor = conn.execute(sql, (limit,))
    columns = [str(item[0]) for item in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def build_import_cleanup_preview(
    conn: sqlite3.Connection,
    *,
    sample_limit: int = 20,
) -> dict[str, Any]:
    """Build a bounded, read-only cleanup plan for historical relationship rows."""

    health = build_import_health_report(conn)
    issue_by_code = {issue["code"]: issue for issue in health["issues"]}
    sample_queries = {
        "artist_dimension_orphans": """SELECT t.track_id, t.track_name, t.artist_id,
                   COUNT(p.play_id) AS current_play_count
              FROM tracks t
              LEFT JOIN artists a ON a.artist_id=t.artist_id
              LEFT JOIN plays p ON p.track_id=t.track_id
             WHERE a.artist_id IS NULL
             GROUP BY t.track_id
             ORDER BY current_play_count DESC, t.track_id
             LIMIT ?""",
        "album_artist_dimension_orphans": """SELECT al.album_id, al.album_name, al.artist_id,
                   COUNT(p.play_id) AS current_play_count
              FROM albums al
              LEFT JOIN artists a ON a.artist_id=al.artist_id
              LEFT JOIN plays p ON p.source_album_id=al.album_id
             WHERE a.artist_id IS NULL
             GROUP BY al.album_id
             ORDER BY current_play_count DESC, al.album_id
             LIMIT ?""",
        "track_album_dimension_orphans": """SELECT t.track_id, t.track_name, t.album_id,
                   COUNT(p.play_id) AS current_play_count
              FROM tracks t
              LEFT JOIN albums al ON al.album_id=t.album_id
              LEFT JOIN plays p ON p.track_id=t.track_id
             WHERE t.album_id IS NOT NULL AND al.album_id IS NULL
             GROUP BY t.track_id
             ORDER BY current_play_count DESC, t.track_id
             LIMIT ?""",
    }
    groups: list[dict[str, Any]] = []
    for issue_code, query in sample_queries.items():
        issue = issue_by_code.get(issue_code)
        if not issue:
            continue
        groups.append(
            {
                "issue_code": issue_code,
                "title": issue["title"],
                "count": issue["count"],
                "affected_play_count": issue["affected_play_count"],
                "proposed_action": issue["recommended_action"],
                "automatic_cleanup_allowed": False,
                "samples": _sample_rows(conn, query, limit=sample_limit),
            }
        )
    secondary_issue = issue_by_code.get("foreign_key_orphans")
    if secondary_issue:
        explicit = {
            "tracks -> artists",
            "track_artists -> artists",
            "albums -> artists",
            "tracks -> albums",
        }
        samples = [
            {"child_table": str(row[0]), "row_id": row[1], "parent_table": str(row[2])}
            for row in conn.execute("PRAGMA foreign_key_check").fetchall()
            if f"{row[0]} -> {row[2]}" not in explicit
        ][:sample_limit]
        groups.append(
            {
                "issue_code": "foreign_key_orphans",
                "title": secondary_issue["title"],
                "count": secondary_issue["count"],
                "affected_play_count": 0,
                "proposed_action": secondary_issue["recommended_action"],
                "automatic_cleanup_allowed": False,
                "samples": samples,
            }
        )
    revision_row = conn.execute("PRAGMA data_version").fetchone()
    database_revision = str(revision_row[0] if revision_row else 0)
    token_payload = {
        "database_revision": database_revision,
        "groups": [
            {"issue_code": group["issue_code"], "count": group["count"]} for group in groups
        ],
    }
    preview_token = hashlib.sha256(
        json.dumps(token_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "status": "ready",
        "database_revision": database_revision,
        "preview_token": preview_token,
        "writes_performed": False,
        "groups": groups,
        "excluded_issue_codes": ["audio_without_track"],
    }
