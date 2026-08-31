"""Deterministic, evidence-backed Album Project auto merges.

The weak ``album_spotify_links`` relation is useful for discovery, but a link
alone is not an album identity.  This module proposes a release merge only
when every participating standalone Album Project independently proves either
the same complete Spotify release or one of three tightly controlled
equivalent-release relations: a remaster with the same ordered repertoire, a
deluxe superset, or a catalog alias with the same date and ordered repertoire.
Names are discovery evidence, never the deciding signal.

Accepted plans are materialised as inferred ``release_groups``.  Existing
Album Project rebuilding then keeps source albums as attribution metadata while
publishing one statistics-level project.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from backend.domains.playback.album_projects import (
    _ensure_album_project_revision_schema,
    ensure_album_project_schema,
    get_album_project_revision,
    rebuild_album_projects,
)

_COMPILATION_NAME_MARKERS = (
    "精选",
    "精選",
    "greatest hits",
    "best of",
    "anthology",
    "compilation",
)

ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION = "spotify_complete_release_v2"

_RELEASE_PACKAGING_MARKERS = (
    "remaster",
    "remastered",
    "edition",
    "deluxe",
    "expanded",
    "anniversary",
    "platinum",
    "complete",
    "special",
    "bonus",
)

_FORBIDDEN_ALTERNATE_PATTERNS = (
    re.compile(
        r"\blive\b|\bconcert\b|\blong\s+pond\s+studio\s+sessions?\b|"
        r"现场|現場|演唱会|演唱會",
        re.I,
    ),
    re.compile(r"\bacoustic\b|\bunplugged\b|不插电|不插電|原声版|原聲版", re.I),
    re.compile(r"\bremix(?:es)?\b|\bmixes\b|混音", re.I),
    re.compile(
        r"taylor\s*['’]?s\s+version|re[ -]?record(?:ed|ing)?|重录|重錄",
        re.I,
    ),
)

_REMASTER_PATTERN = re.compile(r"\bremaster(?:ed)?\b", re.I)
_DELUXE_PATTERN = re.compile(
    r"\b(?:deluxe|expanded|anniversary|platinum|complete|special)\b|"
    r"\bbonus\s+tracks?\b",
    re.I,
)
_TRACK_REMASTER_SUFFIXES = (
    re.compile(r"\s*[\[(][^\])]*remaster(?:ed)?[^\])]*[\])]\s*$", re.I),
    re.compile(
        r"\s+(?:-|:|–|—)\s*(?:(?:19|20)\d{2}\s+)?"
        r"remaster(?:ed)?(?:\s+(?:19|20)\d{2})?\s*$",
        re.I,
    ),
)

_RELATION_PRIORITY = {
    "exact_release": 0,
    "catalog_alias_equivalent": 1,
    "remaster_equivalent": 2,
    "deluxe_superset": 3,
}

_EXTERNAL_EVIDENCE_TYPE = {
    "exact_release": "catalog_exact",
    "catalog_alias_equivalent": "catalog_alias_equivalent",
    "remaster_equivalent": "remaster_equivalent",
    "deluxe_superset": "deluxe_superset",
}

_EXTERNAL_CONFIDENCE = {
    "exact_release": 1.0,
    "catalog_alias_equivalent": 0.99,
    "remaster_equivalent": 0.99,
    "deluxe_superset": 0.98,
}


@dataclass(frozen=True)
class AlbumProjectExternalIdentity:
    """One provider release identity materialised on the merged project."""

    spotify_album_id: str
    evidence_type: str
    confidence: float
    is_primary: bool


@dataclass(frozen=True)
class AlbumProjectAutoMergeCandidate:
    """One immutable, reviewable release merge proposal."""

    candidate_key: str
    project_ids: tuple[int, ...]
    album_ids: tuple[int, ...]
    canonical_name: str
    artist_id: int
    primary_album_id: int
    spotify_album_id: str
    spotify_album_ids: tuple[str, ...]
    external_identities: tuple[AlbumProjectExternalIdentity, ...]
    relation_types: tuple[str, ...]
    release_date: str
    album_artists: str
    complete_track_count: int
    evidence_codes: tuple[str, ...]


@dataclass(frozen=True)
class AlbumProjectAutoMergePlan:
    """Side-effect-free result of scanning the current inferred projects."""

    candidates: tuple[AlbumProjectAutoMergeCandidate, ...]
    scanned_project_count: int
    strong_evidence_project_count: int
    skipped_reason_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AlbumProjectAutoMergeApplyReport:
    """Execution evidence returned after an atomic batch and rebuild."""

    candidate_count: int
    groups_created: int
    projects_merged: int
    albums_merged: int
    release_group_ids: tuple[int, ...]
    album_project_revision: int
    requires_downstream_refresh: bool


@dataclass(frozen=True)
class _ProjectReleaseEvidence:
    project_id: int
    album_id: int
    project_name: str
    artist_id: int
    artist_name: str
    local_track_count: int
    spotify_album_id: str
    spotify_album_name: str
    release_date: str
    album_artists: str
    total_tracks: int
    track_list: tuple[str, ...]
    link_track_count: int
    confidence: float


@dataclass(frozen=True)
class _EvidenceEdge:
    left: _ProjectReleaseEvidence
    right: _ProjectReleaseEvidence
    relation_type: str


class _ProjectSets:
    """Minimal deterministic disjoint-set helper for equivalent releases."""

    def __init__(self, project_ids: set[int]):
        self.parent = {project_id: project_id for project_id in project_ids}

    def find(self, project_id: int) -> int:
        parent = self.parent[project_id]
        if parent != project_id:
            self.parent[project_id] = self.find(parent)
        return self.parent[project_id]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        survivor, absorbed = sorted((left_root, right_root))
        self.parent[absorbed] = survivor


def normalize_album_release_name(value: str | None) -> str:
    """Return a conservative identity key for release-name comparisons."""

    normalized = unicodedata.normalize("NFKC", value or "").casefold().strip()
    normalized = normalized.translate({ord("–"): "-", ord("—"): "-", ord("："): ":"})
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s*([:()\[\]-])\s*", r"\1", normalized)
    # Packaging labels describe a Spotify release edition, not a different
    # album project. This only broadens metadata discovery; the exact-release
    # or equivalent-release evidence gates below still decide every merge.
    packaging = re.search(r"(?:\(([^()]*)\)|\[([^\[\]]*)\])$", normalized)
    if packaging:
        suffix = next((part for part in packaging.groups() if part is not None), "")
        if any(marker in suffix for marker in _RELEASE_PACKAGING_MARKERS):
            normalized = normalized[: packaging.start()].strip()
    return normalized


def plan_album_project_auto_merges(conn: sqlite3.Connection) -> AlbumProjectAutoMergePlan:
    """Build a dry-run plan without mutating release or project tables.

    Scope is intentionally narrow:

    * only inferred, release-scope, non-compilation Album Projects;
    * only standalone source albums not already governed by a release group;
    * only complete Spotify album/EP metadata with artist and release date;
    * the local album name must match the Spotify release after conservative
      normalisation;
    * at least one locally linked Spotify track must occur in the complete
      Spotify track list;
    * every project in a candidate must point unambiguously at the same exact
      release or one controlled equivalent-release family;
    * different provider IDs merge only through ordered track equivalence for
      remasters/catalog aliases, or an ordered bounded superset for deluxe
      editions.

    Live, acoustic, remix, Taylor's Version and compilation releases remain
    fail-closed. Existing multi-album bundles are not reinterpreted here.
    """

    skipped: Counter[str] = Counter()
    projects = conn.execute(
        """SELECT ap.project_id, ap.canonical_name, ap.artist_id,
                  ar.artist_name, apa.album_id,
                  (SELECT COUNT(DISTINCT apt.track_id)
                     FROM album_project_tracks apt
                    WHERE apt.project_id=ap.project_id) AS local_track_count
             FROM album_projects ap
             JOIN artists ar ON ar.artist_id=ap.artist_id
             JOIN album_project_albums apa ON apa.project_id=ap.project_id
            WHERE ap.is_manual=0
              AND ap.scope='release'
              AND ap.project_type='album'
              AND NOT EXISTS (
                    SELECT 1
                      FROM release_group_members rgm
                     WHERE rgm.album_id=apa.album_id
              )
            ORDER BY ap.project_id, apa.album_id"""
    ).fetchall()
    scanned_project_ids = {int(row["project_id"]) for row in projects}

    albums_by_project: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for row in projects:
        albums_by_project[int(row["project_id"])].append(row)

    evidence_by_project: dict[int, list[_ProjectReleaseEvidence]] = {}
    for project_id, rows in albums_by_project.items():
        # An inferred project with multiple source albums already encodes bundle
        # semantics and must not be reinterpreted by this standalone detector.
        if len(rows) != 1:
            skipped["existing_multi_album_project"] += 1
            continue
        row = rows[0]
        project_name = str(row["canonical_name"] or "")
        if _looks_like_compilation_name(project_name):
            skipped["compilation_policy_frozen"] += 1
            continue
        strong = _strong_release_evidence_for_album(
            conn,
            project_id=project_id,
            album_id=int(row["album_id"]),
            project_name=project_name,
            artist_id=int(row["artist_id"]),
            artist_name=str(row["artist_name"] or ""),
            local_track_count=int(row["local_track_count"] or 0),
            skipped=skipped,
        )
        if strong:
            evidence_by_project[project_id] = strong

    track_cache: dict[str, tuple[tuple[str, str, str], ...] | None] = {}
    ambiguous_projects = _ambiguous_evidence_projects(conn, evidence_by_project, track_cache)
    skipped["ambiguous_complete_release_evidence"] += len(ambiguous_projects)
    all_evidence = sorted(
        (
            item
            for project_id, rows in evidence_by_project.items()
            if project_id not in ambiguous_projects
            for item in rows
        ),
        key=lambda item: (item.project_id, item.spotify_album_id),
    )
    edges: list[_EvidenceEdge] = []
    exact_groups: dict[tuple[str, str, str, str, str], list[_ProjectReleaseEvidence]] = defaultdict(
        list
    )
    family_groups: dict[tuple[str, str], list[_ProjectReleaseEvidence]] = defaultdict(list)
    for evidence in all_evidence:
        exact_groups[_release_fingerprint(evidence)].append(evidence)
        family_groups[_release_family_key(evidence)].append(evidence)
    for exact_evidence in exact_groups.values():
        for index, left in enumerate(exact_evidence):
            for right in exact_evidence[index + 1 :]:
                if left.project_id != right.project_id:
                    edges.append(_EvidenceEdge(left, right, "exact_release"))
    for family_evidence in family_groups.values():
        for index, left in enumerate(family_evidence):
            for right in family_evidence[index + 1 :]:
                if left.project_id == right.project_id or _release_fingerprint(
                    left
                ) == _release_fingerprint(right):
                    continue
                relation_type = _equivalent_release_relation(conn, left, right, track_cache)
                if relation_type is not None:
                    edges.append(_EvidenceEdge(left, right, relation_type))

    connected_project_ids = {
        project_id for edge in edges for project_id in (edge.left.project_id, edge.right.project_id)
    }
    sets = _ProjectSets(connected_project_ids)
    for edge in edges:
        sets.union(edge.left.project_id, edge.right.project_id)
    components: dict[int, set[int]] = defaultdict(set)
    for project_id in connected_project_ids:
        components[sets.find(project_id)].add(project_id)

    candidates: list[AlbumProjectAutoMergeCandidate] = []
    for project_ids_set in sorted(components.values(), key=lambda values: tuple(sorted(values))):
        component_edges = [
            edge
            for edge in edges
            if edge.left.project_id in project_ids_set and edge.right.project_id in project_ids_set
        ]
        candidate_evidence = sorted(
            {
                (item.project_id, item.spotify_album_id): item
                for edge in component_edges
                for item in (edge.left, edge.right)
            }.values(),
            key=lambda item: (item.project_id, item.spotify_album_id),
        )
        project_ids = tuple(sorted(project_ids_set))
        album_ids = tuple(sorted({item.album_id for item in candidate_evidence}))
        relation_types = tuple(
            sorted(
                {edge.relation_type for edge in component_edges},
                key=lambda value: _RELATION_PRIORITY[value],
            )
        )
        primary = _select_primary_evidence(candidate_evidence)
        spotify_album_ids = tuple(sorted({item.spotify_album_id for item in candidate_evidence}))
        external_identities = _external_identities(
            component_edges,
            primary_spotify_album_id=primary.spotify_album_id,
        )
        artist_id = _select_project_artist_id(conn, candidate_evidence, primary)
        candidates.append(
            AlbumProjectAutoMergeCandidate(
                candidate_key=_candidate_key(spotify_album_ids, album_ids),
                project_ids=project_ids,
                album_ids=album_ids,
                canonical_name=primary.spotify_album_name,
                artist_id=artist_id,
                primary_album_id=primary.album_id,
                spotify_album_id=primary.spotify_album_id,
                spotify_album_ids=spotify_album_ids,
                external_identities=external_identities,
                relation_types=relation_types,
                release_date=primary.release_date,
                album_artists=primary.album_artists,
                complete_track_count=primary.total_tracks,
                evidence_codes=_candidate_evidence_codes(relation_types),
            )
        )

    return AlbumProjectAutoMergePlan(
        candidates=tuple(sorted(candidates, key=lambda item: item.candidate_key)),
        scanned_project_count=len(scanned_project_ids),
        strong_evidence_project_count=len(evidence_by_project),
        skipped_reason_counts=tuple(sorted(skipped.items())),
    )


def apply_album_project_auto_merge_plan(
    conn: sqlite3.Connection,
    plan: AlbumProjectAutoMergePlan,
    *,
    commit: bool = True,
    ensure_schema: bool = True,
) -> AlbumProjectAutoMergeApplyReport:
    """Apply a previously generated plan as one transaction and rebuild once."""

    if not plan.candidates:
        return AlbumProjectAutoMergeApplyReport(
            candidate_count=0,
            groups_created=0,
            projects_merged=0,
            albums_merged=0,
            release_group_ids=(),
            album_project_revision=get_album_project_revision(conn),
            requires_downstream_refresh=False,
        )

    _validate_plan_is_fresh(conn, plan)
    # Schema helpers use ``executescript`` for compatibility and SQLite commits
    # before executescript. Run them before opening the atomic batch savepoint.
    if ensure_schema:
        ensure_album_project_schema(conn)
        _ensure_album_project_revision_schema(conn)
    release_group_ids: list[int] = []
    conn.execute("SAVEPOINT apply_album_project_auto_merge_plan")
    try:
        for candidate in plan.candidates:
            existing = conn.execute(
                """SELECT group_id, is_manual
                     FROM release_groups
                    WHERE canonical_name=? AND artist_id=? AND scope='release'""",
                (candidate.canonical_name, candidate.artist_id),
            ).fetchone()
            if existing is not None:
                if int(existing["is_manual"] or 0):
                    raise RuntimeError("auto merge collides with a manual release group")
                group_id = int(existing["group_id"])
                conn.execute(
                    """UPDATE release_groups
                          SET primary_album_id=?
                        WHERE group_id=?""",
                    (candidate.primary_album_id, group_id),
                )
            else:
                cursor = conn.execute(
                    """INSERT INTO release_groups(
                           canonical_name, artist_id, primary_album_id, scope, is_manual
                       ) VALUES (?, ?, ?, 'release', 0)""",
                    (
                        candidate.canonical_name,
                        candidate.artist_id,
                        candidate.primary_album_id,
                    ),
                )
                group_id = int(cursor.lastrowid)
            conn.executemany(
                "INSERT OR IGNORE INTO release_group_members(group_id, album_id) VALUES (?, ?)",
                ((group_id, album_id) for album_id in candidate.album_ids),
            )
            release_group_ids.append(group_id)

        # The existing rebuild is the single publisher for project identities,
        # source-album membership, track membership, and project revision.
        rebuild_album_projects(conn, commit=False, ensure_schema=False)
        for candidate in plan.candidates:
            project_row = conn.execute(
                """SELECT project_id
                     FROM album_project_albums
                    WHERE album_id=?
                    ORDER BY project_id
                    LIMIT 1""",
                (candidate.primary_album_id,),
            ).fetchone()
            if project_row is None:
                raise RuntimeError(
                    f"rebuilt Album Project missing primary album {candidate.primary_album_id}"
                )
            project_id = int(project_row[0])
            conn.execute(
                """UPDATE album_projects
                      SET normalized_name=?, album_artist_key=?,
                          identity_policy_version=?
                    WHERE project_id=?""",
                (
                    normalize_album_release_name(candidate.canonical_name),
                    normalize_album_release_name(candidate.album_artists),
                    ALBUM_PROJECT_AUTO_IDENTITY_POLICY_VERSION,
                    project_id,
                ),
            )
            # A project may legitimately own several Spotify Album IDs (for
            # example original and remastered catalog releases), while the
            # provider-level primary remains unique.
            conn.execute(
                """UPDATE album_project_external_ids
                      SET is_primary=0, updated_at=CURRENT_TIMESTAMP
                    WHERE project_id=? AND provider='spotify'""",
                (project_id,),
            )
            for external in sorted(
                candidate.external_identities,
                key=lambda item: (item.is_primary, item.spotify_album_id),
            ):
                conn.execute(
                    """INSERT INTO album_project_external_ids(
                           provider, external_album_id, project_id, evidence_type,
                           confidence, is_primary
                       ) VALUES ('spotify', ?, ?, ?, ?, ?)
                       ON CONFLICT(provider, external_album_id) DO UPDATE SET
                           project_id=excluded.project_id,
                           evidence_type=excluded.evidence_type,
                           confidence=excluded.confidence,
                           is_primary=excluded.is_primary,
                           updated_at=CURRENT_TIMESTAMP""",
                    (
                        external.spotify_album_id,
                        project_id,
                        external.evidence_type,
                        external.confidence,
                        int(external.is_primary),
                    ),
                )
        conn.execute("RELEASE SAVEPOINT apply_album_project_auto_merge_plan")
        if commit:
            conn.commit()
    except Exception:
        # ``rebuild_album_projects`` commits only on success.  On failure the
        # outer savepoint is still available and protects all inserted groups.
        try:
            conn.execute("ROLLBACK TO SAVEPOINT apply_album_project_auto_merge_plan")
            conn.execute("RELEASE SAVEPOINT apply_album_project_auto_merge_plan")
        except sqlite3.OperationalError:
            conn.rollback()
        raise

    return AlbumProjectAutoMergeApplyReport(
        candidate_count=len(plan.candidates),
        groups_created=len(set(release_group_ids)),
        projects_merged=sum(len(candidate.project_ids) for candidate in plan.candidates),
        albums_merged=sum(len(candidate.album_ids) for candidate in plan.candidates),
        release_group_ids=tuple(release_group_ids),
        album_project_revision=get_album_project_revision(conn),
        requires_downstream_refresh=True,
    )


def auto_merge_album_projects(conn: sqlite3.Connection) -> AlbumProjectAutoMergeApplyReport:
    """Convenience batch interface: dry-run from current state, then apply once."""

    return apply_album_project_auto_merge_plan(conn, plan_album_project_auto_merges(conn))


def _strong_release_evidence_for_album(
    conn: sqlite3.Connection,
    *,
    project_id: int,
    album_id: int,
    project_name: str,
    artist_id: int,
    artist_name: str,
    local_track_count: int,
    skipped: Counter[str],
) -> list[_ProjectReleaseEvidence]:
    rows = conn.execute(
        """SELECT asl.spotify_album_id, MAX(asl.confidence) AS confidence,
                  MAX(asl.track_count) AS link_track_count,
                  sam.album_name, sam.album_type, sam.release_date,
                  sam.album_artists, sam.total_tracks, sam.track_list
             FROM album_spotify_links asl
             JOIN spotify_album_meta sam
               ON sam.spotify_album_id=asl.spotify_album_id
            WHERE asl.album_id=?
            GROUP BY asl.spotify_album_id, sam.album_name, sam.album_type,
                     sam.release_date, sam.album_artists, sam.total_tracks,
                     sam.track_list
            ORDER BY asl.spotify_album_id""",
        (album_id,),
    ).fetchall()
    result: list[_ProjectReleaseEvidence] = []
    for row in rows:
        album_type = str(row["album_type"] or "").casefold()
        if album_type == "compilation":
            skipped["compilation_policy_frozen"] += 1
            continue
        if album_type not in {"album", "ep"}:
            skipped["not_album_or_ep"] += 1
            continue
        spotify_name = str(row["album_name"] or "")
        if _has_forbidden_alternate_marker(project_name) or _has_forbidden_alternate_marker(
            spotify_name
        ):
            skipped["alternate_release_policy_frozen"] += 1
            continue
        if _catalog_album_name_key(project_name) != _catalog_album_name_key(spotify_name):
            skipped["release_name_mismatch"] += 1
            continue
        release_date = str(row["release_date"] or "").strip()
        album_artists = str(row["album_artists"] or "").strip()
        if not release_date or not album_artists:
            skipped["incomplete_release_metadata"] += 1
            continue
        track_list = _parse_complete_track_list(row["track_list"], row["total_tracks"])
        if track_list is None:
            skipped["incomplete_track_list"] += 1
            continue
        if not _local_album_occurs_in_complete_release(
            conn,
            album_id,
            str(row["spotify_album_id"]),
            track_list,
        ):
            skipped["local_track_not_in_complete_release"] += 1
            continue
        confidence = float(row["confidence"] or 0.0)
        if confidence < 0.9:
            skipped["low_confidence_link"] += 1
            continue
        result.append(
            _ProjectReleaseEvidence(
                project_id=project_id,
                album_id=album_id,
                project_name=project_name,
                artist_id=artist_id,
                artist_name=artist_name,
                local_track_count=local_track_count,
                spotify_album_id=str(row["spotify_album_id"]),
                spotify_album_name=spotify_name,
                release_date=release_date,
                album_artists=album_artists,
                total_tracks=len(track_list),
                track_list=track_list,
                link_track_count=int(row["link_track_count"] or 0),
                confidence=confidence,
            )
        )
    return result


def _parse_complete_track_list(raw: Any, total_tracks: Any) -> tuple[str, ...] | None:
    try:
        expected = int(total_tracks or 0)
        decoded = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if expected <= 0 or not isinstance(decoded, list):
        return None
    track_ids: list[str] = []
    for item in decoded:
        if isinstance(item, dict):
            item = item.get("id") or item.get("spotify_track_id") or item.get("uri")
        if not isinstance(item, str) or not item.strip():
            return None
        track_ids.append(_normalize_spotify_track_id(item))
    if len(track_ids) != expected or len(set(track_ids)) != expected:
        return None
    return tuple(track_ids)


def _local_spotify_track_ids(conn: sqlite3.Connection, album_id: int) -> set[str]:
    rows = conn.execute(
        """SELECT spotify_track_id
             FROM tracks
            WHERE album_id=? AND spotify_track_id IS NOT NULL
            UNION
           SELECT t.spotify_track_id
             FROM track_albums ta
             JOIN tracks t ON t.track_id=ta.track_id
            WHERE ta.album_id=? AND t.spotify_track_id IS NOT NULL""",
        (album_id, album_id),
    ).fetchall()
    return {_normalize_spotify_track_id(str(row[0])) for row in rows if row[0]}


def _local_album_occurs_in_complete_release(
    conn: sqlite3.Connection,
    album_id: int,
    spotify_album_id: str,
    track_list: tuple[str, ...],
) -> bool:
    """Verify membership through ID, ISRC, or provider-owned title evidence."""

    local_track_ids = _local_spotify_track_ids(conn, album_id)
    complete_track_ids = set(track_list)
    if local_track_ids.intersection(complete_track_ids):
        return True
    if not local_track_ids or not complete_track_ids:
        return False

    local_placeholders = ",".join("?" for _ in local_track_ids)
    complete_placeholders = ",".join("?" for _ in complete_track_ids)
    local_isrcs = {
        str(row[0]).strip().casefold()
        for row in conn.execute(
            f"""SELECT DISTINCT isrc FROM spotify_track_meta
                 WHERE spotify_track_id IN ({local_placeholders})
                   AND isrc IS NOT NULL AND trim(isrc) != ''""",
            tuple(sorted(local_track_ids)),
        ).fetchall()
    }
    if not local_isrcs:
        return False
    complete_isrcs = {
        str(row[0]).strip().casefold()
        for row in conn.execute(
            f"""SELECT DISTINCT isrc FROM spotify_track_meta
                 WHERE spotify_track_id IN ({complete_placeholders})
                   AND isrc IS NOT NULL AND trim(isrc) != ''""",
            tuple(sorted(complete_track_ids)),
        ).fetchall()
    }
    if local_isrcs.intersection(complete_isrcs):
        return True

    # Some historical Spotify IDs were relinked with a changed ISRC even though
    # the provider metadata still places the local track on this exact release.
    # Accept that only when its title also occurs in the already-validated
    # complete track list. This remains independent of album_spotify_links.
    complete_track_placeholders = ",".join("?" for _ in complete_track_ids)
    complete_names = {
        _normalize_track_evidence_name(str(row[0]))
        for row in conn.execute(
            f"""SELECT track_name FROM spotify_track_meta
                 WHERE spotify_track_id IN ({complete_track_placeholders})""",
            tuple(sorted(complete_track_ids)),
        ).fetchall()
        if row[0]
    }
    if not complete_names:
        return False
    local_track_placeholders = ",".join("?" for _ in local_track_ids)
    local_names = {
        _normalize_track_evidence_name(str(row[0]))
        for row in conn.execute(
            f"""SELECT track_name FROM spotify_track_meta
                 WHERE spotify_track_id IN ({local_track_placeholders})
                   AND spotify_album_id=?""",
            tuple(sorted(local_track_ids)) + (spotify_album_id,),
        ).fetchall()
        if row[0]
    }
    return bool(local_names.intersection(complete_names))


def _normalize_track_evidence_name(value: str) -> str:
    """Normalize exact provider titles without applying L2 title semantics."""

    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    return re.sub(r"\s+", " ", normalized)


def _normalize_spotify_track_id(value: str) -> str:
    return value.rsplit(":", 1)[-1].strip()


def _looks_like_compilation_name(value: str) -> bool:
    normalized = normalize_album_release_name(value)
    return any(marker in normalized for marker in _COMPILATION_NAME_MARKERS)


def _has_forbidden_alternate_marker(value: str) -> bool:
    normalized = unicodedata.normalize("NFKC", value or "")
    return any(pattern.search(normalized) for pattern in _FORBIDDEN_ALTERNATE_PATTERNS)


def _catalog_album_name_key(value: str) -> str:
    """Return an alias-tolerant key used only behind full catalog evidence."""

    normalized = normalize_album_release_name(value)
    normalized = re.sub(
        r"\s*(?:-|:)?\s*(?:(?:19|20)\d{2}\s+)?remaster(?:ed)?(?:\s+(?:19|20)\d{2})?$",
        "",
        normalized,
        flags=re.I,
    ).strip()
    normalized = re.sub(
        r"\s*(?:-|:)?\s*(?:deluxe|expanded|anniversary|platinum|complete|special)"
        r"(?:\s+edition|\s+version)?$",
        "",
        normalized,
        flags=re.I,
    ).strip()
    return "".join(character for character in normalized if character.isalnum())


def _release_relation_tags(value: str) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", value or "")
    tags: set[str] = set()
    if _REMASTER_PATTERN.search(normalized):
        tags.add("remaster")
    if _DELUXE_PATTERN.search(normalized):
        tags.add("deluxe")
    return frozenset(tags)


def _release_family_key(evidence: _ProjectReleaseEvidence) -> tuple[str, str]:
    return (
        normalize_album_release_name(evidence.album_artists),
        _catalog_album_name_key(evidence.spotify_album_name),
    )


def _release_track_evidence(
    conn: sqlite3.Connection,
    evidence: _ProjectReleaseEvidence,
    cache: dict[str, tuple[tuple[str, str, str], ...] | None],
) -> tuple[tuple[str, str, str], ...] | None:
    cached = cache.get(evidence.spotify_album_id)
    if evidence.spotify_album_id in cache:
        return cached
    track_ids = tuple(evidence.track_list)
    placeholders = ",".join("?" for _ in track_ids)
    rows = conn.execute(
        f"""SELECT spotify_track_id, track_name, isrc
               FROM spotify_track_meta
              WHERE spotify_track_id IN ({placeholders})""",
        track_ids,
    ).fetchall()
    by_id = {
        _normalize_spotify_track_id(str(row["spotify_track_id"])): (
            _normalize_track_equivalence_name(str(row["track_name"] or "")),
            str(row["isrc"] or "").strip().casefold(),
        )
        for row in rows
    }
    result: list[tuple[str, str, str]] = []
    for track_id in track_ids:
        normalized_id = _normalize_spotify_track_id(track_id)
        name, isrc = by_id.get(normalized_id, ("", ""))
        if not name and not isrc:
            cache[evidence.spotify_album_id] = None
            return None
        result.append((normalized_id, name, isrc))
    value = tuple(result)
    cache[evidence.spotify_album_id] = value
    return value


def _normalize_track_equivalence_name(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    changed = True
    while normalized and changed:
        changed = False
        for pattern in _TRACK_REMASTER_SUFFIXES:
            stripped = pattern.sub("", normalized).strip()
            if stripped != normalized:
                normalized = stripped
                changed = True
                break
    normalized = re.sub(r"\s+", " ", normalized)
    return "".join(character for character in normalized if character.isalnum())


def _tracks_equivalent(left: tuple[str, str, str], right: tuple[str, str, str]) -> bool:
    left_id, left_name, left_isrc = left
    right_id, right_name, right_isrc = right
    if left_id == right_id:
        return True
    if left_isrc and right_isrc and left_isrc == right_isrc:
        return True
    return bool(left_name and right_name and left_name == right_name)


def _ordered_track_lists_equivalent(
    left: tuple[tuple[str, str, str], ...],
    right: tuple[tuple[str, str, str], ...],
) -> bool:
    return len(left) == len(right) and all(
        _tracks_equivalent(left_track, right_track) for left_track, right_track in zip(left, right)
    )


def _ordered_track_subset(
    base: tuple[tuple[str, str, str], ...],
    expanded: tuple[tuple[str, str, str], ...],
) -> bool:
    if len(base) >= len(expanded):
        return False
    index = 0
    for track in expanded:
        if index < len(base) and _tracks_equivalent(base[index], track):
            index += 1
    return index == len(base)


def _release_year(value: str) -> int | None:
    match = re.match(r"^((?:19|20)\d{2})", value.strip())
    return int(match.group(1)) if match else None


def _equivalent_release_relation(
    conn: sqlite3.Connection,
    left: _ProjectReleaseEvidence,
    right: _ProjectReleaseEvidence,
    track_cache: dict[str, tuple[tuple[str, str, str], ...] | None],
) -> str | None:
    """Return one strong relation channel, or fail closed."""

    if _release_fingerprint(left) == _release_fingerprint(right):
        return "exact_release"
    if left.spotify_album_id == right.spotify_album_id:
        return None
    if _release_family_key(left) != _release_family_key(right):
        return None

    left_tracks = _release_track_evidence(conn, left, track_cache)
    right_tracks = _release_track_evidence(conn, right, track_cache)
    if left_tracks is None or right_tracks is None:
        return None
    left_tags = _release_relation_tags(left.spotify_album_name)
    right_tags = _release_relation_tags(right.spotify_album_name)

    if {left_tags, right_tags} == {frozenset(), frozenset({"remaster"})}:
        base, remaster = (left, right) if not left_tags else (right, left)
        base_tracks, remaster_tracks = (
            (left_tracks, right_tracks) if base is left else (right_tracks, left_tracks)
        )
        base_year = _release_year(base.release_date)
        remaster_year = _release_year(remaster.release_date)
        if (
            len(base_tracks) >= 5
            and base_year is not None
            and remaster_year is not None
            and remaster_year >= base_year
            and _ordered_track_lists_equivalent(base_tracks, remaster_tracks)
        ):
            return "remaster_equivalent"
        return None

    if {left_tags, right_tags} == {frozenset(), frozenset({"deluxe"})}:
        base, deluxe = (left, right) if not left_tags else (right, left)
        base_tracks, deluxe_tracks = (
            (left_tracks, right_tracks) if base is left else (right_tracks, left_tracks)
        )
        base_year = _release_year(base.release_date)
        deluxe_year = _release_year(deluxe.release_date)
        maximum_extra = max(10, len(base_tracks) // 2)
        if (
            len(base_tracks) >= 5
            and len(deluxe_tracks) - len(base_tracks) <= maximum_extra
            and base_year is not None
            and deluxe_year is not None
            and deluxe_year >= base_year
            and _ordered_track_subset(base_tracks, deluxe_tracks)
        ):
            return "deluxe_superset"
        return None

    if left_tags or right_tags:
        return None
    if (
        len(left_tracks) >= 3
        and left.release_date == right.release_date
        and _ordered_track_lists_equivalent(left_tracks, right_tracks)
    ):
        return "catalog_alias_equivalent"
    return None


def _ambiguous_evidence_projects(
    conn: sqlite3.Connection,
    evidence_by_project: dict[int, list[_ProjectReleaseEvidence]],
    track_cache: dict[str, tuple[tuple[str, str, str], ...] | None],
) -> set[int]:
    """Reject a local project whose provider identities do not form one family."""

    ambiguous: set[int] = set()
    for project_id, evidence_rows in evidence_by_project.items():
        if len(evidence_rows) < 2:
            continue
        if len({_release_family_key(item) for item in evidence_rows}) != 1:
            ambiguous.add(project_id)
            continue

        # Multiple provider links are safe only when all of them belong to one
        # connected strong-evidence component. This prevents one noisy same-name
        # catalog link from bridging two otherwise unrelated release families.
        connected = {0}
        while True:
            newly_connected = {
                index
                for index, candidate in enumerate(evidence_rows)
                if index not in connected
                and any(
                    _equivalent_release_relation(
                        conn,
                        evidence_rows[known_index],
                        candidate,
                        track_cache,
                    )
                    is not None
                    for known_index in connected
                )
            }
            if not newly_connected:
                break
            connected.update(newly_connected)
        if len(connected) != len(evidence_rows):
            ambiguous.add(project_id)
    return ambiguous


def _release_fingerprint(evidence: _ProjectReleaseEvidence) -> tuple[str, str, str, str, str]:
    track_hash = hashlib.sha256("\0".join(evidence.track_list).encode("utf-8")).hexdigest()
    return (
        evidence.spotify_album_id,
        normalize_album_release_name(evidence.spotify_album_name),
        evidence.release_date,
        normalize_album_release_name(evidence.album_artists),
        track_hash,
    )


def _candidate_key(spotify_album_ids: tuple[str, ...], album_ids: tuple[int, ...]) -> str:
    payload = f"spotify:{','.join(spotify_album_ids)}|albums:{','.join(map(str, album_ids))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _external_identities(
    edges: list[_EvidenceEdge],
    *,
    primary_spotify_album_id: str,
) -> tuple[AlbumProjectExternalIdentity, ...]:
    relation_by_id: dict[str, str] = {}
    for edge in edges:
        for evidence in (edge.left, edge.right):
            existing = relation_by_id.get(evidence.spotify_album_id)
            if (
                existing is None
                or _RELATION_PRIORITY[edge.relation_type] < _RELATION_PRIORITY[existing]
            ):
                relation_by_id[evidence.spotify_album_id] = edge.relation_type
    return tuple(
        AlbumProjectExternalIdentity(
            spotify_album_id=spotify_album_id,
            evidence_type=_EXTERNAL_EVIDENCE_TYPE[relation_type],
            confidence=_EXTERNAL_CONFIDENCE[relation_type],
            is_primary=spotify_album_id == primary_spotify_album_id,
        )
        for spotify_album_id, relation_type in sorted(relation_by_id.items())
    )


def _candidate_evidence_codes(relation_types: tuple[str, ...]) -> tuple[str, ...]:
    common = (
        "normalized_release_name_match",
        "album_artists_present",
        "complete_track_list_match",
        "local_track_in_complete_release",
    )
    relation_codes: list[str] = []
    if "exact_release" in relation_types:
        relation_codes.extend(("release_date_match", "spotify_album_id_match"))
    if "catalog_alias_equivalent" in relation_types:
        relation_codes.extend(
            ("release_date_match", "different_spotify_album_ids", "catalog_alias_equivalent")
        )
    if "remaster_equivalent" in relation_types:
        relation_codes.extend(
            ("different_spotify_album_ids", "ordered_track_equivalence", "remaster_equivalent")
        )
    if "deluxe_superset" in relation_types:
        relation_codes.extend(
            ("different_spotify_album_ids", "base_tracklist_ordered_subset", "deluxe_superset")
        )
    return tuple(dict.fromkeys((*common, *relation_codes)))


def _select_primary_evidence(
    evidence: list[_ProjectReleaseEvidence],
) -> _ProjectReleaseEvidence:
    return sorted(
        evidence,
        key=lambda item: (
            len(_release_relation_tags(item.spotify_album_name)),
            "remaster" in _release_relation_tags(item.spotify_album_name),
            "deluxe" in _release_relation_tags(item.spotify_album_name),
            normalize_album_release_name(item.project_name)
            != normalize_album_release_name(item.spotify_album_name),
            _release_year(item.release_date) or 9999,
            -item.local_track_count,
            -item.link_track_count,
            item.album_id,
        ),
    )[0]


def _select_project_artist_id(
    conn: sqlite3.Connection,
    evidence: list[_ProjectReleaseEvidence],
    primary: _ProjectReleaseEvidence,
) -> int:
    artist_ids = {item.artist_id for item in evidence}
    if len(artist_ids) == 1:
        return next(iter(artist_ids))

    normalized_album_artists = normalize_album_release_name(primary.album_artists)
    exact = conn.execute("SELECT artist_id, artist_name FROM artists ORDER BY artist_id").fetchall()
    exact_ids = [
        int(row["artist_id"])
        for row in exact
        if normalize_album_release_name(str(row["artist_name"] or "")) == normalized_album_artists
    ]
    if len(exact_ids) == 1:
        return exact_ids[0]
    return primary.artist_id


def _validate_plan_is_fresh(
    conn: sqlite3.Connection,
    plan: AlbumProjectAutoMergePlan,
) -> None:
    current = plan_album_project_auto_merges(conn)
    if current != plan:
        raise RuntimeError("stale Album Project auto-merge plan")
