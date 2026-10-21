"""Spotify release date evidence; range ordering never establishes a release day."""

from __future__ import annotations

import calendar
import re
import sqlite3
from dataclasses import dataclass
from datetime import date

RELEASE_DATE_POLICY_VERSION = "release_date_evidence_v2_legacy_year"

SCHEMA = """
CREATE TABLE IF NOT EXISTS spotify_album_date_observations (
    observation_id INTEGER PRIMARY KEY,
    spotify_album_id TEXT NOT NULL,
    release_date TEXT,
    release_date_precision TEXT,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    source_run_id TEXT,
    previous_date TEXT,
    previous_precision TEXT,
    observed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@dataclass(frozen=True)
class ReleaseDate:
    raw: str | None
    precision: str | None
    format_precision: str | None
    status: str
    # Validated string bounds retain the legacy ordering/cutoff contract.
    # They cannot establish month/day evidence without a declared precision.
    start: date | None
    end: date | None

    @property
    def comparison_start(self) -> date | None:
        return date(self.start.year, 1, 1) if self.status == "legacy" and self.start else self.start

    @property
    def comparison_end(self) -> date | None:
        return date(self.end.year, 12, 31) if self.status == "legacy" and self.end else self.end

    @property
    def exact_day(self) -> date | None:
        return self.start if self.status == "confirmed" and self.precision == "day" else None

    @property
    def display(self) -> str | None:
        # A legacy ISO string is retained, but cannot claim month/day evidence.
        if self.status == "confirmed":
            return self.raw
        return self.raw[:4] if self.status == "legacy" and self.raw else None


def parse_release_date(value: object, precision: object = None) -> ReleaseDate:
    raw = value if isinstance(value, str) else None
    declared = precision if isinstance(precision, str) else None
    if not raw:
        return ReleaseDate(raw, declared, None, "missing", None, None)
    form = {4: "year", 7: "month", 10: "day"}.get(len(raw))
    if not form or not re.fullmatch(r"[0-9]{4}(?:-[0-9]{2})?(?:-[0-9]{2})?", raw):
        return ReleaseDate(raw, declared, None, "invalid", None, None)
    try:
        year = int(raw[:4])
        month = int(raw[5:7]) if form != "year" else 1
        day = int(raw[8:10]) if form == "day" else 1
        start = date(year, month, day)
        end = (
            date(year, 12, 31)
            if form == "year"
            else date(year, month, calendar.monthrange(year, month)[1])
            if form == "month"
            else start
        )
    except ValueError:
        return ReleaseDate(raw, declared, form, "invalid", None, None)
    if precision is not None and declared != form:
        return ReleaseDate(raw, declared, form, "inconsistent", None, None)
    return ReleaseDate(raw, declared, form, "confirmed" if declared else "legacy", start, end)


def compare_release_dates(left: ReleaseDate, right: ReleaseDate) -> str:
    """same = two confirmed identical days; compatible = overlapping ranges."""
    if left.comparison_start is None or right.comparison_start is None:
        return "unknown"
    if left.comparison_end < right.comparison_start or right.comparison_end < left.comparison_start:
        return "conflict"
    if left.exact_day is not None and left.exact_day == right.exact_day:
        return "same"
    return "compatible"


def release_sort_key(value: object, precision: object = None) -> tuple:
    evidence = parse_release_date(value, precision)
    return (
        evidence.start is None,
        evidence.start or date.max,
        evidence.end or date.max,
        str(value or ""),
    )


def precision_expression(conn: sqlite3.Connection, table: str, alias: str = "") -> str:
    columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
    return (
        f"{alias + '.' if alias else ''}release_date_precision"
        if "release_date_precision" in columns
        else "NULL"
    )


def persist_release_date(conn, album, *, source="spotify_refresh", source_run_id=None):
    """Update a pair atomically, audit rejected evidence, retain a reliable old pair.

    Caller owns the transaction. Repeated observations are no-ops. Missing
    precision is never inferred into the persisted source field.
    """
    if precision_expression(conn, "spotify_album_meta") == "NULL":
        raise ValueError("release date schema migration required")
    sid = album["id"]
    row = conn.execute(
        "SELECT release_date, release_date_precision FROM spotify_album_meta WHERE spotify_album_id=?",
        (sid,),
    ).fetchone()
    if row is None:
        raise ValueError(f"unknown cached Spotify Album ID: {sid}")
    old = parse_release_date(row[0], row[1])
    new = parse_release_date(album.get("release_date"), album.get("release_date_precision"))
    relation = compare_release_dates(old, new)
    status = new.status
    accepted = new.status == "confirmed"
    if relation == "conflict":
        status, accepted = "conflict", False
    elif old.status == "confirmed" and new.status == "confirmed" and len(new.raw) < len(old.raw):
        status, accepted = "precision_regression", False
    elif old.raw == new.raw and old.precision == new.precision:
        status, accepted = "unchanged", False
    elif accepted:
        status = "accepted"
    # First legacy/invalid observation is retained verbatim, with unknown precision.
    if not old.raw and not accepted and new.raw:
        conn.execute(
            "UPDATE spotify_album_meta SET release_date=?, release_date_precision=NULL WHERE spotify_album_id=?",
            (new.raw, sid),
        )
    elif accepted:
        conn.execute(
            "UPDATE spotify_album_meta SET release_date=?, release_date_precision=? WHERE spotify_album_id=?",
            (new.raw, new.precision, sid),
        )
    last = conn.execute(
        "SELECT release_date, release_date_precision, status, source FROM spotify_album_date_observations WHERE spotify_album_id=? ORDER BY observation_id DESC LIMIT 1",
        (sid,),
    ).fetchone()
    signature = (new.raw, new.precision, status, source)
    if status != "unchanged" and (last is None or tuple(last) != signature):
        conn.execute(
            "INSERT INTO spotify_album_date_observations(spotify_album_id,release_date,release_date_precision,status,source,source_run_id,previous_date,previous_precision) VALUES (?,?,?,?,?,?,?,?)",
            (sid, new.raw, new.precision, status, source, source_run_id, old.raw, old.precision),
        )
    return status


def release_anchor_sources(conn, album_id, *, project_id=None, explicit_edition=False):
    """Read only already-established source associations for this target.

    A project primary binding is stronger than playback-container links. An
    explicit edition stays on the named member album and never borrows another
    edition's primary source. No relationship or artist identity is approved here.
    """
    from backend.domains.playback.album_project_identity import normalize_album_project_lookup

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    album = conn.execute("SELECT album_name FROM albums WHERE album_id=?", (album_id,)).fetchone()
    names = {normalize_album_project_lookup(str(album[0]))} if album else set()
    if (
        project_id is None
        and not explicit_edition
        and {"album_project_external_ids", "album_projects"}.issubset(tables)
    ):
        owners = conn.execute(
            """SELECT DISTINCT ap.project_id FROM album_projects ap
            JOIN album_project_external_ids e USING(project_id)
            WHERE ap.primary_album_id=? AND e.provider='spotify' AND e.confidence>=0.9""",
            (album_id,),
        ).fetchall()
        if len(owners) > 1:
            return []
        if owners:
            project_id = owners[0][0]
    if project_id is not None and "album_projects" in tables and not explicit_edition:
        project = conn.execute(
            "SELECT canonical_name FROM album_projects WHERE project_id=?", (project_id,)
        ).fetchone()
        if project:
            names.add(normalize_album_project_lookup(str(project[0])))
    expr = precision_expression(conn, "spotify_album_meta", "sam")
    bound = []
    if project_id is not None and "album_project_external_ids" in tables:
        bound = [
            dict(
                zip(
                    (
                        "spotify_album_id",
                        "album_name",
                        "release_date",
                        "release_date_precision",
                        "confidence",
                        "is_primary",
                    ),
                    row,
                )
            )
            for row in conn.execute(
                f"""SELECT e.external_album_id,sam.album_name,sam.release_date,{expr},e.confidence,e.is_primary
            FROM album_project_external_ids e LEFT JOIN spotify_album_meta sam
                ON sam.spotify_album_id=e.external_album_id
            WHERE e.project_id=? AND e.provider='spotify' AND e.confidence>=0.9
            ORDER BY e.external_album_id""",
                (project_id,),
            )
        ]
    if bound and not explicit_edition:
        primaries = [row for row in bound if row["is_primary"]]
        matching = [
            row
            for row in bound
            if normalize_album_project_lookup(str(row["album_name"] or "")) in names
        ]
        selected = primaries or matching or (bound if len(bound) == 1 else [])
        return [
            {key: value for key, value in row.items() if key != "is_primary"}
            | {"project_bound": True}
            for row in selected
        ]
    if not album or "album_spotify_links" not in tables:
        return []
    bound_ids = {row["spotify_album_id"] for row in bound}
    return [
        dict(
            zip(
                (
                    "spotify_album_id",
                    "album_name",
                    "release_date",
                    "release_date_precision",
                    "confidence",
                ),
                row,
            )
        )
        | {"project_bound": row[0] in bound_ids}
        for row in conn.execute(
            f"""SELECT sam.spotify_album_id,sam.album_name,sam.release_date,{expr},MAX(asl.confidence)
            FROM album_spotify_links asl JOIN spotify_album_meta sam USING(spotify_album_id)
            WHERE asl.album_id=? AND asl.confidence>=0.9
            GROUP BY sam.spotify_album_id ORDER BY sam.spotify_album_id""",
            (album_id,),
        )
        if normalize_album_project_lookup(str(row[1] or "")) in names
    ]


def project_date_precision(conn, album_id, release_date, *, project_id=None):
    """Only unambiguous linked source evidence can confirm a derived project pair."""
    if (album_id is None and project_id is None) or not release_date:
        return None
    rows = release_anchor_sources(conn, album_id, project_id=project_id)
    values = [parse_release_date(r["release_date"], r["release_date_precision"]) for r in rows]
    confirmed = {
        item.precision for item in values if item.status == "confirmed" and item.raw == release_date
    }
    if len(confirmed) != 1:
        return None
    precision = next(iter(confirmed))
    target = parse_release_date(release_date, precision)
    # Check the prospective confirmed pair, not a broadened legacy target:
    # two conflicting confirmed days must never confirm a project date.
    if any(compare_release_dates(target, item) in {"conflict", "unknown"} for item in values):
        return None
    return precision


def sync_project_release_precisions(conn, spotify_album_ids):
    """Bounded maintenance of date evidence only; manual dates/memberships stay intact."""
    ids = tuple(sorted(set(spotify_album_ids)))
    if not {"album_projects", "album_spotify_links"}.issubset(
        {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    ):
        return 0
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    external_clause = ""
    parameters = ids
    if "album_project_external_ids" in {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }:
        external_clause = f"""OR EXISTS (SELECT 1 FROM album_project_external_ids e
            WHERE e.project_id=ap.project_id AND e.provider='spotify'
            AND e.external_album_id IN ({placeholders}))"""
        parameters += ids
    projects = conn.execute(
        f"""SELECT ap.project_id,ap.primary_album_id,ap.release_date,ap.release_date_precision
        FROM album_projects ap WHERE ap.is_manual=0 AND (
            EXISTS (SELECT 1 FROM album_spotify_links asl WHERE asl.album_id=ap.primary_album_id
                    AND asl.spotify_album_id IN ({placeholders})) {external_clause})""",
        parameters,
    ).fetchall()
    changed = 0
    for project in projects:
        raw = project[2]
        # Multiple independent established sources can confirm the same pair;
        # differing source pairs never establish a correction by majority.
        sources = release_anchor_sources(conn, project[1], project_id=project[0])
        values = [
            parse_release_date(r["release_date"], r["release_date_precision"]) for r in sources
        ]
        pairs = {(value.raw, value.precision) for value in values}
        if (
            project[3] is None
            and values
            and all(value.status == "confirmed" for value in values)
            and len(pairs) == 1
        ):
            old, new = parse_release_date(raw), values[0]
            if old.status == "missing" or compare_release_dates(old, new) == "compatible":
                raw = new.raw
        precision = project_date_precision(conn, project[1], raw, project_id=project[0])
        changed += conn.execute(
            """UPDATE album_projects SET release_date=?,release_date_precision=?
            WHERE project_id=? AND (release_date IS NOT ? OR release_date_precision IS NOT ?)""",
            (raw, precision, project[0], raw, precision),
        ).rowcount
    return changed


def release_evidence_inventory(conn):
    """Read-only inventory of known referenced IDs and retryable evidence gaps.

    Confirmed coarse dates are final source facts. Rejected conflicts and
    already observed incomplete artist IDs need review instead of repeated
    automatic requests. Explicit maintenance can still re-observe these IDs.
    Orphan cached albums are reported separately, never automatically fetched.
    """
    from backend.domains.metadata.spotify_album_credits import evidence_schema_available

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    references = {}
    for table, column in (
        ("plays", "spotify_album_id_at_play"),
        ("spotify_track_meta", "spotify_album_id"),
        ("album_spotify_links", "spotify_album_id"),
        ("albums", "spotify_album_id"),
        ("album_project_external_ids", "external_album_id"),
    ):
        if table not in tables:
            continue
        columns = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
        if column not in columns:
            continue
        provider_filter = " AND provider='spotify'" if table == "album_project_external_ids" else ""
        for row in conn.execute(
            f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL AND "{column}"!=\'\''
            + provider_filter
        ):
            references.setdefault(str(row[0]), []).append(table)
    precision = precision_expression(conn, "spotify_album_meta")
    cached = {
        str(r[0]): (r[1], r[2])
        for r in conn.execute(
            f"SELECT spotify_album_id,release_date,{precision} FROM spotify_album_meta"
        )
    }
    dates = {}
    if "spotify_album_date_observations" in tables:
        dates = {
            r[0]: r[1]
            for r in conn.execute(
                """SELECT o.spotify_album_id,o.status FROM spotify_album_date_observations o
            JOIN (SELECT spotify_album_id,MAX(observation_id) AS latest
                  FROM spotify_album_date_observations GROUP BY spotify_album_id) x
            ON o.observation_id=x.latest"""
            )
        }
    credits = {}
    rejected = set()
    if evidence_schema_available(conn):
        for row in conn.execute(
            "SELECT spotify_album_id,spotify_artist_id FROM spotify_album_artist_credits"
        ):
            credits.setdefault(row[0], []).append(row[1])
        rejected = {
            r[0]
            for r in conn.execute(
                """SELECT e.spotify_album_id FROM spotify_album_credit_events e
            JOIN (SELECT spotify_album_id,MAX(event_id) AS latest
                  FROM spotify_album_credit_events GROUP BY spotify_album_id) x
            ON e.event_id=x.latest WHERE e.event_type='rejected'"""
            )
        }
    items = []
    for sid in sorted(references):
        raw, prec = cached.get(sid, (None, None))
        value = parse_release_date(raw, prec)
        reasons, pending = [], []
        if sid not in cached:
            reasons.append("cache_missing")
            pending.append("cache_missing")
        if dates.get(sid) in {"conflict", "precision_regression"}:
            reasons.append("date_review_required")
        elif value.status != "confirmed":
            reasons.append("date_" + value.status)
            pending.append("date_" + value.status)
        elif value.precision != "day":
            reasons.append("date_precision_" + value.precision)
        if sid in rejected:
            reasons.append("artist_review_required")
        elif sid not in credits:
            reasons.append("album_artists_missing")
            pending.append("album_artists_missing")
        elif not all(credits[sid]):
            reasons.append("artist_ids_unconfirmed")
        items.append(
            {
                "id": sid,
                "references": references[sid],
                "cached": sid in cached,
                "release_date": raw,
                "release_date_precision": prec,
                "date_status": value.status,
                "reasons": reasons,
                "retryable_reasons": pending,
                "needs_fetch": bool(pending),
            }
        )
    return {"items": items, "orphan_cached_ids": sorted(set(cached) - set(references))}


def select_missing_release_evidence_ids(conn, limit=200):
    return [r["id"] for r in release_evidence_inventory(conn)["items"] if r["needs_fetch"]][:limit]


def install_album_release_evidence(conn, albums, *, source="spotify_refresh", source_run_id=None):
    """Caller-owned transaction, shared date/Album artist response, no track fetching."""
    from backend.domains.metadata.spotify_album_credits import persist_album_artists

    results = {}
    for album in albums:
        if not album:
            continue
        sid = album["id"]
        results[sid] = {
            "date": persist_release_date(conn, album, source=source, source_run_id=source_run_id),
            "artists": persist_album_artists(
                conn, album, source=source, source_run_id=source_run_id
            ),
        }
    changed = sync_project_release_precisions(conn, results)
    return {"evidence_outcomes": results, "project_precision_changes": changed}
