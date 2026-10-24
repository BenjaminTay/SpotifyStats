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


def _guard(conn, project_id, source_id, *, verify_artist=True, date_kind="original_release"):
    from backend.domains.metadata.release_dates import _release_anchor_sources
    from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
    from backend.providers.spotify.album_tracks import complete_track_ids

    p = conn.execute(
        "SELECT primary_album_id,artist_id,is_manual,release_date,release_date_precision FROM album_projects WHERE project_id=?",
        (project_id,),
    ).fetchone()
    if p is None or p[2]:
        raise ValueError("unknown_or_manual_project")
    edition_album_ids = []
    sources = _release_anchor_sources(conn, p[0], project_id=project_id)
    if date_kind == "edition_release":
        sources = []
        for member in conn.execute(
            "SELECT album_id FROM album_project_albums WHERE project_id=? ORDER BY album_id",
            (project_id,),
        ):
            candidates = _release_anchor_sources(
                conn, member[0], project_id=project_id, explicit_edition=True
            )
            if source_id in {row["spotify_album_id"] for row in candidates}:
                edition_album_ids.append(member[0])
                sources.extend(candidates)
        bound = (
            conn.execute(
                "SELECT 1 FROM album_project_external_ids WHERE project_id=? AND provider='spotify' AND external_album_id=? AND confidence>=0.9",
                (project_id, source_id),
            ).fetchone()
            if _table_available(conn, "album_project_external_ids")
            else None
        )
        if bound and not edition_album_ids:
            edition_album_ids = [p[0]]
            sources = [{"spotify_album_id": source_id}]
    if source_id not in {r["spotify_album_id"] for r in sources}:
        raise ValueError("source_not_established_for_project")
    resolver = AlbumArtistResolver(conn) if verify_artist else None
    name = conn.execute("SELECT artist_name FROM artists WHERE artist_id=?", (p[1],)).fetchone()
    reviewed_participation = any(
        r["spotify_album_id"] == source_id and r.get("reference_verified") for r in sources
    )
    if not name or (
        verify_artist
        and resolver.target_presence(source_id, p[1]) != "verified_id"
        and not reviewed_participation
    ):
        raise ValueError("artist_identity_unconfirmed")
    s = conn.execute(
        "SELECT release_date,release_date_precision,track_list,total_tracks FROM spotify_album_meta WHERE spotify_album_id=?",
        (source_id,),
    ).fetchone()
    catalog = complete_track_ids(s[2], s[3]) if s else None
    if catalog is None:
        raise ValueError("incomplete_source_catalog")
    guard = {
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
    }
    if date_kind == "edition_release":
        guard["edition_album_ids"] = edition_album_ids
    return guard, [p[3], p[4]]


def _table_available(conn, name):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


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
    guard, previous = _guard(
        conn, item["project_id"], item["spotify_album_id"], date_kind=item["date_kind"]
    )
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
    return _review_assertion(
        conn, assertion_id, decision, actor=actor, reason=reason, run_id=run_id
    )


def _review_assertion(
    conn, assertion_id, decision, *, actor, reason, run_id, explicit_conflict=False
):
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

            guard, current = _guard(
                conn, row["project_id"], row["spotify_album_id"], date_kind=row["date_kind"]
            )
            if guard != stored:
                raise ValueError("source_or_project_identity_changed")
            raw = parse_release_date(*guard["source_pair"])
            if not explicit_conflict and compare_release_dates(raw, day) not in (
                "compatible",
                "same",
            ):
                raise ValueError("independent_date_conflicts_with_source")
            for source in (
                _release_anchor_sources(
                    conn, guard["primary_album_id"], project_id=row["project_id"]
                )
                if row["date_kind"] == "original_release"
                else []
            ):
                other = parse_release_date(source["release_date"], source["release_date_precision"])
                if not explicit_conflict and compare_release_dates(other, day) not in (
                    "compatible",
                    "same",
                ):
                    raise ValueError("independent_date_conflicts_with_source_set")
            if row["date_kind"] == "original_release" and current != json.loads(
                row["previous_project_pair_json"]
            ):
                raise ValueError("project_pair_changed")
            if (
                not explicit_conflict
                and row["date_kind"] == "original_release"
                and compare_release_dates(parse_release_date(*current), day)
                not in (
                    "compatible",
                    "same",
                )
            ):
                raise ValueError("independent_date_conflicts_with_project")
            if conn.execute(
                "SELECT 1 FROM album_release_date_assertions WHERE project_id=? AND status='approved' AND date_kind=? "
                "AND (date_kind='original_release' OR (spotify_album_id=? AND territory=? AND medium=?))",
                (
                    row["project_id"],
                    row["date_kind"],
                    row["spotify_album_id"],
                    row["territory"],
                    row["medium"],
                ),
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
            if row["date_kind"] == "original_release" and current != [row["release_date"], "day"]:
                raise ValueError("approved_project_pair_changed")
            pair = json.loads(row["previous_project_pair_json"])
        if row["date_kind"] == "original_release":
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


def overlay_source_dates(conn, rows, *, project_id, album_id, date_kind="original_release"):
    """Read approved facts only; never create schema, approve sources or borrow editions."""
    if not rows or project_id is None or not _exists(conn):
        return rows
    active = conn.execute(
        "SELECT assertion_id FROM album_release_date_assertions WHERE project_id=? AND status='approved' AND date_kind=?",
        (project_id, date_kind),
    ).fetchall()
    if not active:
        return rows
    matching = [_row(conn, row[0]) for row in active]
    matching = [
        item
        for item in matching
        if item["spotify_album_id"] in {row["spotify_album_id"] for row in rows}
    ]
    if not matching:
        return rows
    if len(matching) != 1:
        return [{**row, "independent_date_conflict": True} for row in rows]
    evidence = matching[0]
    stored = json.loads(evidence["guard_json"])
    if (date_kind == "original_release" and album_id != stored["primary_album_id"]) or (
        date_kind == "edition_release" and album_id not in stored.get("edition_album_ids", [])
    ):
        return rows
    from backend.domains.metadata.album_release_references import available

    conflict_review = (
        conn.execute(
            "SELECT guard_json FROM album_release_date_conflict_reviews WHERE assertion_id=?",
            (evidence["assertion_id"],),
        ).fetchone()
        if available(conn, "album_release_date_conflict_reviews")
        else None
    )
    if conflict_review:
        expected = json.loads(conflict_review[0])
        try:
            valid = _conflict_guard(conn, evidence) == expected
            if date_kind == "original_release":
                pair = conn.execute(
                    "SELECT release_date,release_date_precision FROM album_projects WHERE project_id=?",
                    (project_id,),
                ).fetchone()
                valid = valid and list(pair) == [evidence["release_date"], "day"]
        except ValueError:
            valid = False
        if not valid:
            return [{**row, "independent_date_conflict": True} for row in rows]
    result = []
    for row in rows:
        if row["spotify_album_id"] != evidence["spotify_album_id"] and not conflict_review:
            result.append(row)
            continue
        try:
            guard, _ = _guard(
                conn,
                project_id,
                evidence["spotify_album_id"],
                verify_artist=False,
                date_kind=date_kind,
            )
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


def _conflict_guard(conn, row):
    from backend.domains.metadata.album_release_references import review_guard
    from backend.domains.metadata.release_dates import _release_anchor_sources

    guard = review_guard(conn, row["project_id"], row["spotify_album_id"])
    original, _ = _guard(
        conn, row["project_id"], row["spotify_album_id"], date_kind=row["date_kind"]
    )
    guard["date_source_guard"] = original
    albums = original.get("edition_album_ids", [original["primary_album_id"]])
    guard["source_sets"] = [
        [
            album,
            _release_anchor_sources(
                conn,
                album,
                project_id=row["project_id"],
                explicit_edition=row["date_kind"] == "edition_release",
            ),
        ]
        for album in albums
    ]
    return guard


def prepare_date_conflict(conn, assertion_id):
    """Explicit, read-only conflict proposal; ordinary precision approval stays strict."""
    row = _row(conn, assertion_id)
    if row["status"] != "pending":
        raise ValueError("pending_date_assertion_required")
    return {"assertion": row, "guard": _conflict_guard(conn, row)}


def approve_date_conflict(conn, proposal, *, actor, reason, run_id):
    """Caller must fence/reconcile L3; source declarations are never rewritten."""
    from backend.domains.metadata.album_track_release_evidence import require_transaction

    require_transaction(conn, actor, reason)
    row = proposal["assertion"]
    existing = conn.execute(
        "SELECT guard_json FROM album_release_date_conflict_reviews WHERE assertion_id=?",
        (row["assertion_id"],),
    ).fetchone()
    current = _row(conn, row["assertion_id"])
    if existing and current["status"] == "approved":
        if (
            json.loads(existing[0]) != proposal["guard"]
            or _conflict_guard(conn, current) != proposal["guard"]
        ):
            raise ValueError("approved_conflict_dependencies_changed")
        project = conn.execute(
            "SELECT release_date,release_date_precision FROM album_projects WHERE project_id=?",
            (row["project_id"],),
        ).fetchone()
        if row["date_kind"] == "original_release" and list(project) != [row["release_date"], "day"]:
            raise ValueError("approved_project_pair_changed")
        return False
    if prepare_date_conflict(conn, row["assertion_id"]) != proposal:
        raise ValueError("stale_date_conflict_proposal")
    # Savepoint also undoes an audit record if the underlying review rejects.
    conn.execute("SAVEPOINT explicit_date_conflict")
    try:
        conn.execute(
            "INSERT INTO album_release_date_conflict_reviews(assertion_id,guard_json,actor,reason,reviewed_at) VALUES(?,?,?,?,?)",
            (
                row["assertion_id"],
                _json(proposal["guard"]),
                actor,
                reason,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        changed = _review_assertion(
            conn,
            row["assertion_id"],
            "approve",
            actor=actor,
            reason=reason,
            run_id=run_id,
            explicit_conflict=True,
        )
        conn.execute("RELEASE SAVEPOINT explicit_date_conflict")
        return changed
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT explicit_date_conflict")
        conn.execute("RELEASE SAVEPOINT explicit_date_conflict")
        raise
