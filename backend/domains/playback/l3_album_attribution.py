"""Deterministic L3 song-work to native album-work attribution.

Track composition answers which recordings represent one song work.  Album
composition answers whether complete release projects are editions of one
album work (currently rerecord lineages).  This module connects the two: each
L3 song key receives at most one album owner, while the actual source album is
left untouched for explanation.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from backend.domains.metadata.artist_identity import get_artist_identity_map
from backend.domains.metadata.track_composition_identity import (
    normalize_composition_track_title,
)
from backend.domains.playback.album_composition_auto_merge import (
    normalize_album_composition_title,
)

L3_ALBUM_ATTRIBUTION_POLICY_VERSION = "l3_native_album_attribution_v2"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS l3_song_album_attributions (
    canonical_song_key        TEXT PRIMARY KEY,
    representative_track_id   INTEGER NOT NULL REFERENCES tracks(track_id),
    canonical_artist_key      TEXT NOT NULL,
    target_project_id         INTEGER NOT NULL
                                  REFERENCES album_projects(project_id) ON DELETE CASCADE,
    origin_release_project_id INTEGER NOT NULL
                                  REFERENCES album_projects(project_id) ON DELETE CASCADE,
    attribution_kind          TEXT NOT NULL,
    decision_source           TEXT NOT NULL CHECK(decision_source IN ('automatic', 'manual')),
    confidence                REAL NOT NULL DEFAULT 1.0
                                   CHECK(confidence >= 0 AND confidence <= 1),
    evidence_json             TEXT NOT NULL DEFAULT '{}',
    policy_version            TEXT NOT NULL,
    track_identity_revision   INTEGER NOT NULL,
    album_project_revision    INTEGER NOT NULL,
    created_at                TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_l3_song_album_target
    ON l3_song_album_attributions(target_project_id);
CREATE INDEX IF NOT EXISTS idx_l3_song_album_origin
    ON l3_song_album_attributions(origin_release_project_id);

CREATE TABLE IF NOT EXISTS l3_song_album_attribution_overrides (
    override_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    anchor_track_id   INTEGER NOT NULL REFERENCES tracks(track_id),
    target_project_id INTEGER REFERENCES album_projects(project_id) ON DELETE SET NULL,
    action            TEXT NOT NULL CHECK(action IN ('force_target', 'force_keep_source')),
    reason            TEXT NOT NULL,
    active            INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0, 1)),
    created_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_l3_song_album_override_active_anchor
    ON l3_song_album_attribution_overrides(anchor_track_id)
    WHERE active=1;

CREATE TABLE IF NOT EXISTS l3_song_album_attribution_issues (
    canonical_song_key       TEXT NOT NULL,
    issue_kind               TEXT NOT NULL
                                 CHECK(issue_kind IN ('conflict', 'uncovered', 'invalid_override')),
    representative_track_id  INTEGER REFERENCES tracks(track_id),
    canonical_artist_key     TEXT,
    evidence_json            TEXT NOT NULL DEFAULT '{}',
    policy_version           TEXT NOT NULL,
    track_identity_revision  INTEGER NOT NULL,
    album_project_revision   INTEGER NOT NULL,
    created_at               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(canonical_song_key, issue_kind)
);

CREATE TABLE IF NOT EXISTS l3_song_album_attribution_exclusions (
    canonical_song_key       TEXT PRIMARY KEY,
    representative_track_id  INTEGER REFERENCES tracks(track_id),
    canonical_artist_key     TEXT,
    reason_code              TEXT NOT NULL,
    evidence_json            TEXT NOT NULL DEFAULT '{}',
    policy_version           TEXT NOT NULL,
    track_identity_revision  INTEGER NOT NULL,
    album_project_revision   INTEGER NOT NULL,
    created_at               TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS l3_album_attribution_revision_state (
    state_id         INTEGER PRIMARY KEY CHECK(state_id = 1),
    current_revision INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'empty'
                          CHECK(status IN ('empty', 'building', 'ready', 'failed')),
    policy_version   TEXT NOT NULL DEFAULT 'l3_native_album_attribution_v2',
    track_identity_revision INTEGER NOT NULL DEFAULT 0,
    album_project_revision  INTEGER NOT NULL DEFAULT 0,
    mapping_digest    TEXT NOT NULL DEFAULT '',
    attributed_count  INTEGER NOT NULL DEFAULT 0,
    conflict_count    INTEGER NOT NULL DEFAULT 0,
    uncovered_count   INTEGER NOT NULL DEFAULT 0,
    scanned_count     INTEGER NOT NULL DEFAULT 0,
    excluded_count    INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO l3_album_attribution_revision_state(
    state_id, current_revision, policy_version
) VALUES (1, 0, 'l3_native_album_attribution_v2');
"""


@dataclass(frozen=True)
class L3AlbumAttributionDecision:
    canonical_song_key: str
    representative_track_id: int
    canonical_song_name: str
    canonical_artist_key: str
    target_project_id: int
    target_project_name: str
    origin_release_project_id: int
    origin_project_name: str
    attribution_kind: str
    decision_source: str
    confidence: float
    source_project_ids: tuple[int, ...]
    candidate_project_ids: tuple[int, ...]
    evidence_codes: tuple[str, ...]
    evidence: tuple[tuple[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class L3AlbumAttributionIssue:
    canonical_song_key: str
    issue_kind: str
    representative_track_id: int
    canonical_song_name: str
    canonical_artist_key: str
    candidate_project_ids: tuple[int, ...]
    candidate_project_names: tuple[str, ...]
    evidence_codes: tuple[str, ...]
    evidence: tuple[tuple[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class L3AlbumAttributionExclusion:
    canonical_song_key: str
    representative_track_id: int
    canonical_song_name: str
    canonical_artist_key: str
    reason_code: str
    evidence_codes: tuple[str, ...]
    evidence: tuple[tuple[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class L3AlbumAttributionPlan:
    policy_version: str
    track_identity_revision: int
    album_project_revision: int
    input_digest: str
    decisions: tuple[L3AlbumAttributionDecision, ...]
    issues: tuple[L3AlbumAttributionIssue, ...]
    exclusions: tuple[L3AlbumAttributionExclusion, ...]
    uncovered_song_keys: tuple[str, ...]
    conflict_song_keys: tuple[str, ...]
    excluded_song_keys: tuple[str, ...]
    scanned_song_count: int
    changed: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class L3AlbumAttributionApplyReport:
    decision_count: int
    automatic_count: int
    manual_count: int
    uncovered_count: int
    conflict_count: int
    excluded_count: int
    scanned_count: int
    rows_inserted: int
    attribution_revision: int
    changed: bool
    requires_downstream_refresh: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _ProjectCandidate:
    project_id: int
    canonical_name: str
    canonical_artist_id: int
    release_date: str
    project_type: str
    is_manual: bool
    relation_tag: str | None
    source_buckets: tuple[str, ...]
    membership_roles: tuple[str, ...]
    track_relation_tags: tuple[str, ...]
    has_original_recording: bool
    target_project_id: int
    target_project_name: str


def _controlled_project_role(name: str) -> str | None:
    parsed = normalize_album_composition_title(name)
    if parsed.relation_tag:
        return parsed.relation_tag
    text = " ".join(name.casefold().replace("’", "'").split())
    if re.search(r"\b(?:remix(?:es)?|mixes)\b", text):
        return "remix"
    if re.search(r"\b(?:acoustic|unplugged|stripped)\b", text):
        return "acoustic"
    live_shape = re.search(
        r"(?:^live\b|[:\[(\-–—]\s*live\b|\blive\s+(?:from|at|in|on|album|version|sessions?)\b|\blive$|\btour\s+live\b|\blive\s+on\s+tour\b)",
        text,
    )
    if live_shape and not re.search(r"\bto\s+live$", text):
        return "live"
    if re.search(r"(?:演唱[会會]|現場|现场|巡[回迴])", text):
        return "live"
    if re.search(
        r"\b(?:demo|demos|session recordings?|rehearsal|karaoke|instrumental)\b",
        text,
    ) or re.search(r"(?:演奏版|伴奏版)", text):
        return "alternate"
    if re.search(
        r"\b(?:greatest hits|best of|anthology|essentials|collection)\b", text
    ) or re.search(r"(?:精[選选]|金曲|黃金十年|黄金十年)", text):
        return "compilation"
    return None


def ensure_l3_album_attribution_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    columns = {
        str(row[1])
        for row in conn.execute("PRAGMA table_info(l3_album_attribution_revision_state)").fetchall()
    }
    if "scanned_count" not in columns:
        conn.execute(
            """ALTER TABLE l3_album_attribution_revision_state
               ADD COLUMN scanned_count INTEGER NOT NULL DEFAULT 0"""
        )
    if "excluded_count" not in columns:
        conn.execute(
            """ALTER TABLE l3_album_attribution_revision_state
               ADD COLUMN excluded_count INTEGER NOT NULL DEFAULT 0"""
        )


def get_l3_album_attribution_revision(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            """SELECT current_revision
                 FROM l3_album_attribution_revision_state WHERE state_id=1"""
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0] or 0) if row is not None else 0


def get_l3_album_attribution_state(conn: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(conn, "l3_album_attribution_revision_state"):
        return {
            "current_revision": 0,
            "status": "empty",
            "policy_version": L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            "track_identity_revision": 0,
            "album_project_revision": 0,
            "mapping_digest": "",
            "attributed_count": 0,
            "conflict_count": 0,
            "uncovered_count": 0,
            "scanned_count": 0,
            "excluded_count": 0,
            "updated_at": None,
        }
    row = conn.execute(
        """SELECT current_revision, status, policy_version,
                  track_identity_revision, album_project_revision,
                  mapping_digest, attributed_count, conflict_count,
                  uncovered_count, scanned_count, excluded_count, updated_at
             FROM l3_album_attribution_revision_state WHERE state_id=1"""
    ).fetchone()
    if row is None:
        return {
            "current_revision": 0,
            "status": "empty",
            "policy_version": L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            "track_identity_revision": 0,
            "album_project_revision": 0,
            "mapping_digest": "",
            "attributed_count": 0,
            "conflict_count": 0,
            "uncovered_count": 0,
            "scanned_count": 0,
            "excluded_count": 0,
            "updated_at": None,
        }
    return dict(row)


def _track_identity_revision(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0] or 0) if row is not None else 0


def _album_project_revision(conn: sqlite3.Connection) -> int:
    try:
        row = conn.execute(
            "SELECT current_revision FROM album_project_revision_state WHERE state_id=1"
        ).fetchone()
    except sqlite3.OperationalError:
        return 0
    return int(row[0] or 0) if row is not None else 0


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def _load_release_memberships(conn: sqlite3.Connection) -> pd.DataFrame:
    from backend.domains.playback.album_projects import apply_canonical_song_keys

    required_tables = {
        "album_projects",
        "album_project_tracks",
        "album_project_albums",
        "tracks",
    }
    if not all(_table_exists(conn, table) for table in required_tables):
        return pd.DataFrame()

    raw = pd.read_sql_query(
        """SELECT ap.project_id,
                  ap.canonical_name AS project_name,
                  ap.artist_id,
                  ap.release_date,
                  ap.project_type,
                  ap.is_manual,
                  apt.track_id,
                  t.track_name,
                  apt.membership_role,
                  apt.source_album_id,
                  COALESCE(apa.source_bucket, 'other') AS source_bucket
             FROM album_projects ap
             JOIN album_project_tracks apt ON apt.project_id=ap.project_id
             JOIN tracks t ON t.track_id=apt.track_id
             LEFT JOIN album_project_albums apa
               ON apa.project_id=apt.project_id
              AND apa.album_id=COALESCE(apt.source_album_id, ap.primary_album_id)
            WHERE ap.scope='release'
            ORDER BY ap.project_id, apt.track_id""",
        conn,
    )
    if raw.empty:
        return raw
    return apply_canonical_song_keys(raw, conn, merge_level=3)


def _load_work_universe(
    conn: sqlite3.Connection, *, include_unplayed: bool = True
) -> tuple[pd.DataFrame, dict[int, str]]:
    """Return every active L3 work before Album Project membership is joined.

    The previous attribution planner started from ``album_project_tracks`` and
    therefore could not report works whose catalog membership was completely
    missing.  This universe starts from active L1 identities and the shared L3
    work-key resolver, then attaches raw-play evidence only for diagnostics.
    """

    from backend.domains.playback.song_work_keys import load_l3_song_work_keys

    keys = load_l3_song_work_keys(conn)
    if keys.empty:
        return pd.DataFrame(), {}
    required = {
        "l1_id",
        "canonical_song_key",
        "canonical_song_name",
        "representative_track_id",
    }
    if not required.issubset(keys.columns):
        missing = sorted(required - set(keys.columns))
        raise RuntimeError(f"L3 work-key resolver missing columns: {missing}")

    track_to_key: dict[int, str] = {}
    key_by_l1: dict[int, str] = {}
    for row in keys.itertuples(index=False):
        l1_id = int(row.l1_id)
        key = str(row.canonical_song_key)
        key_by_l1[l1_id] = key
        track_to_key[l1_id] = key
        track_to_key[int(row.representative_track_id)] = key
    if _table_exists(conn, "track_l1_source_links"):
        for row in conn.execute(
            "SELECT l1_id, track_id FROM track_l1_source_links ORDER BY l1_id, track_id"
        ).fetchall():
            key = key_by_l1.get(int(row[0]))
            if key is not None:
                track_to_key[int(row[1])] = key

    play_stats: dict[int, tuple[int, int, tuple[int, ...]]] = {}
    if _table_exists(conn, "plays"):
        play_columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(plays)").fetchall()}
        source_album_expression = (
            "plays.source_album_id" if "source_album_id" in play_columns else "NULL"
        )
        if _table_exists(conn, "track_l1_source_links"):
            rows = conn.execute(
                f"""SELECT links.l1_id, COUNT(plays.play_id),
                          COALESCE(SUM(plays.ms_played), 0),
                          GROUP_CONCAT(DISTINCT {source_album_expression})
                     FROM (
                         SELECT DISTINCT l1_id, track_id
                           FROM track_l1_source_links
                     ) links
                     LEFT JOIN plays ON plays.track_id=links.track_id
                    GROUP BY links.l1_id"""
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT tracks.track_id, COUNT(plays.play_id),
                          COALESCE(SUM(plays.ms_played), 0),
                          GROUP_CONCAT(DISTINCT {source_album_expression})
                     FROM tracks
                     LEFT JOIN plays ON plays.track_id=tracks.track_id
                    GROUP BY tracks.track_id"""
            ).fetchall()
        for row in rows:
            source_ids = tuple(
                sorted({int(value) for value in str(row[3] or "").split(",") if value.strip()})
            )
            play_stats[int(row[0])] = (int(row[1] or 0), int(row[2] or 0), source_ids)

    records: list[dict[str, Any]] = []
    for key, frame in keys.groupby("canonical_song_key", sort=True):
        representative = int(frame.iloc[0]["representative_track_id"])
        l1_ids = tuple(sorted({int(value) for value in frame["l1_id"].tolist()}))
        raw_play_count = sum(play_stats.get(l1_id, (0, 0, ()))[0] for l1_id in l1_ids)
        raw_ms = sum(play_stats.get(l1_id, (0, 0, ()))[1] for l1_id in l1_ids)
        source_album_ids = tuple(
            sorted(
                {album_id for l1_id in l1_ids for album_id in play_stats.get(l1_id, (0, 0, ()))[2]}
            )
        )
        records.append(
            {
                "canonical_song_key": str(key),
                "canonical_song_name": str(frame.iloc[0]["canonical_song_name"]),
                "representative_track_id": representative,
                "l1_ids": l1_ids,
                "raw_play_count": raw_play_count,
                "raw_ms": raw_ms,
                "source_album_ids": source_album_ids,
            }
        )
    work_universe = pd.DataFrame.from_records(records)
    if not include_unplayed and not work_universe.empty:
        work_universe = work_universe.loc[work_universe["raw_play_count"] > 0].reset_index(
            drop=True
        )
        included_keys = set(work_universe["canonical_song_key"].astype(str))
        track_to_key = {
            track_id: key for track_id, key in track_to_key.items() if key in included_keys
        }
    return work_universe, track_to_key


def _canonical_artist_ids(conn: sqlite3.Connection) -> dict[int, int]:
    if not _table_exists(conn, "artists"):
        return {}
    identity = get_artist_identity_map(conn)
    result: dict[int, int] = {}
    for row in conn.execute("SELECT artist_id FROM artists ORDER BY artist_id").fetchall():
        artist_id = int(row[0])
        resolution = identity.get(artist_id)
        result[artist_id] = (
            int(resolution.canonical_artist_id) if resolution is not None else artist_id
        )
    return result


def _project_album_sets(conn: sqlite3.Connection) -> dict[int, frozenset[int]]:
    grouped: dict[int, set[int]] = defaultdict(set)
    for row in conn.execute(
        "SELECT project_id, album_id FROM album_project_albums ORDER BY project_id, album_id"
    ).fetchall():
        grouped[int(row[0])].add(int(row[1]))
    return {project_id: frozenset(album_ids) for project_id, album_ids in grouped.items()}


def _composition_parent_map(
    conn: sqlite3.Connection,
    canonical_artists: dict[int, int],
) -> dict[int, tuple[int, str]]:
    project_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(album_projects)").fetchall()
    }
    # Compact contract fixtures and pre-composition databases model release
    # projects without an artist/scope hierarchy.  In that shape there is no
    # composition parent to resolve, so keep every release project as its own
    # target instead of assuming columns that do not exist.
    if not {"artist_id", "scope"}.issubset(project_columns):
        return {}
    rows = conn.execute(
        """SELECT project_id, canonical_name, artist_id, scope
             FROM album_projects WHERE scope IN ('release', 'composition')
             ORDER BY scope, project_id"""
    ).fetchall()
    album_sets = _project_album_sets(conn)
    composition = [row for row in rows if str(row["scope"]) == "composition"]
    result: dict[int, tuple[int, str]] = {}
    for release in (row for row in rows if str(row["scope"]) == "release"):
        release_id = int(release["project_id"])
        release_albums = album_sets.get(release_id, frozenset())
        if not release_albums:
            continue
        release_artist = canonical_artists.get(int(release["artist_id"]), int(release["artist_id"]))
        matches: list[sqlite3.Row] = []
        for parent in composition:
            parent_artist = canonical_artists.get(
                int(parent["artist_id"]), int(parent["artist_id"])
            )
            if parent_artist != release_artist:
                continue
            if release_albums.issubset(album_sets.get(int(parent["project_id"]), frozenset())):
                matches.append(parent)
        if not matches:
            continue
        matches.sort(
            key=lambda row: (
                len(album_sets.get(int(row["project_id"]), frozenset())),
                int(row["project_id"]),
            )
        )
        winner = matches[0]
        result[release_id] = (int(winner["project_id"]), str(winner["canonical_name"]))
    return result


def _candidate_rank(candidate: _ProjectCandidate) -> tuple[Any, ...]:
    buckets = set(candidate.source_buckets)
    roles = set(candidate.membership_roles)
    relation = candidate.relation_tag
    is_compilation = candidate.project_type.startswith("compilation")

    if relation in {"live", "acoustic", "remix", "alternate"}:
        tier = 70
    elif relation == "compilation":
        # A compilation can still be the earliest known original source when
        # no studio album/single is represented.  It must beat derivative
        # live/acoustic/remix projects but lose to a native album or single.
        tier = 60
    elif relation == "rerecord" or "rerecord" in buckets or "rerecord" in roles:
        tier = 50
    elif candidate.is_manual and candidate.has_original_recording and not is_compilation:
        tier = 0
    elif candidate.has_original_recording and candidate.project_type == "soundtrack":
        tier = 15
    elif candidate.has_original_recording and "original_album" in buckets and not relation:
        tier = 10
    elif candidate.has_original_recording and "deluxe" in buckets and not relation:
        tier = 20
    elif candidate.has_original_recording and "single" in buckets and not relation:
        tier = 30
    elif candidate.has_original_recording and not relation and not is_compilation:
        tier = 40
    elif "live_acoustic_remix" in buckets:
        tier = 70
    elif is_compilation:
        tier = 90
    else:
        tier = 60

    # Earlier release is the default native home when two otherwise equivalent
    # studio memberships remain. Stable ids only settle exact business ties.
    return (
        tier,
        candidate.release_date or "9999-12-31",
        candidate.project_id,
    )


def _attribution_kind(candidate: _ProjectCandidate) -> str:
    buckets = set(candidate.source_buckets)
    roles = set(candidate.membership_roles)
    if candidate.project_type == "soundtrack":
        return "soundtrack"
    if candidate.has_original_recording and candidate.relation_tag is None:
        if "single" in buckets:
            return "album_single"
        if "deluxe" in buckets and "original_album" not in buckets:
            return "deluxe_exclusive"
        return "studio_album"
    if candidate.target_project_id != candidate.project_id and (
        candidate.relation_tag == "rerecord" or "rerecord" in buckets or "rerecord" in roles
    ):
        return "rerecord_union"
    if candidate.relation_tag == "live" or "live" in candidate.track_relation_tags:
        return "live_residual"
    if candidate.relation_tag == "acoustic" or "acoustic" in candidate.track_relation_tags:
        return "acoustic_residual"
    if candidate.relation_tag == "remix" or "remix" in candidate.track_relation_tags:
        return "remix_residual"
    if candidate.relation_tag == "alternate":
        return "alternate_residual"
    if candidate.relation_tag == "compilation":
        return "compilation_residual"
    if candidate.project_type.startswith("compilation"):
        return "compilation_exclusive"
    return "studio_album"


def _representative_track_id(conn: sqlite3.Connection, key: str, frame: pd.DataFrame) -> int:
    if key.startswith(("composition:", "recording:")):
        group_id = int(key.split(":", 1)[1])
        row = conn.execute(
            "SELECT primary_track_id FROM track_groups WHERE group_id=?",
            (group_id,),
        ).fetchone()
        if row is not None and row[0] is not None:
            return int(row[0])
    if key.startswith("l1:"):
        l1_id = int(key.split(":", 1)[1])
        if _table_exists(conn, "track_l1_identities"):
            row = conn.execute(
                """SELECT representative_track_id FROM track_l1_identities
                    WHERE l1_id=?""",
                (l1_id,),
            ).fetchone()
            if row is not None and row[0] is not None:
                return int(row[0])
        elif conn.execute(
            "SELECT 1 FROM tracks WHERE track_id=?",
            (l1_id,),
        ).fetchone():
            # Compact legacy/contract databases predate the L1 identity tables;
            # their l1 key is deliberately the stable track owner itself.
            return l1_id
    return int(frame["track_id"].min())


def _active_overrides(
    conn: sqlite3.Connection,
    track_to_song_key: dict[int, str],
) -> tuple[dict[str, sqlite3.Row], set[str], dict[str, sqlite3.Row]]:
    if not _table_exists(conn, "l3_song_album_attribution_overrides"):
        return {}, set(), {}
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in conn.execute(
        """SELECT override_id, anchor_track_id, target_project_id, action, reason
             FROM l3_song_album_attribution_overrides
            WHERE active=1 ORDER BY override_id"""
    ).fetchall():
        key = track_to_song_key.get(int(row["anchor_track_id"]))
        if key:
            grouped[key].append(row)
    resolved: dict[str, sqlite3.Row] = {}
    conflicts: set[str] = set()
    invalid: dict[str, sqlite3.Row] = {}
    for key, rows in grouped.items():
        if any(row["target_project_id"] is None for row in rows):
            invalid[key] = rows[-1]
            continue
        targets = {int(row["target_project_id"]) for row in rows}
        if len(targets) != 1:
            conflicts.add(key)
            continue
        resolved[key] = rows[-1]
    return resolved, conflicts, invalid


def _stable_evidence(**values: Any) -> tuple[tuple[str, Any], ...]:
    return tuple(sorted(values.items(), key=lambda item: item[0]))


def _current_projection_digest(conn: sqlite3.Connection) -> str:
    if not _table_exists(conn, "l3_song_album_attributions"):
        return ""
    rows = conn.execute(
        """SELECT canonical_song_key, representative_track_id, canonical_artist_key,
                  target_project_id, origin_release_project_id, attribution_kind,
                  decision_source, confidence, evidence_json, policy_version,
                  track_identity_revision, album_project_revision
             FROM l3_song_album_attributions ORDER BY canonical_song_key"""
    ).fetchall()
    payload = [tuple(row) for row in rows]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _issue_json(item: L3AlbumAttributionIssue) -> str:
    return json.dumps(
        {
            "canonical_song_name": item.canonical_song_name,
            "candidate_project_ids": item.candidate_project_ids,
            "candidate_project_names": item.candidate_project_names,
            "evidence_codes": item.evidence_codes,
            "evidence": dict(item.evidence),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _exclusion_json(item: L3AlbumAttributionExclusion) -> str:
    return json.dumps(
        {
            "canonical_song_name": item.canonical_song_name,
            "evidence_codes": item.evidence_codes,
            "evidence": dict(item.evidence),
        },
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _current_issue_rows(conn: sqlite3.Connection) -> tuple[tuple[Any, ...], ...]:
    if not _table_exists(conn, "l3_song_album_attribution_issues"):
        return ()
    return tuple(
        tuple(row)
        for row in conn.execute(
            """SELECT canonical_song_key, issue_kind, representative_track_id,
                      canonical_artist_key, evidence_json, policy_version,
                      track_identity_revision, album_project_revision
                 FROM l3_song_album_attribution_issues
                ORDER BY canonical_song_key, issue_kind"""
        ).fetchall()
    )


def _current_exclusion_rows(conn: sqlite3.Connection) -> tuple[tuple[Any, ...], ...]:
    if not _table_exists(conn, "l3_song_album_attribution_exclusions"):
        return ()
    return tuple(
        tuple(row)
        for row in conn.execute(
            """SELECT canonical_song_key, representative_track_id,
                      canonical_artist_key, reason_code, evidence_json,
                      policy_version, track_identity_revision,
                      album_project_revision
                 FROM l3_song_album_attribution_exclusions
                ORDER BY canonical_song_key"""
        ).fetchall()
    )


def _desired_projection_digest(plan_rows: list[tuple[Any, ...]]) -> str:
    return hashlib.sha256(
        json.dumps(plan_rows, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def plan_l3_album_attributions(
    conn: sqlite3.Connection, *, include_unplayed: bool = True
) -> L3AlbumAttributionPlan:
    """Build the complete desired one-owner L3 album projection without writes."""

    track_revision = _track_identity_revision(conn)
    album_revision = _album_project_revision(conn)
    work_universe, track_to_song_key = _load_work_universe(conn, include_unplayed=include_unplayed)
    memberships = _load_release_memberships(conn)
    if work_universe.empty:
        empty_digest = hashlib.sha256(b"[]").hexdigest()
        state = get_l3_album_attribution_state(conn)
        state_ready = (
            state["status"] == "ready"
            and state["policy_version"] == L3_ALBUM_ATTRIBUTION_POLICY_VERSION
            and int(state["track_identity_revision"]) == track_revision
            and int(state["album_project_revision"]) == album_revision
            and state["mapping_digest"] == empty_digest
            and int(state["attributed_count"]) == 0
            and int(state["conflict_count"]) == 0
            and int(state["uncovered_count"]) == 0
            and int(state["scanned_count"]) == 0
            and int(state["excluded_count"]) == 0
        )
        return L3AlbumAttributionPlan(
            policy_version=L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            track_identity_revision=track_revision,
            album_project_revision=album_revision,
            input_digest=empty_digest,
            decisions=(),
            issues=(),
            exclusions=(),
            uncovered_song_keys=(),
            conflict_song_keys=(),
            excluded_song_keys=(),
            scanned_song_count=0,
            changed=(
                _current_projection_digest(conn) != empty_digest
                or bool(_current_issue_rows(conn))
                or bool(_current_exclusion_rows(conn))
                or not state_ready
            ),
        )

    canonical_artists = _canonical_artist_ids(conn)
    parent_map = _composition_parent_map(conn, canonical_artists)
    project_columns = {
        str(row[1]) for row in conn.execute("PRAGMA table_info(album_projects)").fetchall()
    }
    legacy_project_schema = not {"artist_id", "scope"}.issubset(project_columns)
    overrides, override_conflicts, invalid_overrides = _active_overrides(conn, track_to_song_key)

    decisions: list[L3AlbumAttributionDecision] = []
    issues: list[L3AlbumAttributionIssue] = []
    exclusions: list[L3AlbumAttributionExclusion] = []
    uncovered: list[str] = []
    conflicts = set(override_conflicts)

    for work in work_universe.sort_values("canonical_song_key").itertuples(index=False):
        key = str(work.canonical_song_key)
        song_frame = (
            memberships[memberships["canonical_song_key"].astype(str) == key]
            if not memberships.empty
            else pd.DataFrame()
        )
        candidates: list[_ProjectCandidate] = []
        grouped_projects = (
            song_frame.groupby("project_id", sort=True) if not song_frame.empty else ()
        )
        for project_id, project_frame in grouped_projects:
            project_id_int = int(project_id)
            first = project_frame.iloc[0]
            track_relations: set[str] = set()
            has_original = False
            for title in project_frame["track_name"].astype(str):
                identity = normalize_composition_track_title(title)
                track_relations.update(identity.relation_tags)
                if not identity.relation_tags and not identity.blocker_tags:
                    has_original = True
            project_role = _controlled_project_role(str(first["project_name"]))
            source_artist_id = int(first["artist_id"])
            canonical_artist_id = canonical_artists.get(source_artist_id, source_artist_id)
            parent = parent_map.get(project_id_int)
            target_project_id = parent[0] if parent else project_id_int
            target_project_name = parent[1] if parent else str(first["project_name"])
            candidates.append(
                _ProjectCandidate(
                    project_id=project_id_int,
                    canonical_name=str(first["project_name"]),
                    canonical_artist_id=canonical_artist_id,
                    release_date=str(first["release_date"] or ""),
                    project_type=str(first["project_type"]),
                    is_manual=bool(first["is_manual"]),
                    relation_tag=project_role,
                    source_buckets=tuple(sorted(set(project_frame["source_bucket"].astype(str)))),
                    membership_roles=tuple(
                        sorted(set(project_frame["membership_role"].astype(str)))
                    ),
                    track_relation_tags=tuple(sorted(track_relations)),
                    has_original_recording=has_original,
                    target_project_id=target_project_id,
                    target_project_name=target_project_name,
                )
            )

        if not candidates:
            representative = int(work.representative_track_id)
            track_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(tracks)").fetchall()
            }
            if "artist_id" in track_columns:
                artist_row = conn.execute(
                    "SELECT artist_id FROM tracks WHERE track_id=?", (representative,)
                ).fetchone()
            elif _table_exists(conn, "track_artists"):
                track_artist_columns = {
                    str(row[1])
                    for row in conn.execute("PRAGMA table_info(track_artists)").fetchall()
                }
                ordering = (
                    "is_primary DESC, artist_id"
                    if "is_primary" in track_artist_columns
                    else "artist_id"
                )
                artist_row = conn.execute(
                    f"""SELECT artist_id FROM track_artists
                        WHERE track_id=? ORDER BY {ordering} LIMIT 1""",
                    (representative,),
                ).fetchone()
            else:
                artist_row = None
            artist_id = int(artist_row[0]) if artist_row is not None else 0
            canonical_artist_id = canonical_artists.get(artist_id, artist_id)
            if legacy_project_schema:
                exclusions.append(
                    L3AlbumAttributionExclusion(
                        canonical_song_key=key,
                        representative_track_id=representative,
                        canonical_song_name=str(work.canonical_song_name),
                        canonical_artist_key=str(canonical_artist_id or ""),
                        reason_code="legacy_album_project_schema",
                        evidence_codes=("album_project_ownership_unavailable",),
                        evidence=_stable_evidence(
                            raw_play_count=int(work.raw_play_count),
                            raw_ms=int(work.raw_ms),
                            source_album_ids=tuple(work.source_album_ids),
                        ),
                    )
                )
                continue
            uncovered.append(key)
            issues.append(
                L3AlbumAttributionIssue(
                    canonical_song_key=key,
                    issue_kind="uncovered",
                    representative_track_id=representative,
                    canonical_song_name=str(work.canonical_song_name),
                    canonical_artist_key=str(canonical_artist_id or ""),
                    candidate_project_ids=(),
                    candidate_project_names=(),
                    evidence_codes=("no_album_project_membership",),
                    evidence=_stable_evidence(
                        raw_play_count=int(work.raw_play_count),
                        raw_ms=int(work.raw_ms),
                        source_album_ids=tuple(work.source_album_ids),
                    ),
                )
            )
            continue
        candidates.sort(key=_candidate_rank)
        if key in invalid_overrides:
            conflicts.add(key)
            override = invalid_overrides[key]
            issues.append(
                L3AlbumAttributionIssue(
                    canonical_song_key=key,
                    issue_kind="invalid_override",
                    representative_track_id=_representative_track_id(conn, key, song_frame),
                    canonical_song_name=str(song_frame.iloc[0]["canonical_song_name"]),
                    canonical_artist_key=str(candidates[0].canonical_artist_id),
                    candidate_project_ids=tuple(item.project_id for item in candidates),
                    candidate_project_names=tuple(item.canonical_name for item in candidates),
                    evidence_codes=("override_target_missing",),
                    evidence=_stable_evidence(
                        override_id=int(override["override_id"]),
                        override_action=str(override["action"]),
                    ),
                )
            )
            continue
        if key in override_conflicts:
            issues.append(
                L3AlbumAttributionIssue(
                    canonical_song_key=key,
                    issue_kind="conflict",
                    representative_track_id=_representative_track_id(conn, key, song_frame),
                    canonical_song_name=str(song_frame.iloc[0]["canonical_song_name"]),
                    canonical_artist_key=str(candidates[0].canonical_artist_id),
                    candidate_project_ids=tuple(item.project_id for item in candidates),
                    candidate_project_names=tuple(item.canonical_name for item in candidates),
                    evidence_codes=("conflicting_manual_overrides",),
                    evidence=(),
                )
            )
            continue
        winner = candidates[0]
        decision_source = "automatic"
        confidence = 1.0 if _candidate_rank(winner)[0] <= 40 else 0.9
        evidence_codes = ["single_l3_album_owner", "catalog_membership"]

        override = overrides.get(key)
        if override is not None:
            target_id = int(override["target_project_id"])
            target_row = conn.execute(
                """SELECT project_id, canonical_name, artist_id, scope
                     FROM album_projects WHERE project_id=?""",
                (target_id,),
            ).fetchone()
            if target_row is None:
                conflicts.add(key)
                issues.append(
                    L3AlbumAttributionIssue(
                        canonical_song_key=key,
                        issue_kind="invalid_override",
                        representative_track_id=_representative_track_id(conn, key, song_frame),
                        canonical_song_name=str(song_frame.iloc[0]["canonical_song_name"]),
                        canonical_artist_key=str(candidates[0].canonical_artist_id),
                        candidate_project_ids=tuple(item.project_id for item in candidates),
                        candidate_project_names=tuple(item.canonical_name for item in candidates),
                        evidence_codes=("override_target_not_found",),
                        evidence=_stable_evidence(
                            override_id=int(override["override_id"]),
                            target_project_id=target_id,
                        ),
                    )
                )
                continue
            matching_origin = next(
                (candidate for candidate in candidates if candidate.project_id == target_id),
                None,
            )
            if matching_origin is None:
                matching_origin = winner
            winner = _ProjectCandidate(
                **{
                    **asdict(matching_origin),
                    "target_project_id": target_id,
                    "target_project_name": str(target_row["canonical_name"]),
                }
            )
            decision_source = "manual"
            confidence = 1.0
            evidence_codes.append(str(override["action"]))

        candidate_ids = tuple(candidate.project_id for candidate in candidates)
        artist_key = str(winner.canonical_artist_id)
        source_ids = tuple(sorted(set(int(value) for value in song_frame["project_id"])))
        kind = _attribution_kind(winner)
        if kind.endswith("_residual"):
            evidence_codes.append("no_stronger_native_project")
        elif winner.target_project_id != winner.project_id:
            evidence_codes.append("album_composition_parent")
        else:
            evidence_codes.append("native_release_project")

        decisions.append(
            L3AlbumAttributionDecision(
                canonical_song_key=key,
                representative_track_id=_representative_track_id(conn, key, song_frame),
                canonical_song_name=str(song_frame.iloc[0]["canonical_song_name"]),
                canonical_artist_key=artist_key,
                target_project_id=winner.target_project_id,
                target_project_name=winner.target_project_name,
                origin_release_project_id=winner.project_id,
                origin_project_name=winner.canonical_name,
                attribution_kind=kind,
                decision_source=decision_source,
                confidence=confidence,
                source_project_ids=source_ids,
                candidate_project_ids=candidate_ids,
                evidence_codes=tuple(sorted(set(evidence_codes))),
                evidence=_stable_evidence(
                    winning_rank=_candidate_rank(winner),
                    source_buckets=winner.source_buckets,
                    membership_roles=winner.membership_roles,
                    track_relation_tags=winner.track_relation_tags,
                    project_relation_tag=winner.relation_tag,
                    override_reason=(str(override["reason"]) if override is not None else None),
                ),
            )
        )

    decisions.sort(key=lambda item: item.canonical_song_key)
    issues.sort(key=lambda item: (item.canonical_song_key, item.issue_kind))
    exclusions.sort(key=lambda item: item.canonical_song_key)
    plan_rows: list[tuple[Any, ...]] = []
    for item in decisions:
        evidence_json = json.dumps(
            {
                "canonical_song_name": item.canonical_song_name,
                "target_project_name": item.target_project_name,
                "origin_project_name": item.origin_project_name,
                "source_project_ids": item.source_project_ids,
                "candidate_project_ids": item.candidate_project_ids,
                "evidence_codes": item.evidence_codes,
                "evidence": dict(item.evidence),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        plan_rows.append(
            (
                item.canonical_song_key,
                item.representative_track_id,
                item.canonical_artist_key,
                item.target_project_id,
                item.origin_release_project_id,
                item.attribution_kind,
                item.decision_source,
                item.confidence,
                evidence_json,
                L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                track_revision,
                album_revision,
            )
        )
    desired_digest = _desired_projection_digest(plan_rows)
    input_payload = {
        "track_revision": track_revision,
        "album_revision": album_revision,
        "rows": plan_rows,
        "issues": [item.to_dict() for item in issues],
        "exclusions": [item.to_dict() for item in exclusions],
        "uncovered": sorted(uncovered),
        "conflicts": sorted(conflicts),
    }
    input_digest = hashlib.sha256(
        json.dumps(input_payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()
    expected_issue_rows = tuple(
        (
            item.canonical_song_key,
            item.issue_kind,
            item.representative_track_id,
            item.canonical_artist_key,
            _issue_json(item),
            L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            track_revision,
            album_revision,
        )
        for item in issues
    )
    expected_exclusion_rows = tuple(
        (
            item.canonical_song_key,
            item.representative_track_id,
            item.canonical_artist_key,
            item.reason_code,
            _exclusion_json(item),
            L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            track_revision,
            album_revision,
        )
        for item in exclusions
    )
    state = get_l3_album_attribution_state(conn)
    state_ready = (
        state["status"] == "ready"
        and state["policy_version"] == L3_ALBUM_ATTRIBUTION_POLICY_VERSION
        and int(state["track_identity_revision"]) == track_revision
        and int(state["album_project_revision"]) == album_revision
        and state["mapping_digest"] == desired_digest
        and int(state["attributed_count"]) == len(decisions)
        and int(state["conflict_count"]) == len(conflicts)
        and int(state["uncovered_count"]) == len(uncovered)
        and int(state["scanned_count"]) == len(work_universe)
        and int(state["excluded_count"]) == len(exclusions)
    )
    return L3AlbumAttributionPlan(
        policy_version=L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
        track_identity_revision=track_revision,
        album_project_revision=album_revision,
        input_digest=input_digest,
        decisions=tuple(decisions),
        issues=tuple(issues),
        exclusions=tuple(exclusions),
        uncovered_song_keys=tuple(sorted(uncovered)),
        conflict_song_keys=tuple(sorted(conflicts)),
        excluded_song_keys=tuple(item.canonical_song_key for item in exclusions),
        scanned_song_count=len(work_universe),
        changed=(
            _current_projection_digest(conn) != desired_digest
            or _current_issue_rows(conn) != expected_issue_rows
            or _current_exclusion_rows(conn) != expected_exclusion_rows
            or not state_ready
        ),
    )


def build_l3_album_attribution_scope_health(conn: sqlite3.Connection) -> dict[str, Any]:
    """Report played-work and complete active-identity scopes independently."""

    required = (
        "tracks",
        "plays",
        "track_l1_identities",
        "album_projects",
        "album_project_tracks",
        "album_project_albums",
    )
    empty_statuses = {
        "historical_legacy": 0,
        "explained": 0,
        "needs_evidence": 0,
        "repairable": 0,
    }
    if not all(_table_exists(conn, table) for table in required):
        return {
            "available": False,
            "played_works": None,
            "all_identities": None,
            "problem_ledger": {"status_counts": empty_statuses, "entries": []},
            "writes_performed": False,
        }

    played = plan_l3_album_attributions(conn, include_unplayed=False)
    complete = plan_l3_album_attributions(conn, include_unplayed=True)

    def scope(plan: L3AlbumAttributionPlan) -> dict[str, int]:
        return {
            "scanned_work_count": plan.scanned_song_count,
            "attributed_work_count": len(plan.decisions),
            "issue_count": len(plan.issues),
            "uncovered_count": len(plan.uncovered_song_keys),
            "conflict_count": len(plan.conflict_song_keys),
            "excluded_count": len(plan.exclusions),
        }

    played_keys = {item.canonical_song_key for item in played.decisions}
    played_keys.update(item.canonical_song_key for item in played.issues)
    played_keys.update(item.canonical_song_key for item in played.exclusions)
    status_counts = dict(empty_statuses)
    entries: list[dict[str, Any]] = []
    for issue in complete.issues:
        evidence = dict(issue.evidence)
        is_played = issue.canonical_song_key in played_keys
        if issue.issue_kind in {"conflict", "invalid_override"}:
            status = "needs_evidence"
        elif is_played and evidence.get("source_album_ids"):
            status = "repairable"
        elif is_played:
            status = "needs_evidence"
        else:
            status = "historical_legacy"
        status_counts[status] += 1
        entries.append(
            {
                "canonical_song_key": issue.canonical_song_key,
                "representative_track_id": issue.representative_track_id,
                "issue_kind": issue.issue_kind,
                "scope": "played_works" if is_played else "all_identities",
                "status": status,
                "raw_play_count": int(evidence.get("raw_play_count", 0)),
                "raw_ms": int(evidence.get("raw_ms", 0)),
                "source_album_ids": list(evidence.get("source_album_ids", ())),
            }
        )

    identity_counts = conn.execute(
        """SELECT COUNT(*),
                  SUM(CASE WHEN identity_status='active' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN identity_status='superseded' THEN 1 ELSE 0 END)
             FROM track_l1_identities"""
    ).fetchone()
    all_scope = scope(complete)
    all_scope.update(
        {
            "identity_count": int(identity_counts[0] or 0),
            "active_identity_count": int(identity_counts[1] or 0),
            "superseded_identity_count": int(identity_counts[2] or 0),
        }
    )
    return {
        "available": True,
        "played_works": scope(played),
        "all_identities": all_scope,
        "problem_ledger": {"status_counts": status_counts, "entries": entries},
        "writes_performed": False,
    }


def reconcile_l3_album_attribution_dependencies(
    conn: sqlite3.Connection,
    *,
    include_unplayed: bool = False,
) -> L3AlbumAttributionPlan:
    """Repair only proven missing Album Project closures, then re-plan L3.

    This is intentionally narrower than the governance pipeline's full album
    rebuild.  It is safe for startup and search maintenance because it touches
    only albums named by an ``uncovered`` attribution issue (plus the
    representative track's own album when playback source metadata is absent).
    Conflicts and invalid overrides are never auto-resolved here. Runtime
    maintenance defaults to played works; complete governance coverage remains
    available through ``plan_l3_album_attributions`` with its default scope.
    """

    ensure_l3_album_attribution_schema(conn)
    plan = plan_l3_album_attributions(conn, include_unplayed=include_unplayed)
    uncovered_issues = tuple(issue for issue in plan.issues if issue.issue_kind == "uncovered")
    if not uncovered_issues:
        return plan

    album_ids = {
        int(album_id)
        for issue in uncovered_issues
        for album_id in dict(issue.evidence).get("source_album_ids", ())
    }
    album_ids.update(
        int(row[0])
        for issue in uncovered_issues
        for row in conn.execute(
            "SELECT album_id FROM tracks WHERE track_id=? AND album_id IS NOT NULL",
            (issue.representative_track_id,),
        ).fetchall()
    )
    if not album_ids:
        return plan

    from backend.domains.playback.album_projects import rebuild_album_projects_for_impact

    rebuild_album_projects_for_impact(
        conn,
        local_album_ids=album_ids,
        impact_scope_exact=True,
    )
    return plan_l3_album_attributions(conn, include_unplayed=include_unplayed)


def apply_l3_album_attribution_plan(
    conn: sqlite3.Connection,
    plan: L3AlbumAttributionPlan | None = None,
    *,
    commit: bool = True,
    ensure_schema: bool = True,
    include_unplayed: bool = True,
) -> L3AlbumAttributionApplyReport:
    """Publish one complete attribution projection atomically."""

    if ensure_schema:
        ensure_l3_album_attribution_schema(conn)
    fresh = plan_l3_album_attributions(conn, include_unplayed=include_unplayed)
    if plan is None:
        plan = fresh
    elif plan != fresh:
        raise RuntimeError("stale L3 album attribution plan")
    if plan.policy_version != L3_ALBUM_ATTRIBUTION_POLICY_VERSION:
        raise RuntimeError("unsupported L3 album attribution policy version")
    if not plan.changed:
        return L3AlbumAttributionApplyReport(
            decision_count=len(plan.decisions),
            automatic_count=sum(item.decision_source == "automatic" for item in plan.decisions),
            manual_count=sum(item.decision_source == "manual" for item in plan.decisions),
            uncovered_count=len(plan.uncovered_song_keys),
            conflict_count=len(plan.conflict_song_keys),
            excluded_count=len(plan.exclusions),
            scanned_count=plan.scanned_song_count,
            rows_inserted=0,
            attribution_revision=get_l3_album_attribution_revision(conn),
            changed=False,
            requires_downstream_refresh=False,
        )

    conn.execute("SAVEPOINT apply_l3_album_attribution")
    try:
        conn.execute(
            """UPDATE l3_album_attribution_revision_state
                  SET status='building', policy_version=?,
                      track_identity_revision=?, album_project_revision=?,
                      updated_at=CURRENT_TIMESTAMP
                WHERE state_id=1""",
            (
                L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                plan.track_identity_revision,
                plan.album_project_revision,
            ),
        )
        conn.execute("DELETE FROM l3_song_album_attributions")
        conn.execute("DELETE FROM l3_song_album_attribution_issues")
        conn.execute("DELETE FROM l3_song_album_attribution_exclusions")
        for decision in plan.decisions:
            evidence_json = json.dumps(
                {
                    "canonical_song_name": decision.canonical_song_name,
                    "target_project_name": decision.target_project_name,
                    "origin_project_name": decision.origin_project_name,
                    "source_project_ids": decision.source_project_ids,
                    "candidate_project_ids": decision.candidate_project_ids,
                    "evidence_codes": decision.evidence_codes,
                    "evidence": dict(decision.evidence),
                },
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            conn.execute(
                """INSERT INTO l3_song_album_attributions(
                       canonical_song_key, representative_track_id,
                       canonical_artist_key, target_project_id,
                       origin_release_project_id, attribution_kind,
                       decision_source, confidence, evidence_json,
                       policy_version, track_identity_revision,
                       album_project_revision
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.canonical_song_key,
                    decision.representative_track_id,
                    decision.canonical_artist_key,
                    decision.target_project_id,
                    decision.origin_release_project_id,
                    decision.attribution_kind,
                    decision.decision_source,
                    decision.confidence,
                    evidence_json,
                    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                    plan.track_identity_revision,
                    plan.album_project_revision,
                ),
            )
        for issue in plan.issues:
            conn.execute(
                """INSERT INTO l3_song_album_attribution_issues(
                       canonical_song_key, issue_kind, representative_track_id,
                       canonical_artist_key, evidence_json, policy_version,
                       track_identity_revision, album_project_revision
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    issue.canonical_song_key,
                    issue.issue_kind,
                    issue.representative_track_id,
                    issue.canonical_artist_key,
                    _issue_json(issue),
                    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                    plan.track_identity_revision,
                    plan.album_project_revision,
                ),
            )
        for exclusion in plan.exclusions:
            conn.execute(
                """INSERT INTO l3_song_album_attribution_exclusions(
                       canonical_song_key, representative_track_id,
                       canonical_artist_key, reason_code, evidence_json,
                       policy_version, track_identity_revision,
                       album_project_revision
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    exclusion.canonical_song_key,
                    exclusion.representative_track_id,
                    exclusion.canonical_artist_key,
                    exclusion.reason_code,
                    _exclusion_json(exclusion),
                    L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                    plan.track_identity_revision,
                    plan.album_project_revision,
                ),
            )
        mapping_digest = _current_projection_digest(conn)
        conn.execute(
            """UPDATE l3_album_attribution_revision_state
                  SET current_revision=current_revision+1,
                      status='ready', policy_version=?,
                      track_identity_revision=?, album_project_revision=?,
                      mapping_digest=?, attributed_count=?, conflict_count=?,
                      uncovered_count=?, scanned_count=?, excluded_count=?,
                      updated_at=CURRENT_TIMESTAMP
                WHERE state_id=1""",
            (
                L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                plan.track_identity_revision,
                plan.album_project_revision,
                mapping_digest,
                len(plan.decisions),
                len(plan.conflict_song_keys),
                len(plan.uncovered_song_keys),
                plan.scanned_song_count,
                len(plan.exclusions),
            ),
        )
        conn.execute("RELEASE SAVEPOINT apply_l3_album_attribution")
        if commit:
            conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT apply_l3_album_attribution")
        conn.execute("RELEASE SAVEPOINT apply_l3_album_attribution")
        raise

    return L3AlbumAttributionApplyReport(
        decision_count=len(plan.decisions),
        automatic_count=sum(item.decision_source == "automatic" for item in plan.decisions),
        manual_count=sum(item.decision_source == "manual" for item in plan.decisions),
        uncovered_count=len(plan.uncovered_song_keys),
        conflict_count=len(plan.conflict_song_keys),
        excluded_count=len(plan.exclusions),
        scanned_count=plan.scanned_song_count,
        rows_inserted=len(plan.decisions),
        attribution_revision=get_l3_album_attribution_revision(conn),
        changed=True,
        requires_downstream_refresh=True,
    )


def load_l3_song_album_attributions(
    conn: sqlite3.Connection,
    *,
    require_ready: bool = True,
) -> pd.DataFrame:
    """Return the published one-row-per-song L3 owner projection."""

    if not _table_exists(conn, "l3_song_album_attributions"):
        if require_ready:
            raise RuntimeError("L3 album attribution has not been built")
        return pd.DataFrame()
    state = get_l3_album_attribution_state(conn)
    if require_ready:
        expected_track_revision = _track_identity_revision(conn)
        expected_album_revision = _album_project_revision(conn)
        if (
            state["status"] != "ready"
            or state["policy_version"] != L3_ALBUM_ATTRIBUTION_POLICY_VERSION
            or int(state["track_identity_revision"]) != expected_track_revision
            or int(state["album_project_revision"]) != expected_album_revision
        ):
            raise RuntimeError(
                "L3 album attribution is missing or stale: "
                f"status={state['status']}, "
                f"track_revision={state['track_identity_revision']}/{expected_track_revision}, "
                f"album_revision={state['album_project_revision']}/{expected_album_revision}"
            )
    return pd.read_sql_query(
        """SELECT attribution.canonical_song_key,
                  attribution.representative_track_id,
                  representative.track_name AS canonical_song_name,
                  attribution.canonical_artist_key,
                  attribution.target_project_id AS project_id,
                  target.canonical_name AS album_project_name,
                  target.artist_id,
                  artist.artist_name,
                  target.primary_album_id,
                  target.release_date,
                  target.scope,
                  target.project_type,
                  target.include_in_charts,
                  attribution.origin_release_project_id,
                  attribution.attribution_kind,
                  attribution.decision_source,
                  attribution.confidence,
                  attribution.evidence_json,
                  attribution.policy_version
             FROM l3_song_album_attributions attribution
             JOIN tracks representative
               ON representative.track_id=attribution.representative_track_id
             JOIN album_projects target
               ON target.project_id=attribution.target_project_id
             LEFT JOIN artists artist ON artist.artist_id=target.artist_id
            ORDER BY attribution.canonical_song_key""",
        conn,
    )
