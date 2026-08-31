"""Conservative L3 Album Project composition reconciliation.

L2 ``release`` groups answer whether source albums are editions of the same
release project (standard/deluxe/expanded bundles).  L3 ``composition`` groups
answer a different question: whether independently published album projects
represent the same work, for example an original studio album and its
Taylor's Version re-recording.

This module deliberately keeps those layers separate.  It plans from current
L2 Album Projects, requires an explicit controlled version suffix plus strong
track/composition overlap, and then links complete release child groups to one
composition parent.  Planning is side-effect free and all returned dataclasses
are JSON serialisable through ``to_dict``.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from backend.domains.metadata.artist_identity import get_artist_identity_map
from backend.domains.playback.album_projects import (
    _ensure_album_project_revision_schema,
    ensure_album_project_schema,
    get_album_project_revision,
    rebuild_album_projects,
)

ALBUM_COMPOSITION_POLICY_VERSION = "canonical_album_composition_v2_rerecord_only"

_COMPILATION_MARKERS = (
    "greatest hits",
    "best of",
    "anthology",
    "compilation",
    "精选",
    "精選",
)

_PACKAGING_MARKERS = (
    "deluxe",
    "expanded",
    "anniversary",
    "complete edition",
    "special edition",
    "bonus track version",
)

_RELATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "rerecord",
        re.compile(
            r"^(?:taylor(?:'|’)?s version|re[ -]?record(?:ed|ing)?(?: version)?)$",
            re.IGNORECASE,
        ),
    ),
    (
        "acoustic",
        re.compile(r"^(?:acoustic(?: collection| version)?|unplugged)$", re.IGNORECASE),
    ),
    (
        "live",
        re.compile(
            r"^(?:live(?: album| version| at .+| from .+| in .+)?|concert(?: version)?|tour version)$",
            re.IGNORECASE,
        ),
    ),
    (
        "remix",
        re.compile(
            r"^(?:remix(?:es| album| collection)?|.+ remix|.+ mix|mixes|radio edit)$",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class AlbumCompositionTitle:
    """Controlled album-title interpretation used only by the L3 planner."""

    base_name: str
    base_key: str
    relation_tag: str | None
    removed_suffixes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlbumCompositionProjectUnit:
    """One complete L2 release project participating as an indivisible node."""

    project_id: int
    canonical_name: str
    artist_id: int
    source_artist_id: int
    primary_album_id: int
    album_ids: tuple[int, ...]
    release_group_id: int | None
    track_key_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlbumCompositionCandidate:
    """One deterministic desired L3 composition component."""

    candidate_key: str
    canonical_name: str
    normalized_name: str
    artist_id: int
    primary_album_id: int
    relation_tags: tuple[str, ...]
    project_units: tuple[AlbumCompositionProjectUnit, ...]
    album_ids: tuple[int, ...]
    matched_track_keys: int
    minimum_pair_coverage: float
    evidence_codes: tuple[str, ...]
    existing_group_id: int | None
    action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlbumCompositionPlan:
    """Side-effect-free desired state plus safely owned stale auto groups."""

    policy_version: str
    candidates: tuple[AlbumCompositionCandidate, ...]
    archive_group_ids: tuple[int, ...]
    scanned_project_count: int
    skipped_reason_counts: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AlbumCompositionApplyReport:
    """Atomic reconciliation evidence."""

    candidate_count: int
    groups_created: int
    groups_updated: int
    groups_archived: int
    release_children_created: int
    unchanged_groups: int
    album_project_revision: int
    requires_downstream_refresh: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class _Project:
    project_id: int
    canonical_name: str
    artist_id: int
    source_artist_id: int
    primary_album_id: int
    album_ids: tuple[int, ...]
    project_type: str
    is_manual: bool
    release_group_id: int | None
    release_group_is_manual: bool
    title: AlbumCompositionTitle
    track_keys: frozenset[str]


def normalize_album_composition_title(value: str | None) -> AlbumCompositionTitle:
    """Strip only controlled packaging and L3 relation suffixes.

    A generic word such as ``Version`` or ``Live`` inside an ordinary title is
    never removed.  The recognised marker must occupy a complete trailing
    bracket or delimiter suffix.
    """

    display = unicodedata.normalize("NFKC", value or "").strip()
    display = re.sub(r"\s+", " ", display)
    removed: list[str] = []

    # Packaging does not create an L3 relation; it may wrap a relation title,
    # e.g. ``1989 (Taylor's Version) [Deluxe]``.
    while True:
        match = re.search(r"\s*[\[(]([^\[\]()]+)[\])]\s*$", display)
        if match is None or not _matches_marker(match.group(1), _PACKAGING_MARKERS):
            break
        removed.append(match.group(1).strip())
        display = display[: match.start()].strip()

    relation_tag: str | None = None
    suffix_match = re.search(r"\s*[\[(]([^\[\]()]+)[\])]\s*$", display)
    if suffix_match is not None:
        relation_tag = _relation_tag(suffix_match.group(1))
        if relation_tag:
            removed.append(suffix_match.group(1).strip())
            display = display[: suffix_match.start()].strip()
    if relation_tag is None:
        delimiter_match = re.search(r"\s+(?:-|:|–|—)\s*([^:–—-]+)\s*$", display)
        if delimiter_match is not None:
            relation_tag = _relation_tag(delimiter_match.group(1))
            if relation_tag:
                removed.append(delimiter_match.group(1).strip())
                display = display[: delimiter_match.start()].strip()

    base_name = display or unicodedata.normalize("NFKC", value or "").strip()
    return AlbumCompositionTitle(
        base_name=base_name,
        base_key=_normalise_key(base_name),
        relation_tag=relation_tag,
        removed_suffixes=tuple(removed),
    )


def plan_album_composition_merges(conn: sqlite3.Connection) -> AlbumCompositionPlan:
    """Plan L3 album composition groups without mutating SQLite state."""

    skipped: Counter[str] = Counter()
    projects = _load_projects(conn, skipped)
    families: dict[tuple[int, str], list[_Project]] = defaultdict(list)
    for project in projects:
        families[(project.artist_id, project.title.base_key)].append(project)

    auto_composition_groups = _load_auto_composition_groups(conn)
    manual_composition_albums = _load_manual_composition_albums(conn)
    desired_existing_ids: set[int] = set()
    candidates: list[AlbumCompositionCandidate] = []

    for (artist_id, base_key), family in sorted(families.items()):
        tagged = [item for item in family if item.title.relation_tag == "rerecord"]
        base = [item for item in family if item.title.relation_tag is None]
        skipped["non_rerecord_project_uses_song_attribution"] += sum(
            item.title.relation_tag not in {None, "rerecord"} for item in family
        )
        if not tagged:
            continue
        if len(base) != 1:
            skipped["missing_or_ambiguous_base_release"] += 1
            continue
        base_project = base[0]
        related: list[tuple[_Project, int, float]] = []
        for variant in sorted(tagged, key=lambda item: item.project_id):
            matched, coverage = _strong_overlap(base_project.track_keys, variant.track_keys)
            if matched:
                related.append((variant, matched, coverage))
            else:
                skipped["insufficient_composition_track_overlap"] += 1
        if not related:
            continue

        component = [base_project, *(item for item, _, _ in related)]
        album_ids = tuple(sorted({aid for item in component for aid in item.album_ids}))
        if any(item.is_manual or item.release_group_is_manual for item in component):
            skipped["manual_release_project_frozen"] += 1
            continue
        if set(album_ids).intersection(manual_composition_albums):
            skipped["manual_composition_group_frozen"] += 1
            continue

        existing = [
            group
            for group in auto_composition_groups
            if group["artist_id"] == artist_id
            and normalize_album_composition_title(group["canonical_name"]).base_key == base_key
        ]
        if len(existing) > 1:
            skipped["ambiguous_automatic_composition_group"] += 1
            continue
        existing_group = existing[0] if existing else None
        if existing_group and int(existing_group["manual_child_count"] or 0):
            skipped["manual_composition_topology_frozen"] += 1
            continue
        existing_id = int(existing_group["group_id"]) if existing_group else None
        if existing_id is not None:
            desired_existing_ids.add(existing_id)

        action = _candidate_action(
            conn,
            existing_id,
            component,
            album_ids,
            canonical_name=base_project.title.base_name,
            artist_id=artist_id,
            primary_album_id=base_project.primary_album_id,
        )
        matched_counts = [matched for _, matched, _ in related]
        coverages = [coverage for _, _, coverage in related]
        units = tuple(_public_unit(item) for item in sorted(component, key=lambda p: p.project_id))
        relation_tags = tuple(
            sorted({item.title.relation_tag for item, _, _ in related if item.title.relation_tag})
        )
        candidate_key = _candidate_key(artist_id, base_key, album_ids)
        candidates.append(
            AlbumCompositionCandidate(
                candidate_key=candidate_key,
                canonical_name=base_project.title.base_name,
                normalized_name=base_key,
                artist_id=artist_id,
                primary_album_id=base_project.primary_album_id,
                relation_tags=relation_tags,
                project_units=units,
                album_ids=album_ids,
                matched_track_keys=min(matched_counts),
                minimum_pair_coverage=round(min(coverages), 6),
                evidence_codes=(
                    "canonical_album_artist_match",
                    "controlled_version_suffix",
                    "composition_track_overlap",
                    "single_base_release",
                    "compilation_policy_frozen",
                ),
                existing_group_id=existing_id,
                action=action,
            )
        )

    # Only topology introduced by this planner is safely auto-owned: an
    # inferred composition group with at least one release child pointing to
    # it.  Legacy direct-only groups are left untouched and reported.
    archive_ids: list[int] = []
    for group in auto_composition_groups:
        group_id = int(group["group_id"])
        if group_id in desired_existing_ids:
            continue
        child_count = int(group["child_count"] or 0)
        if int(group["manual_child_count"] or 0):
            skipped["manual_composition_topology_frozen"] += 1
            continue
        if child_count:
            archive_ids.append(group_id)
        else:
            skipped["unowned_automatic_composition_group"] += 1

    return AlbumCompositionPlan(
        policy_version=ALBUM_COMPOSITION_POLICY_VERSION,
        candidates=tuple(sorted(candidates, key=lambda item: item.candidate_key)),
        archive_group_ids=tuple(sorted(archive_ids)),
        scanned_project_count=len(projects),
        skipped_reason_counts=tuple(sorted(skipped.items())),
    )


def apply_album_composition_plan(
    conn: sqlite3.Connection,
    plan: AlbumCompositionPlan,
    *,
    commit: bool = True,
    ensure_schema: bool = True,
) -> AlbumCompositionApplyReport:
    """Atomically reconcile a fresh L3 album composition plan."""

    if plan.policy_version != ALBUM_COMPOSITION_POLICY_VERSION:
        raise RuntimeError("unsupported Album composition policy version")
    if plan_album_composition_merges(conn) != plan:
        raise RuntimeError("stale Album composition plan")

    changed_candidates = [item for item in plan.candidates if item.action != "unchanged"]
    if not changed_candidates and not plan.archive_group_ids:
        return AlbumCompositionApplyReport(
            candidate_count=len(plan.candidates),
            groups_created=0,
            groups_updated=0,
            groups_archived=0,
            release_children_created=0,
            unchanged_groups=len(plan.candidates),
            album_project_revision=get_album_project_revision(conn),
            requires_downstream_refresh=False,
        )

    if ensure_schema:
        ensure_album_project_schema(conn)
        _ensure_album_project_revision_schema(conn)

    created = updated = archived = release_children_created = 0
    conn.execute("SAVEPOINT apply_album_composition_plan")
    try:
        for group_id in plan.archive_group_ids:
            row = conn.execute(
                "SELECT is_manual, scope FROM release_groups WHERE group_id=?",
                (group_id,),
            ).fetchone()
            if row is None or int(row["is_manual"] or 0) or row["scope"] != "composition":
                raise RuntimeError(f"composition archive ownership changed: {group_id}")
            conn.execute(
                "UPDATE release_groups SET parent_group_id=NULL WHERE parent_group_id=?",
                (group_id,),
            )
            conn.execute("DELETE FROM release_group_members WHERE group_id=?", (group_id,))
            conn.execute("DELETE FROM release_groups WHERE group_id=?", (group_id,))
            archived += 1

        for candidate in changed_candidates:
            child_group_ids: list[int] = []
            for unit in candidate.project_units:
                child_group_id, was_created = _ensure_release_child(conn, unit)
                child_group_ids.append(child_group_id)
                release_children_created += int(was_created)

            group_id = candidate.existing_group_id
            if group_id is None:
                cursor = conn.execute(
                    """INSERT INTO release_groups(
                           canonical_name, artist_id, primary_album_id,
                           scope, parent_group_id, is_manual
                       ) VALUES (?, ?, ?, 'composition', NULL, 0)""",
                    (
                        candidate.canonical_name,
                        candidate.artist_id,
                        candidate.primary_album_id,
                    ),
                )
                group_id = int(cursor.lastrowid)
                created += 1
            else:
                row = conn.execute(
                    "SELECT is_manual, scope FROM release_groups WHERE group_id=?",
                    (group_id,),
                ).fetchone()
                if row is None or int(row["is_manual"] or 0) or row["scope"] != "composition":
                    raise RuntimeError(f"composition group ownership changed: {group_id}")
                conn.execute(
                    """UPDATE release_groups
                          SET canonical_name=?, artist_id=?, primary_album_id=?
                        WHERE group_id=?""",
                    (
                        candidate.canonical_name,
                        candidate.artist_id,
                        candidate.primary_album_id,
                        group_id,
                    ),
                )
                updated += 1

            placeholders = ",".join("?" for _ in child_group_ids)
            conn.execute(
                f"""UPDATE release_groups
                       SET parent_group_id=NULL
                     WHERE parent_group_id=?
                       AND group_id NOT IN ({placeholders})""",
                (group_id, *child_group_ids),
            )
            conn.executemany(
                "UPDATE release_groups SET parent_group_id=? WHERE group_id=?",
                ((group_id, child_id) for child_id in child_group_ids),
            )
            conn.execute("DELETE FROM release_group_members WHERE group_id=?", (group_id,))
            conn.executemany(
                "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
                ((group_id, album_id) for album_id in candidate.album_ids),
            )

        rebuild_album_projects(conn, commit=False, ensure_schema=False)
        for candidate in plan.candidates:
            conn.execute(
                """UPDATE album_projects
                      SET normalized_name=?,
                          album_artist_key=COALESCE(
                              (SELECT lower(trim(artist_name)) FROM artists
                                WHERE artist_id=album_projects.artist_id),
                              album_artist_key
                          ),
                          identity_policy_version=?
                    WHERE canonical_name=? AND artist_id=? AND scope='composition'
                      AND is_manual=0""",
                (
                    candidate.normalized_name,
                    ALBUM_COMPOSITION_POLICY_VERSION,
                    candidate.canonical_name,
                    candidate.artist_id,
                ),
            )
        conn.execute("RELEASE SAVEPOINT apply_album_composition_plan")
        if commit:
            conn.commit()
    except Exception:
        try:
            conn.execute("ROLLBACK TO SAVEPOINT apply_album_composition_plan")
            conn.execute("RELEASE SAVEPOINT apply_album_composition_plan")
        except sqlite3.OperationalError:
            conn.rollback()
        raise

    return AlbumCompositionApplyReport(
        candidate_count=len(plan.candidates),
        groups_created=created,
        groups_updated=updated,
        groups_archived=archived,
        release_children_created=release_children_created,
        unchanged_groups=len(plan.candidates) - len(changed_candidates),
        album_project_revision=get_album_project_revision(conn),
        requires_downstream_refresh=True,
    )


def _load_projects(conn: sqlite3.Connection, skipped: Counter[str]) -> list[_Project]:
    rows = conn.execute(
        """SELECT project_id, canonical_name, artist_id, primary_album_id,
                  project_type, is_manual
             FROM album_projects
            WHERE scope='release' AND project_type='album'
            ORDER BY project_id"""
    ).fetchall()
    track_keys_by_project = _load_project_track_keys(conn)
    artist_identity = get_artist_identity_map(conn)
    result: list[_Project] = []
    for row in rows:
        project_id = int(row["project_id"])
        album_ids = tuple(
            int(item[0])
            for item in conn.execute(
                "SELECT album_id FROM album_project_albums WHERE project_id=? ORDER BY album_id",
                (project_id,),
            ).fetchall()
        )
        if not album_ids:
            skipped["project_without_albums"] += 1
            continue
        name = str(row["canonical_name"] or "")
        if _looks_like_compilation(conn, project_id, name):
            skipped["compilation_policy_frozen"] += 1
            continue
        release_groups = _release_groups_for_exact_album_set(conn, album_ids)
        if len(release_groups) > 1:
            skipped["ambiguous_release_group_ownership"] += 1
            continue
        release_group = release_groups[0] if release_groups else None
        source_artist_id = int(row["artist_id"])
        resolution = artist_identity.get(source_artist_id)
        canonical_artist_id = (
            int(resolution.canonical_artist_id) if resolution is not None else source_artist_id
        )
        result.append(
            _Project(
                project_id=project_id,
                canonical_name=name,
                artist_id=canonical_artist_id,
                source_artist_id=source_artist_id,
                primary_album_id=int(row["primary_album_id"]),
                album_ids=album_ids,
                project_type=str(row["project_type"]),
                is_manual=bool(row["is_manual"]),
                release_group_id=(int(release_group["group_id"]) if release_group else None),
                release_group_is_manual=(
                    bool(release_group["is_manual"]) if release_group else False
                ),
                title=normalize_album_composition_title(name),
                track_keys=frozenset(track_keys_by_project.get(project_id, set())),
            )
        )
    return result


def _load_project_track_keys(conn: sqlite3.Connection) -> dict[int, set[str]]:
    from backend.domains.playback.song_work_keys import apply_l3_song_work_keys

    rows = conn.execute(
        "SELECT DISTINCT project_id, track_id FROM album_project_tracks ORDER BY project_id, track_id"
    ).fetchall()
    frame = pd.DataFrame.from_records(
        [dict(row) for row in rows], columns=["project_id", "track_id"]
    )
    if frame.empty:
        return {}
    keyed = apply_l3_song_work_keys(frame, conn)
    result: dict[int, set[str]] = defaultdict(set)
    for row in keyed.itertuples(index=False):
        result[int(row.project_id)].add(str(row.canonical_song_key))
    return result


def _release_groups_for_exact_album_set(
    conn: sqlite3.Connection, album_ids: tuple[int, ...]
) -> list[sqlite3.Row]:
    desired = set(album_ids)
    if not desired:
        return []
    placeholders = ",".join("?" for _ in desired)
    rows = conn.execute(
        f"""SELECT DISTINCT groups.group_id, groups.is_manual
              FROM release_groups groups
              JOIN release_group_members members ON members.group_id=groups.group_id
             WHERE groups.scope='release' AND members.album_id IN ({placeholders})
             ORDER BY groups.group_id""",
        tuple(sorted(desired)),
    ).fetchall()
    result: list[sqlite3.Row] = []
    for row in rows:
        members = {
            int(item[0])
            for item in conn.execute(
                "SELECT album_id FROM release_group_members WHERE group_id=?",
                (int(row["group_id"]),),
            ).fetchall()
        }
        if members == desired:
            result.append(row)
    return result


def _strong_overlap(left: frozenset[str], right: frozenset[str]) -> tuple[int, float]:
    smaller = min(len(left), len(right))
    if smaller < 2:
        return 0, 0.0
    matched = len(left.intersection(right))
    coverage = matched / smaller
    required = min(5, max(2, math.ceil(smaller * 0.6)))
    if matched < required or coverage < 0.6:
        return 0, coverage
    return matched, coverage


def _candidate_action(
    conn: sqlite3.Connection,
    existing_group_id: int | None,
    component: list[_Project],
    album_ids: tuple[int, ...],
    *,
    canonical_name: str,
    artist_id: int,
    primary_album_id: int,
) -> str:
    if existing_group_id is None:
        return "create"
    metadata = conn.execute(
        """SELECT canonical_name, artist_id, primary_album_id
             FROM release_groups WHERE group_id=?""",
        (existing_group_id,),
    ).fetchone()
    if metadata is None or (
        str(metadata["canonical_name"]) != canonical_name
        or int(metadata["artist_id"]) != artist_id
        or int(metadata["primary_album_id"]) != primary_album_id
    ):
        return "update"
    project_identity = conn.execute(
        """SELECT normalized_name, identity_policy_version
             FROM album_projects
            WHERE canonical_name=? AND artist_id=? AND scope='composition'
              AND is_manual=0""",
        (canonical_name, artist_id),
    ).fetchone()
    if project_identity is None or (
        str(project_identity["normalized_name"] or "") != _normalise_key(canonical_name)
        or str(project_identity["identity_policy_version"] or "")
        != ALBUM_COMPOSITION_POLICY_VERSION
    ):
        return "update"
    current_albums = {
        int(row[0])
        for row in conn.execute(
            "SELECT album_id FROM release_group_members WHERE group_id=?",
            (existing_group_id,),
        ).fetchall()
    }
    if current_albums != set(album_ids):
        return "update"
    for project in component:
        if project.release_group_id is None:
            return "update"
        parent = conn.execute(
            "SELECT parent_group_id FROM release_groups WHERE group_id=?",
            (project.release_group_id,),
        ).fetchone()
        if parent is None or parent[0] != existing_group_id:
            return "update"
    return "unchanged"


def _ensure_release_child(
    conn: sqlite3.Connection,
    unit: AlbumCompositionProjectUnit,
) -> tuple[int, bool]:
    if unit.release_group_id is not None:
        row = conn.execute(
            "SELECT scope, is_manual FROM release_groups WHERE group_id=?",
            (unit.release_group_id,),
        ).fetchone()
        if row is None or row["scope"] != "release" or int(row["is_manual"] or 0):
            raise RuntimeError(f"release child ownership changed: {unit.release_group_id}")
        return unit.release_group_id, False

    existing = conn.execute(
        """SELECT group_id, is_manual FROM release_groups
            WHERE canonical_name=? AND artist_id=? AND scope='release'""",
        (unit.canonical_name, unit.source_artist_id),
    ).fetchone()
    if existing is not None:
        group_id = int(existing["group_id"])
        members = {
            int(row[0])
            for row in conn.execute(
                "SELECT album_id FROM release_group_members WHERE group_id=?", (group_id,)
            ).fetchall()
        }
        if int(existing["is_manual"] or 0) or members != set(unit.album_ids):
            raise RuntimeError("release child semantic key collision")
        return group_id, False

    cursor = conn.execute(
        """INSERT INTO release_groups(
               canonical_name, artist_id, primary_album_id, scope, is_manual
           ) VALUES (?, ?, ?, 'release', 0)""",
        (unit.canonical_name, unit.source_artist_id, unit.primary_album_id),
    )
    group_id = int(cursor.lastrowid)
    conn.executemany(
        "INSERT INTO release_group_members(group_id, album_id) VALUES (?, ?)",
        ((group_id, album_id) for album_id in unit.album_ids),
    )
    return group_id, True


def _load_auto_composition_groups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    artist_identity = get_artist_identity_map(conn)
    return [
        {
            "group_id": int(row["group_id"]),
            "canonical_name": str(row["canonical_name"]),
            "artist_id": (
                int(artist_identity[int(row["artist_id"])].canonical_artist_id)
                if int(row["artist_id"]) in artist_identity
                else int(row["artist_id"])
            ),
            "child_count": int(row["child_count"]),
            "manual_child_count": int(row["manual_child_count"]),
        }
        for row in conn.execute(
            """SELECT groups.group_id, groups.canonical_name, groups.artist_id,
                      COUNT(children.group_id) AS child_count,
                      SUM(CASE WHEN children.is_manual=1 THEN 1 ELSE 0 END)
                          AS manual_child_count
                 FROM release_groups groups
                 LEFT JOIN release_groups children
                   ON children.parent_group_id=groups.group_id
                WHERE groups.scope='composition' AND groups.is_manual=0
                GROUP BY groups.group_id, groups.canonical_name, groups.artist_id
                ORDER BY groups.group_id"""
        ).fetchall()
    ]


def _load_manual_composition_albums(conn: sqlite3.Connection) -> set[int]:
    return {
        int(row[0])
        for row in conn.execute(
            """SELECT members.album_id
                 FROM release_group_members members
                 JOIN release_groups groups ON groups.group_id=members.group_id
                WHERE groups.scope='composition' AND groups.is_manual=1"""
        ).fetchall()
    }


def _looks_like_compilation(conn: sqlite3.Connection, project_id: int, name: str) -> bool:
    if any(marker in _normalise_key(name) for marker in _COMPILATION_MARKERS):
        return True
    row = conn.execute(
        """SELECT 1
             FROM album_project_albums project_album
             JOIN album_spotify_links links ON links.album_id=project_album.album_id
             JOIN spotify_album_meta meta ON meta.spotify_album_id=links.spotify_album_id
            WHERE project_album.project_id=? AND lower(meta.album_type)='compilation'
            LIMIT 1""",
        (project_id,),
    ).fetchone()
    return row is not None


def _public_unit(project: _Project) -> AlbumCompositionProjectUnit:
    return AlbumCompositionProjectUnit(
        project_id=project.project_id,
        canonical_name=project.canonical_name,
        artist_id=project.artist_id,
        source_artist_id=project.source_artist_id,
        primary_album_id=project.primary_album_id,
        album_ids=project.album_ids,
        release_group_id=project.release_group_id,
        track_key_count=len(project.track_keys),
    )


def _candidate_key(artist_id: int, base_key: str, album_ids: tuple[int, ...]) -> str:
    payload = f"artist:{artist_id}|title:{base_key}|albums:{','.join(map(str, album_ids))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _relation_tag(value: str) -> str | None:
    normalized = unicodedata.normalize("NFKC", value).strip()
    for tag, pattern in _RELATION_PATTERNS:
        if pattern.fullmatch(normalized):
            return tag
    return None


def _matches_marker(value: str, markers: tuple[str, ...]) -> bool:
    normalized = _normalise_key(value)
    return any(marker == normalized for marker in markers)


def _normalise_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = normalized.translate({ord("’"): "'", ord("–"): "-", ord("—"): "-"})
    return re.sub(r"\s+", " ", normalized)
