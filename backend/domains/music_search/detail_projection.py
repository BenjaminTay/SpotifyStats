"""Published, bounded facts for music detail readers.

Writers run only inside explicit snapshot maintenance transactions. Readers
never rebuild missing projections and distinguish an empty fact set from an
unavailable publication.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict

import pandas as pd

DETAIL_PROJECTION_VERSION = "music_detail_v1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS music_search_detail_projection_state (
 snapshot_key TEXT PRIMARY KEY REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
 projection_version TEXT NOT NULL, source_revision TEXT NOT NULL,
 source_row_count INTEGER NOT NULL CHECK(source_row_count>=0)
);
CREATE TABLE IF NOT EXISTS music_search_detail_source_facts (
 snapshot_key TEXT NOT NULL REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
 l1_id INTEGER NOT NULL, source_album_id INTEGER NOT NULL DEFAULT 0,
 track_album_id INTEGER NOT NULL DEFAULT 0, week TEXT NOT NULL, day TEXT NOT NULL,
 play_count INTEGER NOT NULL CHECK(play_count>=0), total_ms INTEGER NOT NULL CHECK(total_ms>=0),
 PRIMARY KEY(snapshot_key,l1_id,source_album_id,track_album_id,week,day)
);
CREATE INDEX IF NOT EXISTS idx_music_search_detail_source_album
 ON music_search_detail_source_facts(snapshot_key,source_album_id,l1_id);
CREATE INDEX IF NOT EXISTS idx_music_search_detail_source_week
 ON music_search_detail_source_facts(snapshot_key,week);
CREATE TABLE IF NOT EXISTS music_search_detail_entity_projection (
 snapshot_key TEXT NOT NULL REFERENCES music_search_snapshot_meta(snapshot_key) ON DELETE CASCADE,
 kind TEXT NOT NULL, entity_id INTEGER NOT NULL, payload_json TEXT NOT NULL,
 payload_digest TEXT NOT NULL,
 PRIMARY KEY(snapshot_key,kind,entity_id)
);
"""


def projection_available(conn, snapshot_key, *, allow_stale=False):
    try:
        return (
            conn.execute(
                """SELECT 1 FROM music_search_detail_projection_state p
            JOIN music_search_snapshot_meta s USING(snapshot_key)
            WHERE p.snapshot_key=? AND (s.status='ready' OR (?=1 AND s.status='stale'))
              AND p.source_revision=s.source_revision AND p.projection_version=?""",
                (snapshot_key, int(allow_stale), DETAIL_PROJECTION_VERSION),
            ).fetchone()
            is not None
        )
    except sqlite3.OperationalError:
        return False


def source_rows_from_frame(frame: pd.DataFrame):
    if frame.empty:
        return []
    required = {"track_id", "billboard_week", "play_count", "total_ms"}
    if not required <= set(frame.columns):
        raise ValueError("detail projection source columns are incomplete")
    scoped = frame.copy(deep=False).assign(
        source_album_id=frame.get("source_album_id", pd.Series(0, index=frame.index))
        .fillna(0)
        .astype(int),
        track_album_id=frame.get("track_album_id", pd.Series(0, index=frame.index))
        .fillna(0)
        .astype(int),
        week=pd.to_datetime(frame["billboard_week"]).dt.strftime("%Y-%m-%d"),
        day=pd.to_datetime(frame["ts_date"] if "ts_date" in frame else frame["ts"]).dt.strftime(
            "%Y-%m-%d"
        ),
    )
    rows = scoped.groupby(
        ["track_id", "source_album_id", "track_album_id", "week", "day"], dropna=False, sort=False
    )[["play_count", "total_ms"]].sum()
    return [
        (
            int(key[0]),
            int(key[1]),
            int(key[2]),
            str(key[3]),
            str(key[4]),
            int(value.play_count),
            int(value.total_ms),
        )
        for key, value in rows.iterrows()
        if value.play_count or value.total_ms
    ]


def build_source_rows(conn, context, primary=None):
    from backend.domains.music_search.snapshot import (
        _listening_duration_source,
        _load_shared_logical_frames,
    )
    from backend.domains.playback.logical_timeline import build_billboard_weighted_frame

    if primary is None:
        primary = _load_shared_logical_frames(conn, (context,), ("track", "album"))[
            context.dynamic_threshold
        ][0]
    duration = _listening_duration_source(primary)
    primary = primary.copy(deep=False)
    primary.attrs = {}
    duration = duration.copy(deep=False)
    duration.attrs = {}
    weighted = build_billboard_weighted_frame(
        primary,
        week_start_dow=context.bb_week_start_dow,
        week_start_hour=context.bb_week_start_hour,
        duration_frame=duration,
    )
    return source_rows_from_frame(weighted)


def build_entity_projections(conn, context):
    from backend.domains.metadata.track_credits import canonical_artist_names_for_effective_tracks
    from backend.domains.playback.album_projects import (
        apply_canonical_song_keys,
        load_album_project_membership,
    )

    membership = load_album_project_membership(conn, context.merge_level, include_compilations=True)
    identities = conn.execute("""SELECT li.l1_id, li.representative_track_id, t.track_name, a.artist_name
        FROM track_l1_identities li JOIN tracks t ON t.track_id=li.representative_track_id
        JOIN artists a ON a.artist_id=t.artist_id""").fetchall()
    identity_frame = pd.DataFrame([dict(row) for row in identities]).rename(
        columns={"l1_id": "track_id"}
    )
    keyed = apply_canonical_song_keys(identity_frame, conn, context.merge_level)
    ids_by_song = (
        keyed.groupby("canonical_song_key")["track_id"].apply(list).to_dict()
        if not keyed.empty
        else {}
    )
    payloads = []
    membership_by_project = {}
    if not membership.empty:
        membership = membership.copy()
        membership["l1_ids"] = membership["canonical_song_key"].map(
            lambda key: [int(value) for value in ids_by_song.get(key, [])]
        )
        for project_id, rows in membership.groupby("project_id", sort=False):
            membership_by_project[int(project_id)] = rows.to_json(
                orient="records", date_format="iso"
            )
    credits = canonical_artist_names_for_effective_tracks(
        conn, [int(row["representative_track_id"]) for row in identities]
    )
    artist_ids = {
        str(row[1]): int(row[0])
        for row in conn.execute("SELECT artist_id,artist_name FROM artists")
    }
    artist_tracks = defaultdict(set)
    for row in identities:
        for name in credits.get(int(row["representative_track_id"]), [str(row["artist_name"])]):
            if name in artist_ids:
                artist_tracks[artist_ids[name]].add(int(row["l1_id"]))
    for artist_id in artist_ids.values():
        payloads.append(
            ("artist_track_keys", artist_id, json.dumps(sorted(artist_tracks[artist_id])))
        )
    generation = conn.execute(
        "SELECT active_generation_id FROM music_search_index_state WHERE state_id=1"
    ).fetchone()[0]
    artist_album_keys = defaultdict(set)
    for row in conn.execute(
        "SELECT entity_key,artist_name FROM music_search_documents WHERE generation_id=? AND kind='album_project' AND merge_level=?",
        (generation, context.merge_level),
    ):
        if str(row[1]) in artist_ids:
            artist_album_keys[artist_ids[str(row[1])]].add(str(row[0]))
    for artist_id in artist_ids.values():
        payloads.append(
            ("artist_album_keys", artist_id, json.dumps(sorted(artist_album_keys[artist_id])))
        )
    # Legacy album overlays use representative L1/provider album membership,
    # with release-group canonical names, independent of album-chart ownership.
    album_map = defaultdict(set)
    for row in conn.execute("""SELECT links.l1_id,al.album_name FROM track_l1_source_links links
        JOIN tracks t ON t.track_id=links.track_id JOIN albums al ON al.album_id=t.album_id
        UNION SELECT links.l1_id,al.album_name FROM track_l1_source_links links
        JOIN track_albums ta ON ta.track_id=links.track_id JOIN albums al ON al.album_id=ta.album_id"""):
        album_map[int(row[0])].add(str(row[1]))
    canonical = {
        (str(row[0]), str(row[1])): str(row[2])
        for row in conn.execute("""SELECT al.album_name,a.artist_name,rg.canonical_name
        FROM release_group_members rgm JOIN release_groups rg USING(group_id)
        JOIN albums al ON al.album_id=rgm.album_id JOIN artists a ON a.artist_id=al.artist_id""")
    }
    album_tracks = defaultdict(set)
    for row in identities:
        primary_name = credits.get(int(row["representative_track_id"]), [str(row["artist_name"])])[
            0
        ]
        for name in album_map[int(row["l1_id"])]:
            album_tracks[(canonical.get((name, primary_name), name), primary_name)].add(
                int(row["l1_id"])
            )
    for row in conn.execute("""SELECT project_id,canonical_name,a.artist_name FROM album_projects ap
        JOIN artists a ON a.artist_id=ap.artist_id"""):
        payloads.append(
            (
                "album_track_keys",
                int(row[0]),
                json.dumps(sorted(album_tracks[(str(row[1]), str(row[2]))])),
            )
        )
        payloads.append(("membership", int(row[0]), membership_by_project.get(int(row[0]), "[]")))
    return payloads


def publish_detail_projection(conn, context, source_rows, entity_rows=None):
    _assert_writer_allowed()
    if not _table_exists(conn):
        return
    key = context.filter_fingerprint
    entity_rows = build_entity_projections(conn, context) if entity_rows is None else entity_rows
    conn.execute("DELETE FROM music_search_detail_projection_state WHERE snapshot_key=?", (key,))
    conn.execute("DELETE FROM music_search_detail_source_facts WHERE snapshot_key=?", (key,))
    conn.execute("DELETE FROM music_search_detail_entity_projection WHERE snapshot_key=?", (key,))
    conn.executemany(
        "INSERT INTO music_search_detail_source_facts VALUES (?,?,?,?,?,?,?,?)",
        [(key, *row) for row in source_rows],
    )
    checks = source_checks(source_rows, conn)
    checks.extend(ledger_checks(conn, key))
    entity_rows = [
        (str(row[0]), int(row[1]), str(row[2]))
        for row in entity_rows
        if not str(row[0]).startswith(("source_check_", "ledger_check_", "context_check_"))
        and row[0] != "global_no1_albums"
    ]
    conn.executemany(
        "INSERT INTO music_search_detail_entity_projection VALUES (?,?,?,?,?)",
        [(key, *row, payload_digest(row[2])) for row in [*entity_rows, *checks]],
    )
    conn.execute(
        "INSERT INTO music_search_detail_projection_state VALUES (?,?,?,?)",
        (key, DETAIL_PROJECTION_VERSION, context.source_revision, len(source_rows)),
    )


def _table_exists(conn):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='music_search_detail_projection_state' AND type='table'"
        ).fetchone()
        is not None
    )


def clone_detail_projection(conn, context, base_key, *, rebuild_entities=False):
    if not _table_exists(conn):
        return
    base = conn.execute(
        "SELECT projection_version FROM music_search_detail_projection_state WHERE snapshot_key=?",
        (base_key,),
    ).fetchone()
    key = context.filter_fingerprint
    if base is None or base[0] != DETAIL_PROJECTION_VERSION:
        conn.execute(
            "DELETE FROM music_search_detail_projection_state WHERE snapshot_key=?", (key,)
        )
        return
    rows = conn.execute(
        "SELECT l1_id,source_album_id,track_album_id,week,day,play_count,total_ms FROM music_search_detail_source_facts WHERE snapshot_key=?",
        (base_key,),
    ).fetchall()
    entities = (
        None
        if rebuild_entities
        else conn.execute(
            "SELECT kind,entity_id,payload_json FROM music_search_detail_entity_projection WHERE snapshot_key=?",
            (base_key,),
        ).fetchall()
    )
    publish_detail_projection(conn, context, rows, entities)


def load_detail_source_facts(conn, snapshot_key, l1_ids=None, source_album_ids=None):
    if not projection_available(conn, snapshot_key):
        return None
    where = ["f.snapshot_key=?"]
    params = [snapshot_key]
    for column, values in (("l1_id", l1_ids), ("source_album_id", source_album_ids)):
        if values is not None:
            values = sorted({int(value) for value in values})
            if not values:
                return pd.DataFrame(
                    columns=[
                        "track_id",
                        "source_album_id",
                        "track_album_id",
                        "billboard_week",
                        "ts_date",
                        "play_count",
                        "total_ms",
                        "track_name",
                        "artist_name",
                        "artist_id",
                        "album_name",
                    ]
                )
            where.append(f"f.{column} IN ({','.join('?' for _ in values)})")
            params.extend(values)
    raw_rows = conn.execute(
        f"SELECT f.l1_id,f.source_album_id,f.track_album_id,f.week,f.day,f.play_count,f.total_ms FROM music_search_detail_source_facts f WHERE {' AND '.join(where)}",
        params,
    ).fetchall()
    check_kind, check_ids = (
        ("source_check_l1", l1_ids)
        if l1_ids is not None
        else (
            ("source_check_album", source_album_ids)
            if source_album_ids is not None
            else ("source_check_all", [1])
        )
    )
    if l1_ids is not None and source_album_ids is not None:
        raise ValueError("detail source reader requires one target selector")
    for selected_id in sorted({int(value) for value in check_ids or []}):
        relevant = [
            list(row)
            for row in raw_rows
            if check_kind == "source_check_all"
            or int(row[0 if check_kind == "source_check_l1" else 1]) == selected_id
        ]
        expected = _entity_payload(conn, snapshot_key, check_kind, selected_id)
        if (
            expected is None
            or (expected == [] and relevant)
            or (expected != [] and expected != source_check(relevant))
        ):
            return None
    frame = pd.read_sql_query(
        f"""SELECT f.l1_id AS track_id,NULLIF(f.source_album_id,0) AS source_album_id,
        NULLIF(f.track_album_id,0) AS track_album_id,f.week AS billboard_week,f.day AS ts_date,
        f.play_count,f.total_ms,t.track_name,t.artist_id,a.artist_name,
        COALESCE(sa.album_name,ta.album_name) AS album_name
        FROM music_search_detail_source_facts f JOIN track_l1_identities li ON li.l1_id=f.l1_id
        JOIN tracks t ON t.track_id=li.representative_track_id JOIN artists a ON a.artist_id=t.artist_id
        LEFT JOIN albums sa ON sa.album_id=f.source_album_id LEFT JOIN albums ta ON ta.album_id=f.track_album_id
        WHERE {" AND ".join(where)}""",
        conn,
        params=params,
    )
    if not frame.empty:
        from backend.domains.metadata.artist_identity import canonicalize_artist_frame

        frame = canonicalize_artist_frame(frame, conn, dedupe=False)
        frame["billboard_week"] = pd.to_datetime(frame["billboard_week"])
        frame["ts_date"] = pd.to_datetime(frame["ts_date"])
        frame["ts"] = frame["ts_date"]
        frame["ms_played"] = frame["total_ms"]
    return frame


def _entity_payload(conn, snapshot_key, kind, entity_id):
    if not projection_available(conn, snapshot_key):
        return None
    row = conn.execute(
        "SELECT payload_json,payload_digest FROM music_search_detail_entity_projection WHERE snapshot_key=? AND kind=? AND entity_id=?",
        (snapshot_key, kind, entity_id),
    ).fetchone()
    if row is None:
        return None
    if payload_digest(row[0]) != row[1]:
        return None
    try:
        payload = json.loads(row[0])
        return payload if isinstance(payload, (list, dict)) else None
    except (TypeError, json.JSONDecodeError):
        return None


def load_detail_project_membership(conn, snapshot_key, project_id):
    payload = _entity_payload(conn, snapshot_key, "membership", project_id)
    if payload is None:
        return None
    return pd.DataFrame(payload)


def _target_ledger(conn, key, family, entity_keys):
    if not entity_keys:
        return []
    if not projection_available(conn, key):
        return None
    entity_ids = sorted({int(entity_key.split(":")[1]) for entity_key in entity_keys})
    # Return one JSON value per bounded read. Stepping through hundreds of
    # SQLite rows and separately checking every member repeatedly yields the
    # GIL to concurrent personal-statistics work, even for an indexed query.
    encoded_checks = conn.execute(
        """SELECT json_group_array(json_array(entity_id,payload_json,payload_digest))
           FROM music_search_detail_entity_projection
           WHERE snapshot_key=? AND kind=?
             AND entity_id IN (SELECT value FROM json_each(?))""",
        (key, f"ledger_check_{family}", json.dumps(entity_ids)),
    ).fetchone()[0]
    checks = {}
    for entity_id, payload_json, digest in json.loads(encoded_checks):
        if payload_digest(payload_json) != digest:
            return None
        try:
            checks[entity_id] = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            return None
    if len(checks) != len(entity_ids):
        return None
    encoded_rows = conn.execute(
        """SELECT json_group_array(json_array(week,rank,entity_key,play_count,total_ms,stable_sort_key))
           FROM (SELECT week,rank,entity_key,play_count,total_ms,stable_sort_key
                 FROM music_search_weekly_chart_context
                 WHERE snapshot_key=? AND family=?
                   AND entity_key IN (SELECT value FROM json_each(?))
                 ORDER BY week,rank)""",
        (key, family, json.dumps(entity_keys)),
    ).fetchone()[0]
    rows = json.loads(encoded_rows)
    grouped = defaultdict(list)
    for row in rows:
        grouped[str(row[2])].append(list(row))
    for entity_key in entity_keys:
        entity_id = int(entity_key.split(":")[1])
        expected = checks[entity_id]
        if expected is None or expected != ledger_check(grouped[entity_key]):
            return None
    return rows


def load_detail_overlays(conn, snapshot_key, *, entity, document, values):
    entity_id = int(document["album_project_id"] if entity == "album" else document["artist_id"])
    keys = _entity_payload(conn, snapshot_key, f"{entity}_track_keys", entity_id)
    if keys is None or not isinstance(keys, list):
        return None
    rows = _target_ledger(conn, snapshot_key, "track", [f"track:{int(value)}" for value in keys])
    if rows is None:
        return None
    singles = []
    no1 = []
    seen = set()
    for row in rows:
        try:
            name = json.loads(row[5])["track_name"]
        except (KeyError, TypeError, json.JSONDecodeError):
            return None
        if row[0] not in seen:
            singles.append({"week": str(row[0]), "rank": int(row[1]), "track_name": name})
            seen.add(row[0])
        if int(row[1]) == 1:
            no1.append(
                {
                    "week": str(row[0]),
                    "no1_track_names": name,
                    "no1_track_id": int(str(row[2]).split(":")[1]),
                    "no1_count": 1,
                }
            )
    albums = []
    global_no1 = []
    if entity == "artist":
        album_keys = _entity_payload(conn, snapshot_key, "artist_album_keys", entity_id)
        if album_keys is None or not isinstance(album_keys, list):
            return None
        album_rows = _target_ledger(conn, snapshot_key, "album", album_keys)
        if album_rows is None:
            return None
        seen = set()
        for row in album_rows:
            try:
                name = json.loads(row[5])["album_name"]
            except (KeyError, TypeError, json.JSONDecodeError):
                return None
            if row[0] not in seen:
                albums.append({"week": str(row[0]), "rank": int(row[1]), "album_name": name})
                seen.add(row[0])
        global_no1 = _entity_payload(conn, snapshot_key, "global_no1_albums", 1)
        if global_no1 is None:
            return None
    return {
        "best_singles_overlay": singles,
        "best_albums_overlay": albums,
        f"{entity}_no1_by_week": no1,
        "week_no1_albums": global_no1,
    }


def build_bounded_source_replacements(conn, contexts, weeks):
    """Reuse the established tail-closure loader, including the open week."""
    from backend.domains.music_search.snapshot_week_delta import (
        _load_bounded_tail_closure,
        _logical_events,
    )

    weeks = set(weeks)
    raw = _load_bounded_tail_closure(
        conn,
        weeks,
        week_start_hour=contexts[0].bb_week_start_hour,
        max_gap_minutes=contexts[0].max_merge_gap_minutes,
        max_source_rows=100_000,
    )
    rows = {}
    for dynamic in {c.dynamic_threshold for c in contexts}:
        context = next(c for c in contexts if c.dynamic_threshold == dynamic)
        primary = _logical_events(
            conn,
            raw,
            min_ms=context.min_ms,
            dynamic_threshold=dynamic,
            max_gap_minutes=context.max_merge_gap_minutes,
        )
        rows[dynamic] = [
            row for row in build_source_rows(conn, context, primary) if row[3] in weeks
        ]
    return rows


def replace_detail_projection_weeks(conn, context, base_key, weeks, rows, entity_rows):
    clone_detail_projection(conn, context, base_key)
    key = context.filter_fingerprint
    placeholders = ",".join("?" for _ in weeks)
    if weeks:
        conn.execute(
            f"DELETE FROM music_search_detail_source_facts WHERE snapshot_key=? AND week IN ({placeholders})",
            (key, *sorted(weeks)),
        )
    conn.executemany(
        "INSERT INTO music_search_detail_source_facts VALUES (?,?,?,?,?,?,?,?)",
        [(key, *row) for row in rows],
    )
    conn.execute("DELETE FROM music_search_detail_entity_projection WHERE snapshot_key=?", (key,))
    source_rows = conn.execute(
        "SELECT l1_id,source_album_id,track_album_id,week,day,play_count,total_ms FROM music_search_detail_source_facts WHERE snapshot_key=?",
        (key,),
    ).fetchall()
    conn.executemany(
        "INSERT INTO music_search_detail_entity_projection VALUES (?,?,?,?,?)",
        [
            (key, *row, payload_digest(row[2]))
            for row in [*entity_rows, *source_checks(source_rows, conn), *ledger_checks(conn, key)]
        ],
    )
    conn.execute(
        "UPDATE music_search_detail_projection_state SET source_row_count=(SELECT COUNT(*) FROM music_search_detail_source_facts WHERE snapshot_key=?) WHERE snapshot_key=?",
        (key, key),
    )


def _assert_writer_allowed():
    from backend.core.access_surface import public_readonly_db_guard_active

    if public_readonly_db_guard_active():
        raise RuntimeError("detail projection maintenance is forbidden in public GET")


def backfill_detail_projection_set(conn, contexts):
    """Attach detail facts to existing exact ready search snapshots on a copy.

    This never reconstructs candidate indexes, chart ranking, or search context.
    Source and governance fences are checked before/after all maintenance work.
    """
    _assert_writer_allowed()
    from backend.domains.music_search.context import (
        MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
        build_music_search_filter_context,
    )
    from backend.domains.music_search.snapshot import _load_shared_logical_frames
    from backend.domains.music_search.snapshot_lineage import (
        active_playback_lineage,
        music_search_snapshot_dependency_digest,
    )

    captured = (active_playback_lineage(conn), music_search_snapshot_dependency_digest(conn))
    for context in contexts:
        row = conn.execute(
            "SELECT source_revision,status,builder_version FROM music_search_snapshot_meta WHERE snapshot_key=?",
            (context.filter_fingerprint,),
        ).fetchone()
        if row is None or tuple(row) != (
            context.source_revision,
            "ready",
            MUSIC_SEARCH_SNAPSHOT_BUILDER_VERSION,
        ):
            raise RuntimeError("detail preparation requires exact ready search snapshots")
    payloads = {}
    for dynamic in {c.dynamic_threshold for c in contexts}:
        subset = tuple(c for c in contexts if c.dynamic_threshold == dynamic)
        primary = _load_shared_logical_frames(conn, subset, ("track", "album"))[dynamic][0]
        source_rows = build_source_rows(conn, subset[0], primary)
        for context in subset:
            payloads[context.filter_fingerprint] = (
                source_rows,
                build_entity_projections(conn, context),
            )
        del primary
        from backend.core.cache_manager import invalidate

        invalidate("db")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if captured != (
            active_playback_lineage(conn),
            music_search_snapshot_dependency_digest(conn),
        ):
            raise RuntimeError("detail preparation source fence changed")
        for context in contexts:
            if build_music_search_filter_context(conn, context.filter_values()) != context:
                raise RuntimeError("detail preparation exact filter changed")
            publish_detail_projection(conn, context, *payloads[context.filter_fingerprint])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "status": "ready",
        "variants": len(contexts),
        "source_rows": sum(len(rows[0]) for rows in payloads.values()),
    }


def payload_digest(payload):
    return hashlib.sha256(str(payload).encode()).hexdigest()


def source_check(rows):
    facts = sorted([list(row) for row in rows])
    return {
        "rows": len(facts),
        "plays": sum(int(row[5]) for row in facts),
        "total_ms": sum(int(row[6]) for row in facts),
        "digest": payload_digest(
            json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        ),
    }


def source_checks(rows, conn):
    groups = defaultdict(list)
    rows = [list(row) for row in rows]
    for row in rows:
        groups[("source_check_l1", int(row[0]))].append(row)
        groups[("source_check_album", int(row[1]))].append(row)
    for row in conn.execute("SELECT l1_id FROM track_l1_identities"):
        groups[("source_check_l1", int(row[0]))]
    for row in conn.execute("SELECT album_id FROM albums"):
        groups[("source_check_album", int(row[0]))]
    groups[("source_check_album", 0)]
    groups[("source_check_all", 1)] = rows
    return [
        (kind, key, json.dumps(source_check(values), sort_keys=True, separators=(",", ":")))
        for (kind, key), values in groups.items()
    ]


def ledger_check(rows):
    facts = sorted([list(row) for row in rows])
    return {
        "rows": len(facts),
        "digest": payload_digest(json.dumps(facts, ensure_ascii=True, separators=(",", ":"))),
    }


def ledger_checks(conn, key):
    groups = defaultdict(list)
    global_no1 = []
    for row in conn.execute(
        "SELECT family,week,rank,entity_key,play_count,total_ms,stable_sort_key FROM music_search_weekly_chart_context WHERE snapshot_key=?",
        (key,),
    ):
        family = str(row[0])
        entity_id = int(str(row[3]).split(":")[1])
        groups[(family, entity_id)].append(list(row)[1:])
        if family == "album" and int(row[2]) == 1:
            payload = json.loads(row[6])
            global_no1.append(
                {
                    "week": str(row[1]),
                    "album_name": payload["album_name"],
                    "artist_name": payload["artist_name"],
                }
            )
    for row in conn.execute("SELECT l1_id FROM track_l1_identities"):
        groups[("track", int(row[0]))]
    for row in conn.execute("SELECT project_id FROM album_projects"):
        groups[("album", int(row[0]))]
    for row in conn.execute("SELECT artist_id FROM artists"):
        groups[("artist", int(row[0]))]
    results = [
        (f"ledger_check_{family}", entity_id, json.dumps(ledger_check(rows), separators=(",", ":")))
        for (family, entity_id), rows in groups.items()
    ]
    results.append(
        (
            "global_no1_albums",
            1,
            json.dumps(sorted(global_no1, key=lambda row: row["week"]), separators=(",", ":")),
        )
    )
    results.extend(context_checks(conn, key))
    return results


_CONTEXT_COLUMNS = "entity_key,play_events,total_ms,peak_position,peak_weeks,weeks_on_chart,weeks_at_no1,power_score,power_rank,first_week,latest_week,first_peak_week"


def validate_detail_entity_ledger(conn, key, family, entity_key):
    return _target_ledger(conn, key, family, [entity_key]) is not None


def validate_detail_entity_context(conn, key, entity_key):
    # Entity numeric namespaces can overlap. Use one context-check payload per
    # family rather than letting an album and track borrow the same integer.
    expected = _entity_payload(
        conn, key, "context_check_" + entity_key.split(":")[0], int(entity_key.split(":")[1])
    )
    if expected is None:
        return False
    row = conn.execute(
        f"SELECT {_CONTEXT_COLUMNS} FROM music_search_entity_context WHERE snapshot_key=? AND entity_key=?",
        (key, entity_key),
    ).fetchone()
    return expected == {
        "digest": payload_digest(
            json.dumps(list(row) if row else [], ensure_ascii=True, separators=(",", ":"))
        )
    }


def context_checks(conn, key):
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='music_search_entity_context' AND type='table'"
        ).fetchone()
        is None
    ):
        return []
    rows = {
        str(row[0]): list(row)
        for row in conn.execute(
            f"SELECT {_CONTEXT_COLUMNS} FROM music_search_entity_context WHERE snapshot_key=?",
            (key,),
        )
    }
    if (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE name='music_search_documents' AND type='table'"
        ).fetchone()
        is not None
    ):
        for row in conn.execute("SELECT DISTINCT entity_key FROM music_search_documents"):
            rows.setdefault(str(row[0]), [])
    return [
        (
            "context_check_" + entity_key.split(":")[0],
            int(entity_key.split(":")[1]),
            json.dumps(
                {
                    "digest": payload_digest(
                        json.dumps(row, ensure_ascii=True, separators=(",", ":"))
                    )
                }
            ),
        )
        for entity_key, row in rows.items()
    ]
