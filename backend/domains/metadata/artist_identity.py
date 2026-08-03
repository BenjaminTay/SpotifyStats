"""Global, auditable artist identity resolution.

Raw artist, track, credit, and play rows remain immutable.  This module owns the
derived mapping from raw artist ids to one canonical identity and keeps display
choice separate from the canonical key used by statistics.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class ArtistIdentityResolution:
    raw_artist_id: int
    canonical_artist_id: int
    display_artist_id: int
    display_name: str
    identity_id: int | None


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


def get_identity_revision(conn: sqlite3.Connection) -> int:
    if not _table_exists(conn, "artist_identity_state"):
        return 0
    row = conn.execute(
        "SELECT current_revision FROM artist_identity_state WHERE state_id=1"
    ).fetchone()
    return int(row[0]) if row else 0


def get_identity_state(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "artist_identity_state"):
        return {
            "current_revision": 0,
            "active_aggregate_revision": 0,
            "rebuild_status": "ready",
            "last_error": None,
        }
    row = conn.execute(
        """SELECT current_revision, active_aggregate_revision, rebuild_status,
                  last_error, updated_at
           FROM artist_identity_state WHERE state_id=1"""
    ).fetchone()
    return dict(row) if row else {}


def get_artist_identity_map(
    conn: sqlite3.Connection,
) -> dict[int, ArtistIdentityResolution]:
    if not _table_exists(conn, "artists"):
        return {}
    artists = {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT artist_id, artist_name FROM artists").fetchall()
    }
    result = {
        artist_id: ArtistIdentityResolution(
            raw_artist_id=artist_id,
            canonical_artist_id=artist_id,
            display_artist_id=artist_id,
            display_name=name,
            identity_id=None,
        )
        for artist_id, name in artists.items()
    }
    if _table_exists(conn, "artist_identity_groups"):
        rows = conn.execute(
            """SELECT m.artist_id, g.canonical_artist_id,
                      COALESCE(g.display_artist_id, g.canonical_artist_id),
                      g.display_name, g.identity_id
               FROM artist_identity_members m
               JOIN artist_identity_groups g ON g.identity_id=m.identity_id
               WHERE m.active=1 AND g.status='active'"""
        ).fetchall()
        for raw_id, canonical_id, display_id, display_name, identity_id in rows:
            result[int(raw_id)] = ArtistIdentityResolution(
                raw_artist_id=int(raw_id),
                canonical_artist_id=int(canonical_id),
                display_artist_id=int(display_id),
                display_name=str(display_name),
                identity_id=int(identity_id),
            )
        return result

    if _table_exists(conn, "artist_identity_aliases"):
        rows = conn.execute(
            """SELECT ia.alias_artist_id, ia.canonical_artist_id, a.artist_name
               FROM artist_identity_aliases ia
               JOIN artists a ON a.artist_id=ia.canonical_artist_id"""
        ).fetchall()
        for alias_id, canonical_id, display_name in rows:
            result[int(alias_id)] = ArtistIdentityResolution(
                raw_artist_id=int(alias_id),
                canonical_artist_id=int(canonical_id),
                display_artist_id=int(canonical_id),
                display_name=str(display_name),
                identity_id=None,
            )
    return result


def resolve_artist_id(conn: sqlite3.Connection, artist_id: int) -> ArtistIdentityResolution:
    mapping = get_artist_identity_map(conn)
    if artist_id not in mapping:
        raise KeyError(f"Unknown artist id: {artist_id}")
    return mapping[artist_id]


def resolve_artist_name(
    conn: sqlite3.Connection, artist_name: str
) -> ArtistIdentityResolution | None:
    rows = conn.execute(
        "SELECT artist_id FROM artists WHERE lower(artist_name)=lower(?) ORDER BY artist_id",
        (artist_name,),
    ).fetchall()
    if not rows:
        return None
    mapping = get_artist_identity_map(conn)
    return mapping.get(int(rows[0][0]))


def canonicalize_artist_frame(
    frame: pd.DataFrame,
    conn: sqlite3.Connection,
    *,
    dedupe: bool = True,
) -> pd.DataFrame:
    """Resolve fanned-out artist rows and de-duplicate one play per identity."""
    if frame.empty or "artist_id" not in frame.columns:
        return frame
    mapping = get_artist_identity_map(conn)
    if not mapping:
        return frame
    result = frame.copy()
    result["raw_artist_id"] = result["artist_id"]
    if "artist_name" in result.columns:
        result["raw_artist_name"] = result["artist_name"]
    result["artist_id"] = result["raw_artist_id"].map(
        lambda value: (
            mapping.get(int(value), None).canonical_artist_id
            if pd.notna(value) and int(value) in mapping
            else value
        )
    )
    if "artist_name" in result.columns:
        result["artist_name"] = (
            result["raw_artist_id"]
            .map(
                lambda value: (
                    mapping.get(int(value), None).display_name
                    if pd.notna(value) and int(value) in mapping
                    else None
                )
            )
            .fillna(result["artist_name"])
        )
    if dedupe:
        if "_artist_event_id" in result.columns:
            event_columns = ["_artist_event_id"]
        elif "play_id" in result.columns:
            event_columns = ["play_id"]
            # A merged source event can expand back into multiple effective
            # plays.  ``merge_consecutive_plays`` retains the original
            # play_id and distinguishes those rows with _merge_seq, so keep
            # that sequence in the stable event key when available.
            if "_merge_seq" in result.columns:
                event_columns.append("_merge_seq")
        else:
            event_columns = [
                column
                for column in (
                    "ts",
                    "ts_date",
                    "track_id",
                    "source_album_id",
                    "ms_played",
                    "billboard_week",
                )
                if column in result.columns
            ]
        subset = [*event_columns, "artist_id"]
        if len(subset) > 1:
            result = result.drop_duplicates(subset=subset, keep="first")
    return result.reset_index(drop=True)


def canonical_artist_names_for_track(
    conn: sqlite3.Connection, rows: list[tuple[int, int, str]]
) -> dict[int, list[str]]:
    mapping = get_artist_identity_map(conn)
    grouped: dict[int, list[tuple[int, str]]] = {}
    for track_id, artist_id, role in rows:
        resolved = mapping.get(int(artist_id))
        canonical_id = resolved.canonical_artist_id if resolved else int(artist_id)
        display_name = resolved.display_name if resolved else str(artist_id)
        values = grouped.setdefault(int(track_id), [])
        if not any(existing_id == canonical_id for existing_id, _ in values):
            if role == "primary":
                values.insert(0, (canonical_id, display_name))
            else:
                values.append((canonical_id, display_name))
    return {track_id: [name for _, name in values] for track_id, values in grouped.items()}


def _active_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    if not _table_exists(conn, "artist_identity_groups"):
        return {"groups": groups}
    group_columns = {row[1] for row in conn.execute("PRAGMA table_info(artist_identity_groups)")}
    provider_select = (
        "provider_metadata_artist_id"
        if "provider_metadata_artist_id" in group_columns
        else "NULL AS provider_metadata_artist_id"
    )
    for group in conn.execute(
        f"""SELECT identity_id, canonical_artist_id, display_artist_id, display_name,
                  display_source, {provider_select}, status, revision
           FROM artist_identity_groups WHERE status='active' ORDER BY identity_id"""
    ).fetchall():
        item = dict(group)
        item["members"] = [
            dict(row)
            for row in conn.execute(
                """SELECT artist_id, role, evidence_type, evidence_json, confidence
                   FROM artist_identity_members
                   WHERE identity_id=? AND active=1 ORDER BY artist_id""",
                (group["identity_id"],),
            ).fetchall()
        ]
        if _table_exists(conn, "artist_identity_external_ids"):
            for member in item["members"]:
                member["external_ids"] = [
                    dict(row)
                    for row in conn.execute(
                        """SELECT provider, external_id, evidence_type, evidence_source,
                                  confidence, verified
                           FROM artist_identity_external_ids WHERE artist_id=?
                           ORDER BY provider, external_id""",
                        (member["artist_id"],),
                    ).fetchall()
                ]
        groups.append(item)
    return {"groups": groups}


def _sync_legacy_projection(conn: sqlite3.Connection) -> None:
    if not _table_exists(conn, "artist_identity_aliases"):
        return
    conn.execute("DELETE FROM artist_identity_aliases")
    conn.execute(
        """INSERT INTO artist_identity_aliases(alias_artist_id, canonical_artist_id, reason)
           SELECT m.artist_id, g.canonical_artist_id,
                  '由艺人身份组 #' || g.identity_id || ' 管理'
           FROM artist_identity_members m
           JOIN artist_identity_groups g ON g.identity_id=m.identity_id
           WHERE m.active=1 AND g.status='active'
             AND m.artist_id != g.canonical_artist_id"""
    )


def _next_revision(conn: sqlite3.Connection, expected_revision: int) -> int:
    current = get_identity_revision(conn)
    if current != expected_revision:
        raise ValueError(
            f"identity revision conflict: expected {expected_revision}, current {current}"
        )
    revision = current + 1
    conn.execute(
        """UPDATE artist_identity_state
           SET current_revision=?, rebuild_status='pending', last_error=NULL,
               updated_at=datetime('now') WHERE state_id=1""",
        (revision,),
    )
    return revision


def _external_id_conflicts(conn: sqlite3.Connection, artist_ids: list[int]) -> list[dict[str, Any]]:
    if not artist_ids or not _table_exists(conn, "artist_identity_external_ids"):
        return []
    placeholders = ",".join("?" for _ in artist_ids)
    rows = conn.execute(
        f"""SELECT provider, external_id, group_concat(artist_id) AS artist_ids
            FROM artist_identity_external_ids
            WHERE verified=1 AND artist_id IN ({placeholders})
            GROUP BY provider, external_id ORDER BY provider, external_id""",
        artist_ids,
    ).fetchall()
    providers: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        providers.setdefault(str(row["provider"]), []).append(dict(row))
    return [
        {"provider": provider, "identities": values}
        for provider, values in providers.items()
        if len(values) > 1
    ]


def search_artist_identity_candidates(
    conn: sqlite3.Connection, query: str, limit: int = 20
) -> list[dict[str, Any]]:
    pattern = f"%{query.strip()}%"
    rows = conn.execute(
        """SELECT a.artist_id, a.artist_name, a.image_url, a.image_path
           FROM artists a
           WHERE a.artist_name LIKE ? COLLATE NOCASE
           ORDER BY a.artist_name
           LIMIT ?""",
        (pattern, limit),
    ).fetchall()
    mapping = get_artist_identity_map(conn)
    from backend.domains.metadata.track_credits import get_effective_track_credits

    tracks_by_artist: dict[int, set[int]] = {}
    for credit in get_effective_track_credits(conn):
        tracks_by_artist.setdefault(int(credit["artist_id"]), set()).add(int(credit["track_id"]))
    play_metrics = {
        int(row["track_id"]): dict(row)
        for row in conn.execute(
            """SELECT track_id, COUNT(DISTINCT play_id) AS play_count,
                      MIN(ts_date) AS first_play_date, MAX(ts_date) AS last_play_date
               FROM plays WHERE track_id IS NOT NULL GROUP BY track_id"""
        ).fetchall()
    }
    result = []
    for row in rows:
        item = dict(row)
        resolved = mapping[int(row["artist_id"])]
        external_ids = (
            [
                dict(value)
                for value in conn.execute(
                    """SELECT provider, external_id, evidence_type, confidence, verified
                       FROM artist_identity_external_ids WHERE artist_id=?""",
                    (row["artist_id"],),
                ).fetchall()
            ]
            if _table_exists(conn, "artist_identity_external_ids")
            else []
        )
        metrics = [
            play_metrics.get(track_id, {})
            for track_id in tracks_by_artist.get(resolved.canonical_artist_id, set())
        ]
        item.update(
            {
                "play_count": sum(int(value.get("play_count") or 0) for value in metrics),
                "first_play_date": min(
                    (
                        str(value["first_play_date"])
                        for value in metrics
                        if value.get("first_play_date")
                    ),
                    default=None,
                ),
                "last_play_date": max(
                    (
                        str(value["last_play_date"])
                        for value in metrics
                        if value.get("last_play_date")
                    ),
                    default=None,
                ),
                "identity_id": resolved.identity_id,
                "canonical_artist_id": resolved.canonical_artist_id,
                "canonical_display_name": resolved.display_name,
                "cover_url": f"/covers/artists/{row['artist_id']}.jpg"
                if row["image_url"] or row["image_path"]
                else None,
                "external_ids": external_ids,
            }
        )
        # Older imports can have authoritative Spotify metadata without the
        # governance link having been backfilled yet. Surface that stable ID
        # as non-verified evidence only when the name resolves uniquely; the
        # write operation still binds the selected local artist_id.
        if not item["external_ids"] and _table_exists(conn, "spotify_artist_meta"):
            meta_rows = conn.execute(
                """SELECT DISTINCT spotify_artist_id
                   FROM spotify_artist_meta
                   WHERE artist_name=? COLLATE NOCASE
                     AND COALESCE(spotify_artist_id, '')<>''""",
                (row["artist_name"],),
            ).fetchall()
            meta_ids = sorted({str(value[0]) for value in meta_rows})
            if len(meta_ids) == 1:
                item["external_ids"] = [
                    {
                        "provider": "spotify",
                        "external_id": meta_ids[0],
                        "evidence_type": "provider_metadata_name_match",
                        "confidence": 0.8,
                        "verified": 0,
                    }
                ]
        result.append(item)
    return sorted(result, key=lambda item: (-int(item["play_count"]), item["artist_name"]))


def preview_artist_identity_merge(
    conn: sqlite3.Connection,
    artist_ids: list[int],
    canonical_artist_id: int,
    display_name: str,
) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(int(value) for value in artist_ids))
    if len(unique_ids) < 2:
        raise ValueError("至少选择两个不同艺人")
    if canonical_artist_id not in unique_ids:
        raise ValueError("canonical artist 必须属于所选成员")
    placeholders = ",".join("?" for _ in unique_ids)
    rows = [
        dict(row)
        for row in conn.execute(
            f"""SELECT a.artist_id, a.artist_name, a.genres, a.image_url
                FROM artists a WHERE a.artist_id IN ({placeholders})
                ORDER BY a.artist_id""",
            unique_ids,
        ).fetchall()
    ]
    if len(rows) != len(unique_ids):
        raise ValueError("包含不存在的艺人")
    from backend.domains.metadata.track_credits import get_effective_track_credits

    mapping = get_artist_identity_map(conn)
    selected_canonical_ids = {
        mapping[artist_id].canonical_artist_id if artist_id in mapping else artist_id
        for artist_id in unique_ids
    }
    credits_by_track: dict[int, set[int]] = {}
    tracks_by_artist: dict[int, set[int]] = {}
    for credit in get_effective_track_credits(conn):
        artist_id = int(credit["artist_id"])
        if artist_id not in selected_canonical_ids:
            continue
        track_id = int(credit["track_id"])
        credits_by_track.setdefault(track_id, set()).add(artist_id)
        tracks_by_artist.setdefault(artist_id, set()).add(track_id)
    play_rows = {
        int(row["track_id"]): dict(row)
        for row in conn.execute(
            """SELECT track_id, COUNT(DISTINCT play_id) AS play_count,
                      MIN(ts_date) AS first_play_date, MAX(ts_date) AS last_play_date
               FROM plays WHERE track_id IS NOT NULL GROUP BY track_id"""
        ).fetchall()
    }
    for member in rows:
        resolved = mapping.get(int(member["artist_id"]))
        member_canonical = resolved.canonical_artist_id if resolved else int(member["artist_id"])
        metrics = [
            play_rows.get(track_id, {})
            for track_id in tracks_by_artist.get(member_canonical, set())
        ]
        member["play_count"] = sum(int(value.get("play_count") or 0) for value in metrics)
        member["first_play_date"] = min(
            (str(value["first_play_date"]) for value in metrics if value.get("first_play_date")),
            default=None,
        )
        member["last_play_date"] = max(
            (str(value["last_play_date"]) for value in metrics if value.get("last_play_date")),
            default=None,
        )
    shared_track_ids = [
        track_id for track_id, artist_set in credits_by_track.items() if len(artist_set) > 1
    ]
    shared_tracks = []
    if shared_track_ids:
        track_placeholders = ",".join("?" for _ in shared_track_ids)
        shared_tracks = [
            {
                **dict(row),
                "artists": len(credits_by_track[int(row["track_id"])]),
            }
            for row in conn.execute(
                f"""SELECT track_id, spotify_track_id, track_name FROM tracks
                    WHERE track_id IN ({track_placeholders})
                      AND COALESCE(spotify_track_id, '') != ''
                    ORDER BY track_name LIMIT 20""",
                shared_track_ids,
            ).fetchall()
        ]
    duplicate_events = sum(
        int(play_rows.get(track_id, {}).get("play_count") or 0) for track_id in shared_track_ids
    )
    conflicts = _external_id_conflicts(conn, unique_ids)
    if _table_exists(conn, "spotify_artist_meta"):
        provider_rows = conn.execute(
            f"""SELECT a.artist_id, a.artist_name, sam.spotify_artist_id,
                       sam.artist_name AS provider_artist_name
                FROM artists a
                JOIN spotify_artist_meta sam
                  ON lower(sam.artist_name)=lower(a.artist_name)
                WHERE a.artist_id IN ({placeholders})
                ORDER BY a.artist_id, sam.spotify_artist_id""",
            unique_ids,
        ).fetchall()
        observed_ids = {str(row["spotify_artist_id"]) for row in provider_rows}
        if len(observed_ids) > 1:
            conflicts.append(
                {
                    "provider": "spotify",
                    "evidence_type": "member_name_provider_metadata",
                    "identities": [dict(row) for row in provider_rows],
                }
            )
    genres = sorted({str(row["genres"]) for row in rows if row["genres"]})
    metadata_conflicts: dict[str, Any] = {}
    if len(genres) > 1:
        metadata_conflicts["genres"] = genres
    if _table_exists(conn, "artist_language_sources"):
        language_rows = conn.execute(
            f"""SELECT artist_id, classification, primary_language_code, language_variant
                FROM artist_language_sources
                WHERE status='approved' AND artist_id IN ({placeholders})
                ORDER BY artist_id, source_id DESC""",
            unique_ids,
        ).fetchall()
        language_facts = [dict(row) for row in language_rows]
        language_keys = {
            (
                row["classification"],
                row["primary_language_code"],
                row["language_variant"],
            )
            for row in language_rows
        }
        if len(language_keys) > 1:
            metadata_conflicts["language"] = language_facts
    return {
        "members": rows,
        "canonical_artist_id": canonical_artist_id,
        "display_name": display_name.strip(),
        "combined_play_count_before_dedupe": sum(int(row["play_count"] or 0) for row in rows),
        "duplicate_play_events": int(duplicate_events),
        "shared_stable_tracks": shared_tracks,
        "external_id_conflicts": conflicts,
        "metadata_conflicts": metadata_conflicts,
        "blocked": bool(conflicts),
        "affected_scopes": [
            "播放统计与记录",
            "个人 Billboard 与年终榜",
            "艺人详情、搜索与筛选",
            "Wrapped、社区与 AI 报告",
            "艺人语言、流派、图片及预聚合",
        ],
    }


def list_artist_identity_groups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    snapshot = _active_snapshot(conn)
    for group in snapshot["groups"]:
        for member in group["members"]:
            artist = conn.execute(
                """SELECT artist_name, image_url, image_path FROM artists WHERE artist_id=?""",
                (member["artist_id"],),
            ).fetchone()
            member["artist_name"] = artist["artist_name"]
            member["cover_url"] = (
                f"/covers/artists/{member['artist_id']}.jpg"
                if artist["image_url"] or artist["image_path"]
                else None
            )
    return snapshot["groups"]


def _record_event(
    conn: sqlite3.Connection,
    *,
    identity_id: int | None,
    action: str,
    before: dict[str, Any],
    after: dict[str, Any],
    actor: str,
    reason: str,
    revision: int,
    idempotency_key: str,
    undo_of_event_id: int | None = None,
) -> int:
    cursor = conn.execute(
        """INSERT INTO artist_identity_events(
               identity_id, action, before_json, after_json, actor, reason,
               revision, idempotency_key, undo_of_event_id
           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            identity_id,
            action,
            json.dumps(before, ensure_ascii=False, sort_keys=True),
            json.dumps(after, ensure_ascii=False, sort_keys=True),
            actor,
            reason,
            revision,
            idempotency_key,
            undo_of_event_id,
        ),
    )
    return int(cursor.lastrowid)


def create_artist_identity_group(
    conn: sqlite3.Connection,
    *,
    artist_ids: list[int],
    canonical_artist_id: int,
    display_name: str,
    expected_revision: int,
    idempotency_key: str,
    reason: str,
    actor: str = "local_user",
    confirm_external_id_conflict: bool = False,
    external_ids: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prior = conn.execute(
        "SELECT event_id, revision, identity_id FROM artist_identity_events WHERE idempotency_key=?",
        (idempotency_key,),
    ).fetchone()
    if prior:
        return {"event_id": prior[0], "revision": prior[1], "identity_id": prior[2]}
    preview = preview_artist_identity_merge(conn, artist_ids, canonical_artist_id, display_name)
    if preview["blocked"] and not confirm_external_id_conflict:
        raise ValueError("所选艺人存在不同的 provider / 外部 ID；请确认后再合并")
    reason = reason.strip() or "个人管理直接合并"
    unique_ids = list(dict.fromkeys(int(value) for value in artist_ids))
    normalized_external_ids: list[dict[str, Any]] = []
    for link in external_ids or []:
        artist_id = int(link.get("artist_id", 0))
        if artist_id not in unique_ids:
            raise ValueError("外部身份关联的艺人必须属于所选成员")
        provider = str(link.get("provider") or "").strip().lower()
        external_id = str(link.get("external_id") or "").strip()
        evidence_type = str(link.get("evidence_type") or "").strip()
        confidence = float(link.get("confidence", 1.0))
        if not provider or not external_id or not evidence_type:
            raise ValueError("外部身份关联缺少 provider、external_id 或证据类型")
        if confidence < 0 or confidence > 1:
            raise ValueError("外部身份关联 confidence 必须在 0 到 1 之间")
        normalized_external_ids.append(
            {
                "artist_id": artist_id,
                "provider": provider,
                "external_id": external_id,
                "evidence_type": evidence_type,
                "evidence_source": str(link.get("evidence_source") or "").strip() or None,
                "confidence": confidence,
                "verified": 1 if bool(link.get("verified", True)) else 0,
            }
        )
    verified_by_provider: dict[str, set[str]] = {}
    for link in normalized_external_ids:
        if link["verified"]:
            verified_by_provider.setdefault(link["provider"], set()).add(link["external_id"])
    prospective_conflict = any(len(values) > 1 for values in verified_by_provider.values())
    if prospective_conflict and not confirm_external_id_conflict:
        raise ValueError("所选艺人存在不同的 provider / 外部 ID；请确认后再合并")
    placeholders = ",".join("?" for _ in unique_ids)
    existing_groups = [
        int(row[0])
        for row in conn.execute(
            f"""SELECT DISTINCT identity_id FROM artist_identity_members
                WHERE active=1 AND artist_id IN ({placeholders})""",
            unique_ids,
        ).fetchall()
    ]
    if existing_groups:
        group_placeholders = ",".join("?" for _ in existing_groups)
        existing_members = {
            int(row[0])
            for row in conn.execute(
                f"""SELECT artist_id FROM artist_identity_members
                    WHERE active=1 AND identity_id IN ({group_placeholders})""",
                existing_groups,
            ).fetchall()
        }
        if not existing_members.issubset(set(unique_ids)):
            raise ValueError("所选成员只覆盖了现有身份组的一部分；请先显式移除成员")
    before = _active_snapshot(conn)
    revision = _next_revision(conn, expected_revision)
    if existing_groups:
        group_placeholders = ",".join("?" for _ in existing_groups)
        conn.execute(
            f"UPDATE artist_identity_groups SET status='archived', updated_at=datetime('now') "
            f"WHERE identity_id IN ({group_placeholders})",
            existing_groups,
        )
        conn.execute(
            f"""UPDATE artist_identity_members SET active=0, removed_at=datetime('now')
                WHERE identity_id IN ({group_placeholders}) AND active=1""",
            existing_groups,
        )
    display_artist_id = canonical_artist_id
    cursor = conn.execute(
        """INSERT INTO artist_identity_groups(
               canonical_artist_id, display_artist_id, display_name,
               display_source, revision
           ) VALUES (?, ?, ?, 'user_selected', ?)""",
        (canonical_artist_id, display_artist_id, display_name.strip(), revision),
    )
    identity_id = int(cursor.lastrowid)
    for artist_id in unique_ids:
        conn.execute(
            """INSERT INTO artist_identity_members(
                   identity_id, artist_id, role, evidence_type, evidence_json, confidence
               ) VALUES (?, ?, ?, 'user_confirmed', ?, 1.0)""",
            (
                identity_id,
                artist_id,
                "canonical" if artist_id == canonical_artist_id else "alias",
                json.dumps(
                    {
                        "reason": reason,
                        "shared_stable_tracks": preview["shared_stable_tracks"][:5],
                    },
                    ensure_ascii=False,
                ),
            ),
        )
    for link in normalized_external_ids:
        conn.execute(
            """INSERT INTO artist_identity_external_ids(
                   artist_id, provider, external_id, evidence_type,
                   evidence_source, confidence, verified
               ) VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(artist_id, provider, external_id) DO UPDATE SET
                   evidence_type=excluded.evidence_type,
                   evidence_source=excluded.evidence_source,
                   confidence=excluded.confidence,
                   verified=excluded.verified""",
            (
                link["artist_id"],
                link["provider"],
                link["external_id"],
                link["evidence_type"],
                link["evidence_source"],
                link["confidence"],
                link["verified"],
            ),
        )
    _sync_legacy_projection(conn)
    after = _active_snapshot(conn)
    event_id = _record_event(
        conn,
        identity_id=identity_id,
        action="create_or_merge",
        before=before,
        after=after,
        actor=actor,
        reason=reason,
        revision=revision,
        idempotency_key=idempotency_key,
    )
    conn.commit()
    return {"event_id": event_id, "revision": revision, "identity_id": identity_id}


def update_artist_identity_group(
    conn: sqlite3.Connection,
    *,
    identity_id: int,
    add_ids: list[int] | None,
    remove_ids: list[int] | None,
    canonical_artist_id: int | None,
    display_name: str | None,
    provider_metadata_artist_id: int | None = None,
    expected_revision: int,
    idempotency_key: str,
    reason: str,
    actor: str = "local_user",
    confirm_external_id_conflict: bool = False,
) -> dict[str, Any]:
    group = conn.execute(
        "SELECT * FROM artist_identity_groups WHERE identity_id=? AND status='active'",
        (identity_id,),
    ).fetchone()
    if not group:
        raise ValueError("身份组不存在或已归档")
    current_ids = [
        int(row[0])
        for row in conn.execute(
            "SELECT artist_id FROM artist_identity_members WHERE identity_id=? AND active=1",
            (identity_id,),
        ).fetchall()
    ]
    next_ids = [value for value in current_ids if value not in set(remove_ids or [])]
    next_ids.extend(value for value in (add_ids or []) if value not in next_ids)
    if not next_ids:
        raise ValueError("身份组不能没有成员")
    next_canonical = canonical_artist_id or int(group["canonical_artist_id"])
    if next_canonical not in next_ids:
        raise ValueError("canonical artist 必须属于身份组")
    next_display = (display_name or str(group["display_name"])).strip()
    group_columns = {row[1] for row in conn.execute("PRAGMA table_info(artist_identity_groups)")}
    current_provider_artist_id = (
        group["provider_metadata_artist_id"]
        if "provider_metadata_artist_id" in group_columns
        else None
    )
    next_provider_artist_id = provider_metadata_artist_id or current_provider_artist_id
    if next_provider_artist_id is not None and int(next_provider_artist_id) not in next_ids:
        raise ValueError("provider metadata artist 必须属于身份组")
    preview = (
        preview_artist_identity_merge(conn, next_ids, next_canonical, next_display)
        if len(next_ids) >= 2
        else {"blocked": False}
    )
    if preview["blocked"] and not confirm_external_id_conflict:
        raise ValueError("所选艺人存在不同的 provider / 外部 ID；请确认后再修改")
    reason = reason.strip() or "个人管理直接修改"
    for artist_id in add_ids or []:
        existing_member = conn.execute(
            """SELECT identity_id FROM artist_identity_members
               WHERE artist_id=? AND active=1""",
            (artist_id,),
        ).fetchone()
        if existing_member and int(existing_member[0]) != identity_id:
            raise ValueError("新增成员已属于另一个身份组；请使用合并身份组操作")
    before = _active_snapshot(conn)
    revision = _next_revision(conn, expected_revision)
    if "provider_metadata_artist_id" in group_columns:
        conn.execute(
            """UPDATE artist_identity_groups
               SET canonical_artist_id=?, display_artist_id=?, display_name=?,
                   provider_metadata_artist_id=?, display_source='user_selected',
                   revision=?, updated_at=datetime('now')
               WHERE identity_id=?""",
            (
                next_canonical,
                next_canonical,
                next_display,
                next_provider_artist_id,
                revision,
                identity_id,
            ),
        )
    else:
        conn.execute(
            """UPDATE artist_identity_groups
               SET canonical_artist_id=?, display_artist_id=?, display_name=?,
                   display_source='user_selected', revision=?, updated_at=datetime('now')
               WHERE identity_id=?""",
            (next_canonical, next_canonical, next_display, revision, identity_id),
        )
    for artist_id in remove_ids or []:
        conn.execute(
            """UPDATE artist_identity_members SET active=0, removed_at=datetime('now')
               WHERE identity_id=? AND artist_id=? AND active=1""",
            (identity_id, artist_id),
        )
    for artist_id in add_ids or []:
        if artist_id in current_ids:
            continue
        conn.execute(
            """INSERT INTO artist_identity_members(
                   identity_id, artist_id, role, evidence_type, evidence_json, confidence
               ) VALUES (?, ?, 'alias', 'user_confirmed', ?, 1.0)""",
            (identity_id, artist_id, json.dumps({"reason": reason}, ensure_ascii=False)),
        )
    conn.execute(
        """UPDATE artist_identity_members SET role=CASE WHEN artist_id=? THEN 'canonical' ELSE 'alias' END
           WHERE identity_id=? AND active=1""",
        (next_canonical, identity_id),
    )
    _sync_legacy_projection(conn)
    after = _active_snapshot(conn)
    event_id = _record_event(
        conn,
        identity_id=identity_id,
        action="update",
        before=before,
        after=after,
        actor=actor,
        reason=reason,
        revision=revision,
        idempotency_key=idempotency_key,
    )
    conn.commit()
    return {"event_id": event_id, "revision": revision, "identity_id": identity_id}


def _restore_snapshot(conn: sqlite3.Connection, snapshot: dict[str, Any]) -> None:
    conn.execute("UPDATE artist_identity_groups SET status='archived', updated_at=datetime('now')")
    conn.execute(
        "UPDATE artist_identity_members SET active=0, removed_at=datetime('now') WHERE active=1"
    )
    for group in snapshot.get("groups", []):
        identity_id = int(group["identity_id"])
        group_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(artist_identity_groups)")
        }
        if "provider_metadata_artist_id" in group_columns:
            conn.execute(
                """INSERT INTO artist_identity_groups(
                       identity_id, canonical_artist_id, display_artist_id, display_name,
                       display_source, provider_metadata_artist_id, status, revision, updated_at
                   ) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, datetime('now'))
                   ON CONFLICT(identity_id) DO UPDATE SET
                       canonical_artist_id=excluded.canonical_artist_id,
                       display_artist_id=excluded.display_artist_id,
                       display_name=excluded.display_name,
                       display_source=excluded.display_source,
                       provider_metadata_artist_id=excluded.provider_metadata_artist_id,
                       status='active', revision=excluded.revision,
                       updated_at=datetime('now')""",
                (
                    identity_id,
                    group["canonical_artist_id"],
                    group["display_artist_id"],
                    group["display_name"],
                    group["display_source"],
                    group.get("provider_metadata_artist_id"),
                    group["revision"],
                ),
            )
        else:
            conn.execute(
                """INSERT INTO artist_identity_groups(
                       identity_id, canonical_artist_id, display_artist_id, display_name,
                       display_source, status, revision, updated_at
                   ) VALUES (?, ?, ?, ?, ?, 'active', ?, datetime('now'))
               ON CONFLICT(identity_id) DO UPDATE SET
                   canonical_artist_id=excluded.canonical_artist_id,
                   display_artist_id=excluded.display_artist_id,
                   display_name=excluded.display_name,
                   display_source=excluded.display_source,
                   status='active', revision=excluded.revision,
                   updated_at=datetime('now')""",
                (
                    identity_id,
                    group["canonical_artist_id"],
                    group["display_artist_id"],
                    group["display_name"],
                    group["display_source"],
                    group["revision"],
                ),
            )
        for member in group.get("members", []):
            conn.execute(
                """INSERT INTO artist_identity_members(
                       identity_id, artist_id, role, evidence_type, evidence_json,
                       confidence, active
                   ) VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (
                    identity_id,
                    member["artist_id"],
                    member["role"],
                    member["evidence_type"],
                    member["evidence_json"],
                    member["confidence"],
                ),
            )
    _sync_legacy_projection(conn)


def undo_artist_identity_event(
    conn: sqlite3.Connection,
    *,
    event_id: int,
    expected_revision: int,
    idempotency_key: str,
    reason: str,
    actor: str = "local_user",
) -> dict[str, Any]:
    event = conn.execute(
        "SELECT * FROM artist_identity_events WHERE event_id=?", (event_id,)
    ).fetchone()
    if not event:
        raise ValueError("操作记录不存在")
    if conn.execute(
        "SELECT 1 FROM artist_identity_events WHERE undo_of_event_id=?", (event_id,)
    ).fetchone():
        raise ValueError("该操作已经撤销")
    before = _active_snapshot(conn)
    revision = _next_revision(conn, expected_revision)
    target = json.loads(event["before_json"])
    _restore_snapshot(conn, target)
    after = _active_snapshot(conn)
    undo_id = _record_event(
        conn,
        identity_id=event["identity_id"],
        action="undo",
        before=before,
        after=after,
        actor=actor,
        reason=reason,
        revision=revision,
        idempotency_key=idempotency_key,
        undo_of_event_id=event_id,
    )
    conn.commit()
    return {"event_id": undo_id, "revision": revision, "identity_id": event["identity_id"]}


def list_artist_identity_events(conn: sqlite3.Connection, limit: int = 100) -> list[dict[str, Any]]:
    if not _table_exists(conn, "artist_identity_events"):
        return []
    return [
        dict(row)
        for row in conn.execute(
            """SELECT event_id, identity_id, action, actor, reason, revision,
                      undo_of_event_id, created_at
               FROM artist_identity_events ORDER BY event_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    ]


def resolution_as_dict(resolution: ArtistIdentityResolution) -> dict[str, Any]:
    return asdict(resolution)


def canonicalize_artist_payload(payload: Any, conn: sqlite3.Connection) -> Any:
    """Resolve artist fields in JSON-like consumer payloads without touching raw rows."""
    mapping = get_artist_identity_map(conn)
    raw_names = {
        int(row[0]): str(row[1])
        for row in conn.execute("SELECT artist_id, artist_name FROM artists").fetchall()
    }
    name_mapping = {
        raw_names[raw_id]: resolution
        for raw_id, resolution in mapping.items()
        if raw_id in raw_names
    }

    def walk(value: Any) -> Any:
        if isinstance(value, list):
            return [walk(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {key: walk(item) for key, item in value.items()}
        artist_id = result.get("artist_id")
        resolution = None
        if isinstance(artist_id, int):
            resolution = mapping.get(artist_id)
        artist_name = result.get("artist_name")
        if resolution is None and isinstance(artist_name, str):
            resolution = name_mapping.get(artist_name)
        if resolution is not None:
            if "artist_id" in result:
                result["artist_id"] = resolution.canonical_artist_id
            if "artist_name" in result:
                result["artist_name"] = resolution.display_name
        artist_names = result.get("artist_names")
        if isinstance(artist_names, list):
            resolved_names: list[str] = []
            for name in artist_names:
                current = name_mapping.get(str(name))
                display = current.display_name if current else str(name)
                if display not in resolved_names:
                    resolved_names.append(display)
            result["artist_names"] = resolved_names
        return result

    return walk(payload)
