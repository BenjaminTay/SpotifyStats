"""Shared filter context and stable cache fingerprint for Yearly Review V2."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from backend.domains.metadata.artist_identity import get_identity_revision
from backend.domains.metadata.genre_display_taxonomy import GENRE_DISPLAY_TAXONOMY_VERSION
from backend.domains.metadata.track_credits import get_track_credit_revision
from backend.domains.metadata.track_identity import (
    TRACK_IDENTITY_POLICY_VERSION,
    get_track_identity_revision,
)
from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
from backend.models.yearly_review import YearlyReviewFilterContext
from backend.services.wrapped_service import _artist_metadata_revision

FILTER_FINGERPRINT_VERSION = "yearly_review_filter_v4_l1"

FILTER_FIELDS = (
    "min_ms",
    "music_only",
    "merge_enabled",
    "dynamic_threshold",
    "max_merge_gap_minutes",
    "merge_level",
    "include_compilations",
    "bb_top_n",
    "bb_album_top_n",
    "bb_artist_top_n",
    "bb_week_start_dow",
    "bb_week_start_hour",
)

REVISION_FIELDS = (
    "display_taxonomy_version",
    "artist_metadata_revision",
    "artist_identity_revision",
    "track_credit_revision",
    "track_identity_revision",
    "track_identity_policy",
    "track_group_revision",
    "album_project_revision",
)

_TRACK_GROUP_TABLES = ("track_groups", "track_group_l1_members")


def _album_project_semantic_revision(conn: sqlite3.Connection) -> str:
    """Hash project meaning without unstable surrogate project ids."""
    if not _table_exists(conn, "album_projects"):
        return "unavailable"
    digest = hashlib.sha256()
    queries = (
        """SELECT canonical_name, artist_id, primary_album_id, release_date,
                  scope, project_type, include_in_charts, is_manual
           FROM album_projects
           ORDER BY canonical_name, artist_id, scope, primary_album_id""",
        """SELECT ap.canonical_name, ap.artist_id, ap.scope,
                  apa.album_id, apa.role, apa.source_bucket, apa.inferred
           FROM album_project_albums apa
           JOIN album_projects ap ON ap.project_id=apa.project_id
           ORDER BY ap.canonical_name, ap.artist_id, ap.scope, apa.album_id""",
        """SELECT ap.canonical_name, ap.artist_id, ap.scope,
                  apt.track_id, apt.membership_role, apt.min_merge_level,
                  apt.source_album_id, apt.is_exclusive, apt.inferred
           FROM album_project_tracks apt
           JOIN album_projects ap ON ap.project_id=apt.project_id
           ORDER BY ap.canonical_name, ap.artist_id, ap.scope,
                    apt.track_id, apt.min_merge_level""",
    )
    for query in queries:
        try:
            rows = conn.execute(query)
        except sqlite3.OperationalError:
            digest.update(b"missing\n")
            continue
        for row in rows:
            digest.update(
                json.dumps(
                    list(row), ensure_ascii=True, separators=(",", ":"), default=str
                ).encode()
            )
            digest.update(b"\n")
    return digest.hexdigest()[:20]


def _value(source: Mapping[str, Any] | object, key: str) -> Any:
    if isinstance(source, Mapping):
        return source[key]
    return getattr(source, key)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _table_set_revision(conn: sqlite3.Connection, tables: tuple[str, ...]) -> str:
    """Hash exact ordered table contents without relying on mutable timestamps."""
    digest = hashlib.sha256()
    found = False
    for table in tables:
        digest.update(f"table:{table}\n".encode())
        if not _table_exists(conn, table):
            digest.update(b"missing\n")
            continue
        found = True
        columns = [str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()]
        if not columns:
            digest.update(b"no-columns\n")
            continue
        quoted = ", ".join(f'"{column}"' for column in columns)
        cursor = conn.execute(f'SELECT {quoted} FROM "{table}" ORDER BY {quoted}')
        for row in cursor:
            encoded = json.dumps(
                list(row),
                ensure_ascii=True,
                separators=(",", ":"),
                default=str,
            )
            digest.update(encoded.encode())
            digest.update(b"\n")
    return digest.hexdigest()[:20] if found else "unavailable"


def collect_yearly_review_revisions(conn: sqlite3.Connection) -> dict[str, str | int]:
    """Collect every data-generation revision that can alter report semantics."""
    try:
        artist_revision = _artist_metadata_revision(conn)
    except Exception:
        artist_revision = "unavailable"
    try:
        identity_revision = get_identity_revision(conn)
    except Exception:
        identity_revision = 0
    try:
        credit_revision = get_track_credit_revision(conn)
    except Exception:
        credit_revision = 0
    return {
        "display_taxonomy_version": GENRE_DISPLAY_TAXONOMY_VERSION,
        "artist_metadata_revision": artist_revision,
        "artist_identity_revision": identity_revision,
        "track_credit_revision": credit_revision,
        "track_identity_revision": get_track_identity_revision(conn),
        "track_identity_policy": TRACK_IDENTITY_POLICY_VERSION,
        "track_group_revision": _table_set_revision(conn, _TRACK_GROUP_TABLES),
        "album_project_revision": _album_project_semantic_revision(conn),
    }


def fingerprint_filter_values(values: Mapping[str, Any]) -> str:
    """Return an order-independent fingerprint for user-selected filters."""
    payload = {
        "fingerprint_version": FILTER_FINGERPRINT_VERSION,
        **{key: values[key] for key in FILTER_FIELDS},
    }
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def fingerprint_filter_context(context: YearlyReviewFilterContext | Mapping[str, Any]) -> str:
    if isinstance(context, YearlyReviewFilterContext):
        values = context.model_dump(exclude={"filter_fingerprint"})
    else:
        values = {key: value for key, value in context.items() if key != "filter_fingerprint"}
    return fingerprint_filter_values(values)


def build_yearly_review_context(
    conn: sqlite3.Connection,
    filters: Mapping[str, Any] | object,
    *,
    revision_overrides: Mapping[str, str | int] | None = None,
) -> YearlyReviewFilterContext:
    """Resolve one immutable context for every builder in a report request."""
    revisions = (
        dict(revision_overrides)
        if revision_overrides is not None
        else collect_yearly_review_revisions(conn)
    )
    missing_revisions = set(REVISION_FIELDS) - set(revisions)
    if missing_revisions:
        raise ValueError(f"missing yearly-review revisions: {sorted(missing_revisions)}")

    values = {key: _value(filters, key) for key in FILTER_FIELDS}
    if values["max_merge_gap_minutes"] is None:
        settings = SettingsRepository(conn).load_all()
        values["max_merge_gap_minutes"] = int(
            settings.get(
                "max_merge_gap_minutes",
                SETTINGS_DEFAULTS["max_merge_gap_minutes"],
            )
        )
    values.update({key: revisions[key] for key in REVISION_FIELDS})
    fingerprint = fingerprint_filter_values(values)
    return YearlyReviewFilterContext(**values, filter_fingerprint=fingerprint)
