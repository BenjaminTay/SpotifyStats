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

L3_ALBUM_ATTRIBUTION_POLICY_VERSION = "l3_native_album_attribution_v1"

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

CREATE TABLE IF NOT EXISTS l3_album_attribution_revision_state (
    state_id         INTEGER PRIMARY KEY CHECK(state_id = 1),
    current_revision INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'empty'
                          CHECK(status IN ('empty', 'building', 'ready', 'failed')),
    policy_version   TEXT NOT NULL DEFAULT 'l3_native_album_attribution_v1',
    track_identity_revision INTEGER NOT NULL DEFAULT 0,
    album_project_revision  INTEGER NOT NULL DEFAULT 0,
    mapping_digest    TEXT NOT NULL DEFAULT '',
    attributed_count  INTEGER NOT NULL DEFAULT 0,
    conflict_count    INTEGER NOT NULL DEFAULT 0,
    uncovered_count   INTEGER NOT NULL DEFAULT 0,
    updated_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT OR IGNORE INTO l3_album_attribution_revision_state(
    state_id, current_revision, policy_version
) VALUES (1, 0, 'l3_native_album_attribution_v1');
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
class L3AlbumAttributionPlan:
    policy_version: str
    track_identity_revision: int
    album_project_revision: int
    input_digest: str
    decisions: tuple[L3AlbumAttributionDecision, ...]
    issues: tuple[L3AlbumAttributionIssue, ...]
    uncovered_song_keys: tuple[str, ...]
    conflict_song_keys: tuple[str, ...]
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
            "updated_at": None,
        }
    row = conn.execute(
        """SELECT current_revision, status, policy_version,
                  track_identity_revision, album_project_revision,
                  mapping_digest, attributed_count, conflict_count,
                  uncovered_count, updated_at
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


def _canonical_artist_ids(conn: sqlite3.Connection) -> dict[int, int]:
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
    is_compilation = candidate.project_type == "compilation_exclusive"

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
    if candidate.project_type == "compilation_exclusive":
        return "compilation_exclusive"
    return "studio_album"


def _representative_track_id(conn: sqlite3.Connection, key: str, frame: pd.DataFrame) -> int:
    if key.startswith("composition:"):
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


def _desired_projection_digest(plan_rows: list[tuple[Any, ...]]) -> str:
    return hashlib.sha256(
        json.dumps(plan_rows, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def plan_l3_album_attributions(conn: sqlite3.Connection) -> L3AlbumAttributionPlan:
    """Build the complete desired one-owner L3 album projection without writes."""

    track_revision = _track_identity_revision(conn)
    album_revision = _album_project_revision(conn)
    memberships = _load_release_memberships(conn)
    if memberships.empty:
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
        )
        return L3AlbumAttributionPlan(
            policy_version=L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
            track_identity_revision=track_revision,
            album_project_revision=album_revision,
            input_digest=empty_digest,
            decisions=(),
            issues=(),
            uncovered_song_keys=(),
            conflict_song_keys=(),
            scanned_song_count=0,
            changed=(
                _current_projection_digest(conn) != empty_digest
                or bool(_current_issue_rows(conn))
                or not state_ready
            ),
        )

    canonical_artists = _canonical_artist_ids(conn)
    parent_map = _composition_parent_map(conn, canonical_artists)
    track_to_song_key = {
        int(row.track_id): str(row.canonical_song_key)
        for row in memberships[["track_id", "canonical_song_key"]]
        .drop_duplicates("track_id")
        .itertuples(index=False)
    }
    overrides, override_conflicts, invalid_overrides = _active_overrides(conn, track_to_song_key)

    decisions: list[L3AlbumAttributionDecision] = []
    issues: list[L3AlbumAttributionIssue] = []
    uncovered: list[str] = []
    conflicts = set(override_conflicts)

    for song_key, song_frame in memberships.groupby("canonical_song_key", sort=True):
        key = str(song_key)
        candidates: list[_ProjectCandidate] = []
        for project_id, project_frame in song_frame.groupby("project_id", sort=True):
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
            uncovered.append(key)
            issues.append(
                L3AlbumAttributionIssue(
                    canonical_song_key=key,
                    issue_kind="uncovered",
                    representative_track_id=_representative_track_id(conn, key, song_frame),
                    canonical_song_name=str(song_frame.iloc[0]["canonical_song_name"]),
                    canonical_artist_key="",
                    candidate_project_ids=(),
                    candidate_project_names=(),
                    evidence_codes=("no_album_project_membership",),
                    evidence=(),
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
    )
    return L3AlbumAttributionPlan(
        policy_version=L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
        track_identity_revision=track_revision,
        album_project_revision=album_revision,
        input_digest=input_digest,
        decisions=tuple(decisions),
        issues=tuple(issues),
        uncovered_song_keys=tuple(sorted(uncovered)),
        conflict_song_keys=tuple(sorted(conflicts)),
        scanned_song_count=int(memberships["canonical_song_key"].nunique()),
        changed=(
            _current_projection_digest(conn) != desired_digest
            or _current_issue_rows(conn) != expected_issue_rows
            or not state_ready
        ),
    )


def apply_l3_album_attribution_plan(
    conn: sqlite3.Connection,
    plan: L3AlbumAttributionPlan | None = None,
    *,
    commit: bool = True,
    ensure_schema: bool = True,
) -> L3AlbumAttributionApplyReport:
    """Publish one complete attribution projection atomically."""

    if ensure_schema:
        ensure_l3_album_attribution_schema(conn)
    fresh = plan_l3_album_attributions(conn)
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
        mapping_digest = _current_projection_digest(conn)
        conn.execute(
            """UPDATE l3_album_attribution_revision_state
                  SET current_revision=current_revision+1,
                      status='ready', policy_version=?,
                      track_identity_revision=?, album_project_revision=?,
                      mapping_digest=?, attributed_count=?, conflict_count=?,
                      uncovered_count=?, updated_at=CURRENT_TIMESTAMP
                WHERE state_id=1""",
            (
                L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
                plan.track_identity_revision,
                plan.album_project_revision,
                mapping_digest,
                len(plan.decisions),
                len(plan.conflict_song_keys),
                len(plan.uncovered_song_keys),
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
