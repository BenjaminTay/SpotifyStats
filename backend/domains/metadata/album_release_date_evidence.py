"""Reviewed, project-scoped date assertions; Spotify observations remain immutable."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from urllib.parse import urlsplit

SCHEMA = """
CREATE TABLE IF NOT EXISTS album_release_date_assertions (
 assertion_id INTEGER PRIMARY KEY,
 evidence_key TEXT NOT NULL UNIQUE,
 project_id INTEGER NOT NULL,
 spotify_album_id TEXT NOT NULL,
 release_date TEXT NOT NULL,
 date_kind TEXT NOT NULL CHECK(date_kind IN ('original_release','edition_release')),
 territory TEXT NOT NULL,
 medium TEXT NOT NULL,
 scope_note TEXT NOT NULL,
 sources_json TEXT NOT NULL,
 guard_json TEXT NOT NULL,
 previous_project_pair_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','revoked')),
 recorded_by TEXT NOT NULL,
 recorded_at TEXT NOT NULL,
 reviewed_by TEXT,
 reviewed_at TEXT,
 review_reason TEXT,
 run_id TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_album_date_approved_project
 ON album_release_date_assertions(project_id) WHERE status='approved';
CREATE TABLE IF NOT EXISTS album_release_date_events (
 event_id INTEGER PRIMARY KEY,
 assertion_id INTEGER NOT NULL REFERENCES album_release_date_assertions(assertion_id),
 action TEXT NOT NULL,
 actor TEXT NOT NULL,
 reason TEXT NOT NULL,
 run_id TEXT NOT NULL,
 observed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS album_release_date_revision_state (
 state_id INTEGER PRIMARY KEY CHECK(state_id=1),
 current_revision INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO album_release_date_revision_state(state_id) VALUES(1);
"""


def create_schema(conn):
    for statement in SCHEMA.split(";"):
        if statement.strip():
            conn.execute(statement)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _exists(conn):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='album_release_date_assertions'"
        ).fetchone()
        is not None
    )


def _guard(conn, project_id, source_id, *, verify_artist=True):
    from backend.domains.metadata.release_dates import _release_anchor_sources
    from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
    from backend.providers.spotify.album_tracks import complete_track_ids

    p = conn.execute(
        "SELECT primary_album_id,artist_id,is_manual,release_date,release_date_precision FROM album_projects WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if p is None or p[2]:
        raise ValueError("unknown_or_manual_project")
    sources = _release_anchor_sources(conn, p[0], project_id=project_id)
    if source_id not in {r["spotify_album_id"] for r in sources}:
        raise ValueError("source_not_established_for_project")
    resolver = AlbumArtistResolver(conn) if verify_artist else None
    name = conn.execute("SELECT artist_name FROM artists WHERE artist_id=?", (p[1],)).fetchone()
    if not name or (verify_artist and resolver.match(source_id, p[1], name[0]) != "verified_id"):
        raise ValueError("artist_identity_unconfirmed")
    s = conn.execute(
        "SELECT release_date,release_date_precision,track_list,total_tracks FROM spotify_album_meta WHERE spotify_album_id=?",
        (source_id,),
    ).fetchone()
    catalog = complete_track_ids(s[2], s[3]) if s else None
    if catalog is None:
        raise ValueError("incomplete_source_catalog")
    return {
        "primary_album_id": p[0],
        "artist_id": p[1],
        "source_pair": [s[0], s[1]],
        "catalog_digest": hashlib.sha256(_json(catalog).encode()).hexdigest(),
        "artist_ids": [
            r[0]
            for r in conn.execute(
                "SELECT spotify_artist_id FROM spotify_album_artist_credits WHERE spotify_album_id=? ORDER BY credit_order",
                (source_id,),
            )
        ],
    }, [p[3], p[4]]


def _event(conn, assertion_id, action, actor, reason, run_id):
    if not all(isinstance(v, str) and v.strip() for v in (actor, reason, run_id)):
        raise ValueError("actor_reason_and_run_required")
    conn.execute(
        "INSERT INTO album_release_date_events(assertion_id,action,actor,reason,run_id,observed_at) VALUES(?,?,?,?,?,?)",
        (assertion_id, action, actor, reason, run_id, datetime.now(timezone.utc).isoformat()),
    )


def record_assertion(conn, item, *, actor, run_id):
    """Register evidence without approving dates, source identity or memberships."""
    from backend.domains.metadata.release_dates import parse_release_date

    if not conn.in_transaction:
        raise ValueError("caller_transaction_required")
    if type(item.get("project_id")) is not int or not isinstance(item.get("spotify_album_id"), str):
        raise ValueError("explicit_project_and_source_required")
    if parse_release_date(item.get("release_date"), "day").exact_day is None:
        raise ValueError("confirmed_calendar_day_required")
    if item.get("date_kind") not in ("original_release", "edition_release"):
        raise ValueError("date_kind_required")
    for field in ("territory", "medium", "scope_note"):
        if not isinstance(item.get(field), str) or not item[field].strip():
            raise ValueError(field + "_required")
    sources = item.get("sources")
    if not isinstance(sources, list) or not 1 <= len(sources) <= 20:
        raise ValueError("bounded_source_evidence_required")
    for source in sources:
        if not isinstance(source, dict) or any(
            not isinstance(source.get(k), str) or not source[k].strip()
            for k in ("url", "title", "source_kind", "claim", "observed_at")
        ):
            raise ValueError("source_provenance_required")
        url = urlsplit(source["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password:
            raise ValueError("public_https_evidence_url_required")
    guard, previous = _guard(conn, item["project_id"], item["spotify_album_id"])
    if item.get("expected_source_pair", guard["source_pair"]) != guard["source_pair"]:
        raise ValueError("source_pair_changed")
    if item.get("expected_project_pair", previous) != previous:
        raise ValueError("project_pair_changed")
    fields = (
        "project_id",
        "spotify_album_id",
        "release_date",
        "date_kind",
        "territory",
        "medium",
        "scope_note",
        "sources",
    )
    payload = {k: item[k] for k in fields}
    key = hashlib.sha256(_json({"assertion": payload, "guard": guard}).encode()).hexdigest()
    row = conn.execute(
        "SELECT assertion_id FROM album_release_date_assertions WHERE evidence_key=?", (key,)
    ).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO album_release_date_assertions(evidence_key,project_id,spotify_album_id,release_date,date_kind,territory,medium,scope_note,sources_json,guard_json,previous_project_pair_json,status,recorded_by,recorded_at,run_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?)",
        (
            key,
            item["project_id"],
            item["spotify_album_id"],
            item["release_date"],
            item["date_kind"],
            item["territory"],
            item["medium"],
            item["scope_note"],
            _json(sources),
            _json(guard),
            _json(previous),
            actor,
            datetime.now(timezone.utc).isoformat(),
            run_id,
        ),
    )
    _event(conn, cur.lastrowid, "record", actor, "source evidence registered; not approved", run_id)
    return cur.lastrowid


def _row(conn, assertion_id):
    cur = conn.execute(
        "SELECT * FROM album_release_date_assertions WHERE assertion_id=?", (assertion_id,)
    )
    row = cur.fetchone()
    if row is None:
        raise ValueError("assertion_not_found")
    return dict(zip([c[0] for c in cur.description], row))


def _bump(conn):
    from backend.domains.playback.album_projects import _bump_album_project_revision

    conn.execute(
        "UPDATE album_release_date_revision_state SET current_revision=current_revision+1 WHERE state_id=1"
    )
    _bump_album_project_revision(conn)


def review_assertion(conn, assertion_id, decision, *, actor, reason, run_id):
    """Caller must fence and reconcile L3 before committing approval/revocation."""
    from backend.domains.metadata.release_dates import compare_release_dates, parse_release_date

    if not conn.in_transaction:
        raise ValueError("caller_transaction_required")
    if decision not in ("approve", "reject", "revoke"):
        raise ValueError("unknown_review_decision")
    row = _row(conn, assertion_id)
    new_status = {"approve": "approved", "reject": "rejected", "revoke": "revoked"}[decision]
    if row["status"] == new_status:
        return False
    if (decision == "revoke" and row["status"] != "approved") or (
        decision != "revoke" and row["status"] != "pending"
    ):
        raise ValueError("invalid_review_transition")
    if decision in ("approve", "revoke"):
        stored = json.loads(row["guard_json"])
        day = parse_release_date(row["release_date"], "day")
        if decision == "approve":
            from backend.domains.metadata.release_dates import _release_anchor_sources

            guard, current = _guard(conn, row["project_id"], row["spotify_album_id"])
            if guard != stored:
                raise ValueError("source_or_project_identity_changed")
            raw = parse_release_date(*guard["source_pair"])
            if compare_release_dates(raw, day) not in ("compatible", "same"):
                raise ValueError("independent_date_conflicts_with_source")
            for source in _release_anchor_sources(
                conn, guard["primary_album_id"], project_id=row["project_id"]
            ):
                other = parse_release_date(source["release_date"], source["release_date_precision"])
                if compare_release_dates(other, day) not in ("compatible", "same"):
                    raise ValueError("independent_date_conflicts_with_source_set")
            if current != json.loads(row["previous_project_pair_json"]):
                raise ValueError("project_pair_changed")
            if compare_release_dates(parse_release_date(*current), day) not in (
                "compatible",
                "same",
            ):
                raise ValueError("independent_date_conflicts_with_project")
            if conn.execute(
                "SELECT 1 FROM album_release_date_assertions WHERE project_id=? AND status='approved'",
                (row["project_id"],),
            ).fetchone():
                raise ValueError("project_already_has_approved_date")
            pair = [row["release_date"], "day"]
        else:
            # An obsolete source observation must remain revocable. Fence the
            # project identity and published date without requiring stale source
            # evidence to become valid again first.
            project = conn.execute(
                "SELECT primary_album_id,artist_id,is_manual,release_date,release_date_precision FROM album_projects WHERE project_id=?",
                (row["project_id"],),
            ).fetchone()
            if project is None or tuple(project[:3]) != (
                stored["primary_album_id"],
                stored["artist_id"],
                0,
            ):
                raise ValueError("source_or_project_identity_changed")
            current = list(project[3:])
            if current != [row["release_date"], "day"]:
                raise ValueError("approved_project_pair_changed")
            pair = json.loads(row["previous_project_pair_json"])
        conn.execute(
            "UPDATE album_projects SET release_date=?,release_date_precision=? WHERE project_id=?",
            (*pair, row["project_id"]),
        )
        _bump(conn)
    conn.execute(
        "UPDATE album_release_date_assertions SET status=?,reviewed_by=?,reviewed_at=?,review_reason=?,run_id=? WHERE assertion_id=?",
        (new_status, actor, datetime.now(timezone.utc).isoformat(), reason, run_id, assertion_id),
    )
    _event(conn, assertion_id, decision, actor, reason, run_id)
    return True


def overlay_source_dates(conn, rows, *, project_id, album_id):
    """Read approved facts only; never create schema, approve sources or borrow editions."""
    if not rows or project_id is None or not _exists(conn):
        return rows
    active = conn.execute(
        "SELECT assertion_id FROM album_release_date_assertions WHERE project_id=? AND status='approved'",
        (project_id,),
    ).fetchone()
    if active is None:
        return rows
    evidence = _row(conn, active[0])
    stored = json.loads(evidence["guard_json"])
    if album_id != stored["primary_album_id"]:
        return rows
    result = []
    for row in rows:
        if row["spotify_album_id"] != evidence["spotify_album_id"]:
            result.append(row)
            continue
        try:
            guard, _ = _guard(conn, project_id, evidence["spotify_album_id"], verify_artist=False)
            valid = guard == stored
        except ValueError:
            valid = False
        # A source refresh/identity change must not quietly reuse a reviewed fact.
        if not valid:
            result.append({**row, "independent_date_conflict": True})
            continue
        result.append(
            {
                **row,
                "spotify_release_date": row["release_date"],
                "spotify_release_date_precision": row["release_date_precision"],
                "release_date": evidence["release_date"],
                "release_date_precision": "day",
                "release_date_origin": "independent",
                "release_date_assertion_id": evidence["assertion_id"],
            }
        )
    return result
