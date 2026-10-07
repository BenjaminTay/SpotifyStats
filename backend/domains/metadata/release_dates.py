"""Spotify release date evidence; range ordering never establishes a release day."""

from __future__ import annotations

import calendar
import re
import sqlite3
from dataclasses import dataclass
from datetime import date

RELEASE_DATE_POLICY_VERSION = "release_date_evidence_v1"

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
    start: date | None
    end: date | None

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
    if left.start is None or right.start is None:
        return "unknown"
    if left.end < right.start or right.end < left.start:
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


def project_date_precision(conn, album_id, release_date):
    """Only unambiguous linked source evidence can confirm a derived project pair."""
    if album_id is None or not release_date:
        return None
    expr = precision_expression(conn, "spotify_album_meta", "sam")
    rows = conn.execute(
        f"SELECT sam.release_date, {expr} FROM album_spotify_links asl JOIN spotify_album_meta sam USING(spotify_album_id) WHERE asl.album_id=? AND asl.confidence>=0.9",
        (album_id,),
    ).fetchall()
    values = [parse_release_date(r[0], r[1]) for r in rows]
    target = parse_release_date(release_date)
    if not values or any(
        compare_release_dates(target, item) in {"conflict", "unknown"} for item in values
    ):
        return None
    confirmed = {
        item.precision for item in values if item.status == "confirmed" and item.raw == release_date
    }
    return next(iter(confirmed)) if len(confirmed) == 1 else None


def sync_project_release_precisions(conn, spotify_album_ids):
    """Bounded maintenance of date evidence only; manual dates/memberships stay intact."""
    ids = tuple(sorted(set(spotify_album_ids)))
    if not ids:
        return 0
    placeholders = ",".join("?" for _ in ids)
    projects = conn.execute(
        f"""SELECT DISTINCT ap.project_id,ap.primary_album_id,ap.release_date
        FROM album_projects ap JOIN album_spotify_links asl ON asl.album_id=ap.primary_album_id
        WHERE ap.is_manual=0 AND asl.spotify_album_id IN ({placeholders})""",
        ids,
    ).fetchall()
    changed = 0
    for project in projects:
        precision = project_date_precision(conn, project[1], project[2])
        changed += conn.execute(
            """UPDATE album_projects SET release_date_precision=?
            WHERE project_id=? AND release_date_precision IS NOT ?""",
            (precision, project[0], precision),
        ).rowcount
    return changed
