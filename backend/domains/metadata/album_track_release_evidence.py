"""Reviewed per-track edition facts, independent of project membership and dates."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

POLICY_VERSION = "album_track_release_evidence_v1"
SCHEMA = """
CREATE TABLE IF NOT EXISTS album_track_release_assertions (
 assertion_id INTEGER PRIMARY KEY,
 project_id INTEGER NOT NULL REFERENCES album_projects(project_id),
 anchor_track_id INTEGER NOT NULL REFERENCES tracks(track_id),
 spotify_album_id TEXT NOT NULL,
 spotify_track_id TEXT NOT NULL,
 membership_kind TEXT NOT NULL CHECK(membership_kind IN ('original','bonus','reissue')),
 included_on TEXT,
 date_kind TEXT NOT NULL CHECK(date_kind IN ('original_release','edition_release')),
 territory TEXT NOT NULL,
 medium TEXT NOT NULL,
 sources_json TEXT NOT NULL,
 guard_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','revoked')),
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL,
 reviewed_at TEXT,
 policy_version TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_album_track_release_approved
 ON album_track_release_assertions(project_id,anchor_track_id,spotify_album_id,spotify_track_id)
 WHERE status='approved';
CREATE TABLE IF NOT EXISTS album_track_release_events (
 event_id INTEGER PRIMARY KEY,
 assertion_id INTEGER NOT NULL REFERENCES album_track_release_assertions(assertion_id),
 action TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS album_release_corrections (
 request_id TEXT PRIMARY KEY,
 request_json TEXT NOT NULL,
 result_json TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 created_at TEXT NOT NULL
);
"""


def create_schema(conn):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now():
    return datetime.now(timezone.utc).isoformat()


def require_transaction(conn, actor, reason):
    if not conn.in_transaction:
        raise ValueError("caller_transaction_required")
    if not all(isinstance(v, str) and v.strip() for v in (actor, reason)):
        raise ValueError("actor_and_reason_required")


def validate_sources(sources):
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise ValueError("bounded_source_evidence_required")
    for source in sources:
        if not isinstance(source, dict) or not all(
            isinstance(source.get(k), str) and source[k].strip()
            for k in ("url", "title", "claim", "observed_at")
        ):
            raise ValueError("source_provenance_required")
        url = urlsplit(source["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("public_https_evidence_url_required")


def source_guard(conn, project_id, source_id, *, resolver=None):
    from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
    from backend.providers.spotify.album_tracks import complete_track_ids

    project = conn.execute(
        "SELECT primary_album_id,artist_id,scope,is_manual,canonical_name,project_type FROM album_projects WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if project is None or project[2] != "release" or project[3]:
        raise ValueError("unknown_or_manual_release_project")
    source = conn.execute(
        "SELECT album_name,album_type,release_date,release_date_precision,track_list,total_tracks "
        "FROM spotify_album_meta WHERE spotify_album_id=?",
        (source_id,),
    ).fetchone()
    catalog = complete_track_ids(source[4], source[5]) if source else None
    if not catalog or source[1] not in ("album", "ep", "compilation"):
        raise ValueError("complete_release_catalog_required")
    name = conn.execute(
        "SELECT artist_name FROM artists WHERE artist_id=?", (project[1],)
    ).fetchone()
    resolver = resolver or AlbumArtistResolver(conn)
    if not name or resolver.match(source_id, project[1], name[0]) != "verified_id":
        raise ValueError("artist_identity_unconfirmed")
    guard = {
        "project_identity": list(project),
        "source_identity": list(source[:4]) + [source[5]],
        "catalog_digest": hashlib.sha256(_json(catalog).encode()).hexdigest(),
        "artist_ids": [r["spotify_artist_id"] for r in resolver.read(source_id)],
    }
    return guard, catalog


def assertion_guard(conn, project_id, track_id, source_id, spotify_track_id, *, context=None):
    if context is None:
        guard, catalog = source_guard(conn, project_id, source_id)
    else:
        key = (project_id, source_id)
        if key not in context["sources"]:
            context["sources"][key] = source_guard(
                conn, project_id, source_id, resolver=context["resolver"]
            )
        guard, catalog = context["sources"][key]
    membership = conn.execute(
        "SELECT membership_role,min_merge_level,source_album_id,is_exclusive,inferred "
        "FROM album_project_tracks WHERE project_id=? AND track_id=?",
        (project_id, track_id),
    ).fetchone()
    owner = conn.execute(
        "SELECT track_id FROM spotify_track_owners WHERE spotify_track_id=?",
        (spotify_track_id,),
    ).fetchone()
    if not membership or not owner or owner[0] != track_id or spotify_track_id not in catalog:
        raise ValueError("edition_track_membership_unproven")
    return {
        **guard,
        "membership": list(membership),
        "catalog_position": catalog.index(spotify_track_id) + 1,
    }


def record_assertion(conn, item, *, actor, reason):
    from backend.domains.metadata.release_dates import parse_release_date

    require_transaction(conn, actor, reason)
    if type(item.get("project_id")) is not int or type(item.get("anchor_track_id")) is not int:
        raise ValueError("stable_project_and_track_required")
    if item.get("membership_kind") not in ("original", "bonus", "reissue"):
        raise ValueError("membership_kind_required")
    if item.get("date_kind") not in ("original_release", "edition_release"):
        raise ValueError("date_kind_required")
    if (
        item.get("included_on") is not None
        and parse_release_date(item["included_on"], "day").exact_day is None
    ):
        raise ValueError("included_on_must_be_confirmed_day_or_null")
    for field in ("spotify_album_id", "spotify_track_id", "territory", "medium"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(field + "_required")
    validate_sources(item.get("sources"))
    guard = assertion_guard(
        conn,
        item["project_id"],
        item["anchor_track_id"],
        item["spotify_album_id"],
        item["spotify_track_id"],
    )
    cur = conn.execute(
        "INSERT INTO album_track_release_assertions(project_id,anchor_track_id,spotify_album_id,"
        "spotify_track_id,membership_kind,included_on,date_kind,territory,medium,sources_json,guard_json,"
        "status,actor,reason,created_at,policy_version) VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?,?)",
        (
            item["project_id"],
            item["anchor_track_id"],
            item["spotify_album_id"],
            item["spotify_track_id"],
            item["membership_kind"],
            item.get("included_on"),
            item["date_kind"],
            item["territory"],
            item["medium"],
            _json(item["sources"]),
            _json(guard),
            actor,
            reason,
            _now(),
            POLICY_VERSION,
        ),
    )
    conn.execute(
        "INSERT INTO album_track_release_events(assertion_id,action,actor,reason,observed_at) VALUES(?,'record',?,?,?)",
        (cur.lastrowid, actor, reason, _now()),
    )
    return cur.lastrowid


def read_assertion(conn, assertion_id):
    cur = conn.execute(
        "SELECT * FROM album_track_release_assertions WHERE assertion_id=?", (assertion_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("assertion_not_found")
    return dict(zip([column[0] for column in cur.description], row))


def valid_assertion(conn, row, *, context=None):
    try:
        valid = row["policy_version"] == POLICY_VERSION and assertion_guard(
            conn,
            row["project_id"],
            row["anchor_track_id"],
            row["spotify_album_id"],
            row["spotify_track_id"],
            context=context,
        ) == json.loads(row["guard_json"])
        if row["status"] == "approved":
            owner = conn.execute(
                "SELECT project_id FROM album_project_external_ids WHERE provider='spotify' AND external_album_id=?",
                (row["spotify_album_id"],),
            ).fetchone()
            valid = valid and owner is not None and owner[0] == row["project_id"]
        return valid
    except (ValueError, TypeError):
        return False


def review_assertion(conn, assertion_id, decision, *, actor, reason):
    from backend.domains.playback.album_projects import _bump_album_project_revision

    require_transaction(conn, actor, reason)
    row = read_assertion(conn, assertion_id)
    status = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}.get(decision)
    if status is None:
        raise ValueError("unknown_review_decision")
    if row["status"] == status:
        return False
    if (decision == "revoke" and row["status"] != "approved") or (
        decision != "revoke" and row["status"] != "pending"
    ):
        raise ValueError("invalid_review_transition")
    if decision == "approve":
        if not valid_assertion(conn, row):
            raise ValueError("source_or_membership_changed")
        owner = conn.execute(
            "SELECT project_id FROM album_project_external_ids WHERE provider='spotify' AND external_album_id=?",
            (row["spotify_album_id"],),
        ).fetchone()
        if owner is None or owner[0] != row["project_id"]:
            raise ValueError("explicit_project_source_required")
    conn.execute(
        "UPDATE album_track_release_assertions SET status=?,reviewed_at=? WHERE assertion_id=?",
        (status, _now(), assertion_id),
    )
    conn.execute(
        "INSERT INTO album_track_release_events(assertion_id,action,actor,reason,observed_at) VALUES(?,?,?,?,?)",
        (assertion_id, decision, actor, reason, _now()),
    )
    if decision in ("approve", "revoke"):
        _bump_album_project_revision(conn)
    return True


def load_approved(conn):
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='album_track_release_assertions'"
    ).fetchone():
        return {}
    cur = conn.execute(
        "SELECT * FROM album_track_release_assertions WHERE status='approved' ORDER BY assertion_id"
    )
    columns = [column[0] for column in cur.description]
    rows = cur.fetchall()
    if not rows:
        return {}
    from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver

    context = {"resolver": AlbumArtistResolver(conn), "sources": {}}
    result = {}
    for raw in rows:
        row = dict(zip(columns, raw))
        row["valid"] = valid_assertion(conn, row, context=context)
        result.setdefault((row["project_id"], row["anchor_track_id"]), []).append(row)
    return result
