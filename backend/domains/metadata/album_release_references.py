"""Reviewed release references never own a provider album or add project tracks."""

from __future__ import annotations

import hashlib
import json

from backend.domains.metadata.album_track_release_evidence import (
    _json,
    _now,
    require_transaction,
    validate_sources,
)
from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
from backend.providers.spotify.album_tracks import complete_track_ids

SCHEMA = """
CREATE TABLE IF NOT EXISTS album_release_references (
 reference_id INTEGER PRIMARY KEY,
 evidence_key TEXT NOT NULL UNIQUE,
 project_id INTEGER NOT NULL REFERENCES album_projects(project_id),
 spotify_album_id TEXT NOT NULL,
 request_json TEXT NOT NULL,
 guard_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','revoked')),
 recorded_by TEXT NOT NULL,
 recorded_at TEXT NOT NULL,
 reviewed_by TEXT,
 reviewed_at TEXT,
 review_reason TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_release_reference_active
 ON album_release_references(project_id) WHERE status='approved';
CREATE TABLE IF NOT EXISTS album_release_reference_events (
 event_id INTEGER PRIMARY KEY,
 reference_id INTEGER NOT NULL REFERENCES album_release_references(reference_id),
 action TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS album_release_date_conflict_reviews (
 assertion_id INTEGER PRIMARY KEY REFERENCES album_release_date_assertions(assertion_id),
 guard_json TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 reviewed_at TEXT NOT NULL
);
"""


def create_schema(conn):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def available(conn, table="album_release_references"):
    return bool(
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
    )


def review_guard(conn, project_id, source_id):
    """Bounded identity/catalog/membership/owner fence, independent of dates being edited."""
    project = conn.execute(
        "SELECT primary_album_id,artist_id,scope,is_manual,canonical_name,project_type "
        "FROM album_projects WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if not project or project[2] != "release" or project[3]:
        raise ValueError("nonmanual_release_project_required")
    source = conn.execute(
        "SELECT album_name,album_type,release_date,release_date_precision,total_tracks,track_list "
        "FROM spotify_album_meta WHERE spotify_album_id=?",
        (source_id,),
    ).fetchone()
    catalog = complete_track_ids(source[5], source[4]) if source else None
    if not catalog or source[1] not in ("album", "ep", "compilation"):
        raise ValueError("complete_release_catalog_required")
    resolver = AlbumArtistResolver(conn)
    credits = resolver.read(source_id)
    members = {
        table: [
            list(r)
            for r in conn.execute(
                f"SELECT * FROM {table} WHERE project_id=? ORDER BY 1,2", (project_id,)
            )
        ]
        for table in ("album_project_albums", "album_project_tracks")
    }
    track_ids = sorted(
        {
            r[0]
            for r in conn.execute(
                "SELECT track_id FROM album_project_tracks WHERE project_id=? UNION "
                "SELECT ta.track_id FROM track_albums ta JOIN album_project_albums a USING(album_id) "
                "WHERE a.project_id=?",
                (project_id, project_id),
            )
        }
    )
    if not track_ids or len(track_ids) > 500:
        raise ValueError("bounded_existing_project_tracks_required")
    marks = ",".join("?" for _ in track_ids)
    from backend.domains.metadata.track_credits import get_effective_track_credits

    # Guard the bounded L1/group neighbourhood, not a global song-work rebuild
    # on every comparison GET. Include parent groups as well as direct groups.
    identities = [
        list(r)
        for r in conn.execute(
            f"SELECT DISTINCT i.l1_id,i.representative_track_id FROM track_l1_identities i "
            f"LEFT JOIN track_l1_source_links s USING(l1_id) WHERE i.identity_status='active' "
            f"AND (s.track_id IN ({marks}) OR i.representative_track_id IN ({marks}) "
            f"OR i.l1_id IN ({marks})) ORDER BY i.l1_id",
            track_ids + track_ids + track_ids,
        )
    ]
    if not identities:
        raise ValueError("published_song_identity_required")
    l1_ids = [r[0] for r in identities]
    l1_marks = ",".join("?" for _ in l1_ids)
    groups = [
        list(r)
        for r in conn.execute(
            f"SELECT DISTINCT g.group_id,g.scope,g.parent_group_id FROM track_groups g "
            f"JOIN track_group_l1_members m USING(group_id) WHERE g.group_status='active' "
            f"AND m.l1_id IN ({l1_marks}) ORDER BY g.group_id",
            l1_ids,
        )
    ]
    keys = sorted(
        {f"l1:{i}" for i in l1_ids}
        | {f"{r[1]}:{r[0]}" for r in groups}
        | {f"composition:{r[2]}" for r in groups if r[2] is not None}
    )
    owners = []
    for key in keys:
        row = conn.execute(
            "SELECT canonical_song_key,target_project_id,origin_release_project_id,"
            "representative_track_id,canonical_artist_key,attribution_kind "
            "FROM l3_song_album_attributions WHERE canonical_song_key=?",
            (key,),
        ).fetchone()
        if row is not None:
            owners.append(list(row))
    if not owners:
        raise ValueError("published_song_owner_required")
    return {
        "project": list(project),
        "source": list(source),
        "credits": credits,
        "target_external_ids": sorted(
            [sid, sorted(ids)]
            for sid, ids in resolver.by_external.items()
            if resolver.canonical(project[1]) in ids
        ),
        "members": members,
        "track_ids": track_ids,
        "owners": owners,
        "song_identities": identities,
        "song_groups": groups,
        "effective_credits": sorted(
            get_effective_track_credits(conn, track_ids),
            key=lambda r: (r["track_id"], r["artist_id"]),
        ),
        "source_bindings": [
            list(r)
            for r in conn.execute(
                "SELECT project_id,confidence,is_primary FROM album_project_external_ids "
                "WHERE provider='spotify' AND external_album_id=? ORDER BY project_id",
                (source_id,),
            )
        ],
        "track_owners": [
            list(r)
            for r in conn.execute(
                f"SELECT spotify_track_id,track_id FROM spotify_track_owners "
                f"WHERE track_id IN ({marks}) ORDER BY spotify_track_id",
                track_ids,
            )
        ],
    }


def reference_guard(conn, item):
    guard = review_guard(conn, item["project_id"], item["spotify_album_id"])
    if item["relation"] not in ("album_artist", "track_artist"):
        raise ValueError("explicit_participation_relation_required")
    resolver = AlbumArtistResolver(conn)
    if (
        item["relation"] == "album_artist"
        and resolver.target_presence(item["spotify_album_id"], guard["project"][1]) != "verified_id"
    ):
        raise ValueError("target_album_artist_unconfirmed")
    tracks = item.get("tracks")
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 500:
        raise ValueError("bounded_explicit_track_mapping_required")
    if any(
        not isinstance(t, dict)
        or type(t.get("track_id")) is not int
        or not isinstance(t.get("spotify_track_id"), str)
        for t in tracks
    ):
        raise ValueError("stable_track_mapping_required")
    # A partial reference must cover the selected project's complete existing
    # membership, never just the convenient subset of a mixed-person project.
    if sorted(t["track_id"] for t in tracks) != guard["track_ids"]:
        raise ValueError("reference_must_cover_existing_members")
    catalog = complete_track_ids(guard["source"][5], guard["source"][4])
    owners = dict(guard["track_owners"])
    target = resolver.canonical(guard["project"][1])
    credited = {r["track_id"] for r in guard["effective_credits"] if r["artist_id"] == target}
    if any(
        t["spotify_track_id"] not in catalog
        or owners.get(t["spotify_track_id"]) != t["track_id"]
        or t["track_id"] not in credited
        for t in tracks
    ):
        raise ValueError("recording_or_participation_unconfirmed")
    return guard


def record_reference(conn, item, *, actor, reason):
    require_transaction(conn, actor, reason)
    if type(item.get("project_id")) is not int or not isinstance(item.get("spotify_album_id"), str):
        raise ValueError("stable_project_and_source_required")
    if item.get("date_kind") != "original_release":
        raise ValueError("reference_requires_project_release_scope")
    for field in ("territory", "medium", "scope_note"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(field + "_required")
    validate_sources(item.get("sources"))
    guard = reference_guard(conn, item)
    key = hashlib.sha256(_json([item, guard]).encode()).hexdigest()
    old = conn.execute(
        "SELECT reference_id FROM album_release_references WHERE evidence_key=?", (key,)
    ).fetchone()
    if old:
        return old[0]
    cur = conn.execute(
        "INSERT INTO album_release_references(evidence_key,project_id,spotify_album_id,request_json,"
        "guard_json,status,recorded_by,recorded_at) VALUES(?,?,?,?,?,'pending',?,?)",
        (
            key,
            item["project_id"],
            item["spotify_album_id"],
            _json(item),
            _json(guard),
            actor,
            _now(),
        ),
    )
    _event(conn, cur.lastrowid, "record", actor, reason)
    return cur.lastrowid


def _event(conn, reference_id, action, actor, reason):
    conn.execute(
        "INSERT INTO album_release_reference_events(reference_id,action,actor,reason,observed_at) VALUES(?,?,?,?,?)",
        (reference_id, action, actor, reason, _now()),
    )


def _row(conn, reference_id):
    cur = conn.execute(
        "SELECT * FROM album_release_references WHERE reference_id=?", (reference_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("reference_not_found")
    return dict(zip([c[0] for c in cur.description], row))


def review_reference(conn, reference_id, decision, *, actor, reason):
    """Caller must reconcile/fence attribution publication before committing."""
    require_transaction(conn, actor, reason)
    row = _row(conn, reference_id)
    status = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}.get(decision)
    if status is None:
        raise ValueError("unknown_review_decision")
    if row["status"] == status:
        if status == "approved" and reference_guard(
            conn, json.loads(row["request_json"])
        ) != json.loads(row["guard_json"]):
            raise ValueError("approved_reference_dependencies_changed")
        return False
    if row["status"] != ("approved" if decision == "revoke" else "pending"):
        raise ValueError("invalid_review_transition")
    if decision == "approve" and reference_guard(
        conn, json.loads(row["request_json"])
    ) != json.loads(row["guard_json"]):
        raise ValueError("reference_dependencies_changed")
    conn.execute(
        "UPDATE album_release_references SET status=?,reviewed_by=?,reviewed_at=?,review_reason=? WHERE reference_id=?",
        (status, actor, _now(), reason, reference_id),
    )
    _event(conn, reference_id, decision, actor, reason)
    if decision in ("approve", "revoke"):
        from backend.domains.metadata.album_release_date_evidence import _bump

        _bump(conn)
    return True


def reference_sources(conn, project_id, album_id):
    """None means no reference; an invalid active review fails closed, not fallback."""
    if project_id is None or not available(conn):
        return None
    ids = conn.execute(
        "SELECT reference_id FROM album_release_references WHERE project_id=? AND status='approved'",
        (project_id,),
    ).fetchall()
    if not ids:
        return None
    row = _row(conn, ids[0][0])
    item, guard = json.loads(row["request_json"]), json.loads(row["guard_json"])
    try:
        valid = (
            len(ids) == 1
            and guard["project"][0] == album_id
            and reference_guard(conn, item) == guard
        )
    except ValueError:
        valid = False
    source = guard["source"]
    return [
        {
            "spotify_album_id": row["spotify_album_id"],
            "album_name": source[0],
            "release_date": source[2],
            "release_date_precision": source[3],
            "confidence": 1,
            "project_bound": False,
            "release_reference_id": row["reference_id"],
            "reference_verified": valid,
            "independent_date_conflict": not valid,
        }
    ]
