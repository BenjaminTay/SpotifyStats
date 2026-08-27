"""Preview and explicitly clean the known pre-enforcement SQLite FK debt.

The maintenance path is intentionally separate from schema migration and
normal imports. It only accepts rows that can be mapped losslessly to an
existing Spotify owner and refuses to run when the preview revision changes.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

from backend.core.db import enforce_sqlite_foreign_keys

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SUPPORTED_VIOLATIONS = {
    ("tracks", "artists"),
    ("tracks", "albums"),
    ("track_artists", "artists"),
    ("albums", "artists"),
    ("ai_task_events", "ai_task_runs"),
    ("ai_tool_calls", "ai_task_runs"),
    ("chat_messages", "chat_sessions"),
}
_ALLOWED_TRACK_REFERENCES = {
    ("track_artists", "track_id"),
    ("track_group_members", "track_id"),
    ("track_l1_identities", "fallback_track_id"),
    ("track_l1_identities", "representative_track_id"),
    ("track_l1_source_links", "track_id"),
}
_ALLOWED_IDENTITY_REFERENCES = {
    ("track_l1_source_links", "l1_id"),
}


class HistoricalForeignKeyCleanupError(RuntimeError):
    """The historical debt is unsafe to clean automatically."""


def _quote(identifier: str) -> str:
    if not _IDENTIFIER.fullmatch(identifier):
        raise ValueError(f"unsafe SQLite identifier: {identifier!r}")
    return f'"{identifier}"'


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def _foreign_key_violations(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {
            "table": str(row[0]),
            "rowid": int(row[1]),
            "parent": str(row[2]),
            "fkid": int(row[3]),
        }
        for row in conn.execute("PRAGMA foreign_key_check").fetchall()
    ]


def _ids_clause(values: Sequence[int]) -> tuple[str, tuple[int, ...]]:
    if not values:
        return "(NULL)", ()
    return f"({','.join('?' for _ in values)})", tuple(int(value) for value in values)


def _referencing_columns(conn: sqlite3.Connection, parent_table: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    tables = [
        str(row[0])
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]
    for table in tables:
        for fk in conn.execute(f"PRAGMA foreign_key_list({_quote(table)})").fetchall():
            if str(fk[2]) == parent_table:
                result.append((table, str(fk[3])))
    return result


def _reference_counts(
    conn: sqlite3.Connection,
    parent_table: str,
    ids: Sequence[int],
) -> dict[tuple[str, str], int]:
    clause, params = _ids_clause(ids)
    return {
        (table, column): int(
            conn.execute(
                f"SELECT COUNT(*) FROM {_quote(table)} WHERE {_quote(column)} IN {clause}",
                params,
            ).fetchone()[0]
        )
        for table, column in _referencing_columns(conn, parent_table)
    }


def _play_totals(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute("SELECT COUNT(*), COALESCE(SUM(ms_played), 0) FROM plays").fetchone()
    return {"rows": int(row[0]), "milliseconds": int(row[1])}


def _schema_revision(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "schema_migrations"):
        return 0
    return int(
        conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
    )


def _plan_token(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:24]


def build_cleanup_plan(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return a deterministic, read-only plan and all blocking conditions."""

    violations = _foreign_key_violations(conn)
    blockers: list[str] = []
    unsupported = sorted(
        {
            (item["table"], item["parent"])
            for item in violations
            if (item["table"], item["parent"]) not in _SUPPORTED_VIOLATIONS
        }
    )
    if unsupported:
        blockers.append(f"存在未登记的外键违规类型: {unsupported}")

    stale_track_ids = sorted(
        {
            int(item["rowid"])
            for item in violations
            if item["table"] == "tracks" and item["parent"] in {"artists", "albums"}
        }
    )
    mappings: list[dict[str, Any]] = []
    for track_id in stale_track_ids:
        track = conn.execute(
            """SELECT track_id, track_name, artist_id, album_id, spotify_track_id
                 FROM tracks WHERE track_id=?""",
            (track_id,),
        ).fetchone()
        if track is None:
            blockers.append(f"待清理 Track {track_id} 已不存在")
            continue
        spotify_track_id = str(track[4] or "").strip()
        owners = conn.execute(
            """SELECT owners.track_id
                 FROM spotify_track_owners owners
                 JOIN tracks owner_track ON owner_track.track_id=owners.track_id
                 JOIN artists owner_artist ON owner_artist.artist_id=owner_track.artist_id
                WHERE owners.spotify_track_id=?""",
            (spotify_track_id,),
        ).fetchall()
        owner_ids = sorted({int(row[0]) for row in owners if int(row[0]) != track_id})
        direct_plays = int(
            conn.execute("SELECT COUNT(*) FROM plays WHERE track_id=?", (track_id,)).fetchone()[0]
        )
        if direct_plays:
            blockers.append(f"Track {track_id} 仍有 {direct_plays} 条直接播放")
        if not spotify_track_id:
            blockers.append(f"Track {track_id} 缺少 Spotify ID")
        if len(owner_ids) != 1:
            blockers.append(f"Track {track_id} 的有效 Spotify owner 数量为 {len(owner_ids)}")
            continue
        owner_id = owner_ids[0]
        if owner_id in stale_track_ids:
            blockers.append(f"Track {track_id} 的 owner {owner_id} 也在待删除范围")
            continue
        owner_plays = int(
            conn.execute("SELECT COUNT(*) FROM plays WHERE track_id=?", (owner_id,)).fetchone()[0]
        )
        if not owner_plays:
            blockers.append(f"Track {track_id} 的 owner {owner_id} 没有直接播放证据")
            continue
        mappings.append(
            {
                "alias_track_id": track_id,
                "canonical_track_id": owner_id,
                "spotify_track_id": spotify_track_id,
                "track_name": str(track[1]),
                "album_id": int(track[3]) if track[3] is not None else None,
            }
        )

    mapped_ids = [item["alias_track_id"] for item in mappings]
    if mapped_ids != stale_track_ids:
        blockers.append("并非每个异常 Track 都能无损映射到唯一 Spotify owner")

    track_refs = _reference_counts(conn, "tracks", stale_track_ids)
    unexpected_track_refs = {
        f"{table}.{column}": count
        for (table, column), count in track_refs.items()
        if count and (table, column) not in _ALLOWED_TRACK_REFERENCES
    }
    if unexpected_track_refs:
        blockers.append(f"异常 Track 仍被未登记业务表引用: {unexpected_track_refs}")

    clause, params = _ids_clause(stale_track_ids)
    stale_identity_ids = sorted(
        {
            int(row[0])
            for row in conn.execute(
                f"""SELECT l1_id FROM track_l1_identities
                    WHERE fallback_track_id IN {clause}
                       OR representative_track_id IN {clause}""",
                params + params,
            ).fetchall()
        }
    )
    identity_refs = _reference_counts(conn, "track_l1_identities", stale_identity_ids)
    unexpected_identity_refs = {
        f"{table}.{column}": count
        for (table, column), count in identity_refs.items()
        if count and (table, column) not in _ALLOWED_IDENTITY_REFERENCES
    }
    if unexpected_identity_refs:
        blockers.append(f"异常兼容身份仍被业务表引用: {unexpected_identity_refs}")

    # Source links may point from a stale raw track to a valid owner identity;
    # links whose identity itself is stale require manual interpretation.
    identity_clause, identity_params = _ids_clause(stale_identity_ids)
    stale_identity_source_links = int(
        conn.execute(
            f"SELECT COUNT(*) FROM track_l1_source_links WHERE l1_id IN {identity_clause}",
            identity_params,
        ).fetchone()[0]
    )
    if stale_identity_source_links:
        blockers.append(f"异常兼容身份仍拥有 {stale_identity_source_links} 条来源链接")

    stale_album_ids = sorted(
        {
            int(item["rowid"])
            for item in violations
            if item["table"] == "albums" and item["parent"] == "artists"
        }
    )
    album_refs = _reference_counts(conn, "albums", stale_album_ids)
    album_clause, album_params = _ids_clause(stale_album_ids)
    remaining_album_tracks = int(
        conn.execute(
            f"SELECT COUNT(*) FROM tracks WHERE album_id IN {album_clause} "
            f"AND track_id NOT IN {clause}",
            album_params + params,
        ).fetchone()[0]
    )
    unexpected_album_refs = {
        f"{table}.{column}": count
        for (table, column), count in album_refs.items()
        if count and not (table == "tracks" and column == "album_id")
    }
    if remaining_album_tracks or unexpected_album_refs:
        blockers.append(
            "异常 Album 仍有清理范围外引用: "
            f"tracks={remaining_album_tracks}, others={unexpected_album_refs}"
        )

    orphan_ai_events = [
        int(row[0])
        for row in conn.execute(
            """SELECT event_id FROM ai_task_events events
                WHERE NOT EXISTS (
                    SELECT 1 FROM ai_task_runs runs WHERE runs.task_id=events.task_id
                ) ORDER BY event_id"""
        ).fetchall()
    ]
    orphan_ai_tools = [
        int(row[0])
        for row in conn.execute(
            """SELECT tool_call_id FROM ai_tool_calls calls
                WHERE NOT EXISTS (
                    SELECT 1 FROM ai_task_runs runs WHERE runs.task_id=calls.task_id
                ) ORDER BY tool_call_id"""
        ).fetchall()
    ]
    orphan_chat_messages = [
        int(row[0])
        for row in conn.execute(
            """SELECT id FROM chat_messages messages
                WHERE NOT EXISTS (
                    SELECT 1 FROM chat_sessions sessions WHERE sessions.id=messages.session_id
                ) ORDER BY id"""
        ).fetchall()
    ]

    core = {
        "schema_revision": _schema_revision(conn),
        "foreign_key_violations": violations,
        "play_totals": _play_totals(conn),
        "track_mappings": mappings,
        "stale_identity_ids": stale_identity_ids,
        "stale_album_ids": stale_album_ids,
        "orphan_ai_event_ids": orphan_ai_events,
        "orphan_ai_tool_call_ids": orphan_ai_tools,
        "orphan_chat_message_ids": orphan_chat_messages,
        "reference_counts": {
            "tracks": {f"{t}.{c}": n for (t, c), n in track_refs.items() if n},
            "identities": {f"{t}.{c}": n for (t, c), n in identity_refs.items() if n},
            "albums": {f"{t}.{c}": n for (t, c), n in album_refs.items() if n},
        },
        "blockers": sorted(set(blockers)),
    }
    return {
        **core,
        "status": "ready" if not blockers else "blocked",
        "confirmation_token": _plan_token(core),
        "counts": {
            "foreign_key_violations": len(violations),
            "track_aliases": len(mappings),
            "stale_identities": len(stale_identity_ids),
            "stale_albums": len(stale_album_ids),
            "orphan_ai_rows": len(orphan_ai_events) + len(orphan_ai_tools),
            "orphan_chat_messages": len(orphan_chat_messages),
        },
    }


def _archive_rows(
    conn: sqlite3.Connection,
    run_id: str,
    table: str,
    key_column: str,
    ids: Iterable[int],
) -> None:
    for identifier in ids:
        row = conn.execute(
            f"SELECT * FROM {_quote(table)} WHERE {_quote(key_column)}=?",
            (int(identifier),),
        ).fetchone()
        if row is None:
            continue
        columns = [str(info[1]) for info in conn.execute(f"PRAGMA table_info({_quote(table)})")]
        payload = {column: row[index] for index, column in enumerate(columns)}
        conn.execute(
            """INSERT INTO historical_fk_cleanup_archive(
                   run_id, source_table, source_row_key, row_json
               ) VALUES (?, ?, ?, ?)""",
            (
                run_id,
                table,
                str(identifier),
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )


def _archive_composite_rows(
    conn: sqlite3.Connection,
    run_id: str,
    table: str,
    where_column: str,
    ids: Sequence[int],
) -> None:
    clause, params = _ids_clause(ids)
    columns = [str(info[1]) for info in conn.execute(f"PRAGMA table_info({_quote(table)})")]
    rows = conn.execute(
        f"SELECT * FROM {_quote(table)} WHERE {_quote(where_column)} IN {clause}", params
    ).fetchall()
    for index, row in enumerate(rows):
        payload = {column: row[position] for position, column in enumerate(columns)}
        key = f"{payload.get(where_column)}:{index}"
        conn.execute(
            """INSERT INTO historical_fk_cleanup_archive(
                   run_id, source_table, source_row_key, row_json
               ) VALUES (?, ?, ?, ?)""",
            (
                run_id,
                table,
                key,
                json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
            ),
        )


def apply_cleanup(conn: sqlite3.Connection, confirmation_token: str) -> dict[str, Any]:
    """Apply the exact accepted plan in one fail-closed transaction."""

    enforce_sqlite_foreign_keys(conn)
    if conn.in_transaction:
        raise HistoricalForeignKeyCleanupError("清理连接进入时不得已有事务")
    conn.execute("BEGIN IMMEDIATE")
    try:
        plan = build_cleanup_plan(conn)
        if plan["status"] != "ready":
            raise HistoricalForeignKeyCleanupError(
                "清理预览仍有阻塞项: " + "; ".join(plan["blockers"])
            )
        if confirmation_token != plan["confirmation_token"]:
            raise HistoricalForeignKeyCleanupError(
                "确认令牌与当前数据库修订不一致，请重新执行 --preview"
            )
        if not _table_exists(conn, "track_id_aliases"):
            raise HistoricalForeignKeyCleanupError("数据库尚未应用 migration 59")

        run_id = uuid.uuid4().hex
        conn.execute(
            """INSERT INTO historical_fk_cleanup_runs(
                   run_id, plan_token, status, summary_json
               ) VALUES (?, ?, 'running', ?)""",
            (run_id, confirmation_token, json.dumps(plan["counts"], ensure_ascii=False)),
        )
        mappings = plan["track_mappings"]
        stale_tracks = [int(item["alias_track_id"]) for item in mappings]
        stale_identities = [int(value) for value in plan["stale_identity_ids"]]
        stale_albums = [int(value) for value in plan["stale_album_ids"]]

        _archive_rows(conn, run_id, "tracks", "track_id", stale_tracks)
        _archive_composite_rows(conn, run_id, "track_artists", "track_id", stale_tracks)
        _archive_composite_rows(conn, run_id, "track_group_members", "track_id", stale_tracks)
        _archive_composite_rows(conn, run_id, "track_l1_source_links", "track_id", stale_tracks)
        _archive_rows(conn, run_id, "track_l1_identities", "l1_id", stale_identities)
        _archive_rows(conn, run_id, "albums", "album_id", stale_albums)
        _archive_rows(conn, run_id, "ai_task_events", "event_id", plan["orphan_ai_event_ids"])
        _archive_rows(
            conn,
            run_id,
            "ai_tool_calls",
            "tool_call_id",
            plan["orphan_ai_tool_call_ids"],
        )
        _archive_rows(
            conn,
            run_id,
            "chat_messages",
            "id",
            plan["orphan_chat_message_ids"],
        )

        conn.executemany(
            """INSERT INTO track_id_aliases(alias_track_id, canonical_track_id, reason)
               VALUES (?, ?, 'historical_fk_debt_spotify_owner')""",
            ((int(item["alias_track_id"]), int(item["canonical_track_id"])) for item in mappings),
        )
        for item in mappings:
            alias = int(item["alias_track_id"])
            owner = int(item["canonical_track_id"])
            conn.execute(
                """INSERT OR IGNORE INTO track_group_members(group_id, track_id)
                   SELECT group_id, ? FROM track_group_members WHERE track_id=?""",
                (owner, alias),
            )
        stale_clause, stale_params = _ids_clause(stale_tracks)
        identity_clause, identity_params = _ids_clause(stale_identities)
        album_clause, album_params = _ids_clause(stale_albums)

        conn.execute(
            f"DELETE FROM track_group_members WHERE track_id IN {stale_clause}", stale_params
        )
        conn.execute(
            f"DELETE FROM track_l1_source_links WHERE track_id IN {stale_clause}", stale_params
        )
        conn.execute(f"DELETE FROM track_artists WHERE track_id IN {stale_clause}", stale_params)
        conn.execute(
            f"DELETE FROM track_l1_identities WHERE l1_id IN {identity_clause}",
            identity_params,
        )
        conn.execute(f"DELETE FROM tracks WHERE track_id IN {stale_clause}", stale_params)
        conn.execute(f"DELETE FROM albums WHERE album_id IN {album_clause}", album_params)

        for table, key, ids in (
            ("ai_task_events", "event_id", plan["orphan_ai_event_ids"]),
            ("ai_tool_calls", "tool_call_id", plan["orphan_ai_tool_call_ids"]),
            ("chat_messages", "id", plan["orphan_chat_message_ids"]),
        ):
            delete_clause, delete_params = _ids_clause(ids)
            conn.execute(
                f"DELETE FROM {_quote(table)} WHERE {_quote(key)} IN {delete_clause}",
                delete_params,
            )

        after_violations = _foreign_key_violations(conn)
        if after_violations:
            raise HistoricalForeignKeyCleanupError(f"清理后仍有 {len(after_violations)} 条外键违规")
        after_plays = _play_totals(conn)
        if after_plays != plan["play_totals"]:
            raise HistoricalForeignKeyCleanupError(
                f"播放事实发生变化: before={plan['play_totals']}, after={after_plays}"
            )
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or str(integrity[0]) != "ok":
            raise HistoricalForeignKeyCleanupError(
                f"SQLite integrity_check 失败: {integrity[0] if integrity else None}"
            )

        result = {
            "status": "completed",
            "run_id": run_id,
            "confirmation_token": confirmation_token,
            "counts": plan["counts"],
            "play_totals": after_plays,
            "foreign_key_violations": 0,
            "integrity_check": "ok",
        }
        conn.execute(
            """UPDATE historical_fk_cleanup_runs
                  SET status='completed', summary_json=?, completed_at=datetime('now')
                WHERE run_id=?""",
            (json.dumps(result, ensure_ascii=False, sort_keys=True), run_id),
        )
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
