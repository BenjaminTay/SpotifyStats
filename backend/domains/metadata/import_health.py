"""Read-only health checks for imported and derived Spotify data."""

from __future__ import annotations

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
        ),
        recent_album_state AS (
          SELECT
            ra.album_id,
            COUNT(DISTINCT rp.track_id) AS local_tracks,
            MAX(CASE WHEN sam.album_type = 'album' THEN 1 ELSE 0 END) AS has_album_type
          FROM recent_albums ra
          LEFT JOIN recent_plays rp ON rp.source_album_id = ra.album_id
          LEFT JOIN album_spotify_links asl ON asl.album_id = ra.album_id
          LEFT JOIN spotify_album_meta sam ON sam.spotify_album_id = asl.spotify_album_id
          GROUP BY ra.album_id
        ),
        project_candidate_albums AS (
          SELECT album_id
          FROM recent_album_state
          WHERE has_album_type = 1 OR local_tracks >= 7
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
               OR COALESCE(sam.image_url, '') = '') AS unresolved_recent_tracks,
          (SELECT COUNT(*)
             FROM project_candidate_albums pca
             LEFT JOIN album_project_albums apa ON apa.album_id = pca.album_id
            WHERE apa.album_id IS NULL) AS unresolved_recent_albums
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
            "unresolved_recent_albums": 0,
        }
    )
    metadata["since_date"] = effective_since_date

    blockers: list[str] = []
    warnings: list[str] = []
    if database["play_count"] == 0:
        blockers.append("数据库中没有播放记录")
    if database["sqlite_integrity"] != "ok":
        blockers.append(f"SQLite 完整性检查结果为 {database['sqlite_integrity']}")
    if relationships["orphan_play_track_count"] or relationships["orphan_play_album_count"]:
        blockers.append("播放记录引用了不存在的曲目或专辑")
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

    return {
        "status": status,
        "database": database,
        "relationships": relationships,
        "metadata": metadata,
        "derived": derived,
        "issues": issues,
        "blockers": blockers,
        "warnings": warnings,
        # Compatibility for the existing maintenance response and tests.
        **metadata,
        "unresolved_recent_tracks": metadata.get("unresolved_recent_tracks", 0),
        "unresolved_recent_albums": metadata.get("unresolved_recent_albums", 0),
    }
