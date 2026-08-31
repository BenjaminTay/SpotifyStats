"""Machine-first reconciliation of L3 composition groups.

L2 recording groups are treated as indivisible units.  The planner relates
those units (plus ungrouped L1 identities) by a conservative composition title
and artist rule, then the applier materialises composition membership and the
recording -> composition parent chain in one savepoint.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from backend.domains.metadata.track_composition_identity import (
    COMPOSITION_TITLE_IDENTITY_POLICY_VERSION,
    normalize_composition_track_title,
)

L3_AUTO_MERGE_POLICY_VERSION = (
    f"canonical_artist_composition_v1:{COMPOSITION_TITLE_IDENTITY_POLICY_VERSION}"
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


@dataclass(frozen=True)
class _CompositionUnit:
    unit_id: int
    recording_group_id: int | None
    member_l1_ids: tuple[int, ...]
    primary_l1_id: int
    primary_track_id: int
    canonical_name: str
    artist_ids: tuple[int, ...]
    base_title: str
    relation_tags: tuple[str, ...]
    recording_variant_key: str
    blocker_tags: tuple[str, ...]
    source_context_tags: tuple[str, ...]
    play_count: int
    isrc_durations: tuple[tuple[str, int | None], ...]


class _UnitSets:
    def __init__(
        self,
        units: dict[int, _CompositionUnit],
        cannot_link: set[tuple[int, int]],
    ) -> None:
        self.parent = {unit_id: unit_id for unit_id in units}
        self.members = {unit_id: {unit_id} for unit_id in units}
        self.artist_intersection = {
            unit_id: set(unit.artist_ids) for unit_id, unit in units.items()
        }
        self.cannot_link = cannot_link

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int, *, require_shared_artist: bool) -> bool:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return True
        left_members = self.members[left_root]
        right_members = self.members[right_root]
        if any(
            (min(a, b), max(a, b)) in self.cannot_link for a in left_members for b in right_members
        ):
            return False
        shared_artists = self.artist_intersection[left_root] & self.artist_intersection[right_root]
        if require_shared_artist and not shared_artists:
            return False
        if (len(left_members), -left_root) < (len(right_members), -right_root):
            left_root, right_root = right_root, left_root
            left_members, right_members = right_members, left_members
        self.parent[right_root] = left_root
        left_members.update(right_members)
        del self.members[right_root]
        self.artist_intersection[left_root] = shared_artists
        del self.artist_intersection[right_root]
        return True


def _canonical_artist_signatures(
    conn: sqlite3.Connection, representative_track_ids: list[int]
) -> dict[int, tuple[int, ...]]:
    from backend.domains.metadata.track_credits import get_effective_track_credits

    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in get_effective_track_credits(conn, representative_track_ids):
        grouped[int(row["track_id"])].append(row)
    result: dict[int, tuple[int, ...]] = {}
    for track_id, rows in grouped.items():
        primary = sorted(
            {int(row["artist_id"]) for row in rows if str(row.get("role")) == "primary"}
        )
        if not primary:
            primary = sorted({int(row["artist_id"]) for row in rows})
        if primary:
            result[track_id] = tuple(primary)
    return result


def _load_l1_rows(conn: sqlite3.Connection) -> dict[int, dict[str, Any]]:
    rows = conn.execute(
        """SELECT identities.l1_id, identities.representative_track_id,
                  tracks.track_name,
                  COALESCE(SUM(CASE WHEN links.evidence_type='play_at_time'
                                    THEN links.observed_plays ELSE 0 END), 0) AS play_count
             FROM track_l1_identities identities
             JOIN tracks ON tracks.track_id=identities.representative_track_id
             LEFT JOIN track_l1_source_links links ON links.l1_id=identities.l1_id
            WHERE identities.identity_status='active'
            GROUP BY identities.l1_id
            ORDER BY identities.l1_id"""
    ).fetchall()
    track_ids = [int(row["representative_track_id"]) for row in rows]
    artists = _canonical_artist_signatures(conn, track_ids)
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        track_id = int(row["representative_track_id"])
        if track_id not in artists:
            continue
        result[int(row["l1_id"])] = {
            "l1_id": int(row["l1_id"]),
            "representative_track_id": track_id,
            "track_name": str(row["track_name"]),
            "artist_ids": artists[track_id],
            "play_count": int(row["play_count"] or 0),
        }
    return result


def _load_noncanonical_l1_ids(conn: sqlite3.Connection) -> set[int]:
    if not _table_exists(conn, "spotify_track_owners"):
        return set()
    return {
        int(row["l1_id"])
        for row in conn.execute(
            """SELECT identities.l1_id
                 FROM track_l1_identities identities
                WHERE NOT EXISTS (
                          SELECT 1 FROM spotify_track_owners self_owner
                           WHERE self_owner.track_id=identities.l1_id
                      )
                  AND (
                      EXISTS (
                          SELECT 1
                            FROM tracks source
                            JOIN spotify_track_owners raw_owner
                              ON raw_owner.spotify_track_id=source.spotify_track_id
                           WHERE source.track_id=identities.l1_id
                             AND raw_owner.track_id!=identities.l1_id
                      )
                      OR EXISTS (
                          SELECT 1 FROM track_l1_source_links alias_link
                           WHERE alias_link.track_id=identities.l1_id
                             AND alias_link.l1_id!=identities.l1_id
                      )
                  )"""
        ).fetchall()
    }


def _load_l1_metadata(
    conn: sqlite3.Connection,
) -> dict[int, tuple[tuple[str, int | None], ...]]:
    if not (
        _table_exists(conn, "track_l1_external_ids") and _table_exists(conn, "spotify_track_meta")
    ):
        return {}
    grouped: dict[int, list[tuple[str, int | None]]] = defaultdict(list)
    for row in conn.execute(
        """SELECT external.l1_id, UPPER(TRIM(meta.isrc)) AS isrc, meta.duration_ms
             FROM track_l1_external_ids external
             JOIN spotify_track_meta meta
               ON external.provider='spotify'
              AND meta.spotify_track_id=external.external_track_id
            WHERE NULLIF(TRIM(meta.isrc), '') IS NOT NULL
            ORDER BY external.l1_id, isrc, meta.duration_ms"""
    ).fetchall():
        value = (str(row["isrc"]), int(row["duration_ms"]) if row["duration_ms"] else None)
        if value not in grouped[int(row["l1_id"])]:
            grouped[int(row["l1_id"])].append(value)
    return {l1_id: tuple(values) for l1_id, values in grouped.items()}


def _recording_groups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT groups.group_id, groups.canonical_name, groups.primary_l1_id,
                  groups.primary_track_id, groups.parent_group_id, members.l1_id
             FROM track_groups groups
             JOIN track_group_l1_members members ON members.group_id=groups.group_id
            WHERE groups.scope='recording' AND groups.group_status='active'
            ORDER BY groups.group_id, members.l1_id"""
    ).fetchall()
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        group_id = int(row["group_id"])
        item = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "canonical_name": str(row["canonical_name"]),
                "primary_l1_id": int(row["primary_l1_id"]),
                "primary_track_id": int(row["primary_track_id"]),
                "parent_group_id": (
                    int(row["parent_group_id"]) if row["parent_group_id"] is not None else None
                ),
                "member_l1_ids": [],
            },
        )
        item["member_l1_ids"].append(int(row["l1_id"]))
    return list(grouped.values())


def _composition_groups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT groups.group_id, groups.canonical_name, groups.primary_l1_id,
                  groups.primary_track_id, groups.is_manual,
                  groups.automatic_artist_id, groups.automatic_title_key,
                  groups.automatic_version_tag, groups.identity_policy_version,
                  members.l1_id
             FROM track_groups groups
             JOIN track_group_l1_members members ON members.group_id=groups.group_id
            WHERE groups.scope='composition' AND groups.group_status='active'
            ORDER BY groups.group_id, members.l1_id"""
    ).fetchall()
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
        group_id = int(row["group_id"])
        item = grouped.setdefault(
            group_id,
            {
                "group_id": group_id,
                "canonical_name": str(row["canonical_name"]),
                "primary_l1_id": int(row["primary_l1_id"]),
                "primary_track_id": int(row["primary_track_id"]),
                "is_manual": bool(row["is_manual"]),
                "automatic_artist_id": (
                    int(row["automatic_artist_id"])
                    if row["automatic_artist_id"] is not None
                    else None
                ),
                "automatic_title_key": row["automatic_title_key"],
                "automatic_version_tag": row["automatic_version_tag"],
                "identity_policy_version": row["identity_policy_version"],
                "member_l1_ids": [],
            },
        )
        item["member_l1_ids"].append(int(row["l1_id"]))
    return list(grouped.values())


def _load_units(
    conn: sqlite3.Connection,
) -> tuple[dict[int, _CompositionUnit], list[dict[str, Any]]]:
    l1_rows = _load_l1_rows(conn)
    for l1_id in _load_noncanonical_l1_ids(conn):
        l1_rows.pop(l1_id, None)
    metadata = _load_l1_metadata(conn)
    recording_groups = _recording_groups(conn)
    grouped_l1_ids = {int(l1_id) for group in recording_groups for l1_id in group["member_l1_ids"]}
    units: dict[int, _CompositionUnit] = {}

    def add_unit(group: dict[str, Any] | None, member_l1_ids: list[int]) -> None:
        available = [l1_id for l1_id in member_l1_ids if l1_id in l1_rows]
        if not available:
            return
        primary_l1_id = int(group["primary_l1_id"]) if group else available[0]
        if primary_l1_id not in l1_rows:
            primary_l1_id = available[0]
        primary = l1_rows[primary_l1_id]
        identity = normalize_composition_track_title(str(primary["track_name"]))
        unit_id = min(available)
        units[unit_id] = _CompositionUnit(
            unit_id=unit_id,
            recording_group_id=int(group["group_id"]) if group else None,
            member_l1_ids=tuple(sorted(available)),
            primary_l1_id=primary_l1_id,
            primary_track_id=int(primary["representative_track_id"]),
            canonical_name=str(primary["track_name"]),
            artist_ids=tuple(primary["artist_ids"]),
            base_title=identity.base_title,
            relation_tags=identity.relation_tags,
            recording_variant_key=identity.recording_variant_key,
            blocker_tags=identity.blocker_tags,
            source_context_tags=identity.source_context_tags,
            play_count=sum(int(l1_rows[l1_id]["play_count"]) for l1_id in available),
            isrc_durations=tuple(
                sorted(
                    {value for l1_id in available for value in metadata.get(l1_id, ())},
                    key=lambda value: (value[0], value[1] or 0),
                )
            ),
        )

    for group in recording_groups:
        add_unit(group, [int(value) for value in group["member_l1_ids"]])
    for l1_id in sorted(set(l1_rows) - grouped_l1_ids):
        add_unit(None, [l1_id])
    return units, recording_groups


def _load_overrides(conn: sqlite3.Connection) -> tuple[set[tuple[int, int]], list[tuple[int, int]]]:
    force_separate: set[tuple[int, int]] = set()
    force_merge: list[tuple[int, int]] = []
    if not _table_exists(conn, "track_merge_overrides"):
        return force_separate, force_merge
    for row in conn.execute(
        """SELECT left_l1_id, right_l1_id, action
             FROM track_merge_overrides WHERE scope='composition'
             ORDER BY MIN(left_l1_id, right_l1_id), MAX(left_l1_id, right_l1_id)"""
    ).fetchall():
        left = int(row["left_l1_id"])
        right = int(row["right_l1_id"])
        pair = (min(left, right), max(left, right))
        if str(row["action"]) == "force_separate":
            force_separate.add(pair)
        else:
            force_merge.append(pair)
    return force_separate, force_merge


def _unit_by_l1(units: dict[int, _CompositionUnit]) -> dict[int, int]:
    return {l1_id: unit.unit_id for unit in units.values() for l1_id in unit.member_l1_ids}


def _unit_pair(l1_pair: tuple[int, int], unit_by_l1: dict[int, int]) -> tuple[int, int] | None:
    left = unit_by_l1.get(l1_pair[0])
    right = unit_by_l1.get(l1_pair[1])
    if left is None or right is None or left == right:
        return None
    return min(left, right), max(left, right)


def _pair_warnings(left: _CompositionUnit, right: _CompositionUnit) -> list[str]:
    warnings: list[str] = []
    left_isrcs = {value[0] for value in left.isrc_durations}
    right_isrcs = {value[0] for value in right.isrc_durations}
    if left_isrcs and right_isrcs and left_isrcs.isdisjoint(right_isrcs):
        warnings.append("disjoint_isrc")
    left_durations = [value[1] for value in left.isrc_durations if value[1]]
    right_durations = [value[1] for value in right.isrc_durations if value[1]]
    if (
        left_durations
        and right_durations
        and min(
            abs(left_duration - right_duration)
            for left_duration in left_durations
            for right_duration in right_durations
        )
        >= 10_000
    ):
        warnings.append("strong_duration_conflict")
    if left.source_context_tags or right.source_context_tags:
        warnings.append("source_context_present")
    return warnings


def _choose_primary_unit(
    component: set[int], units: dict[int, _CompositionUnit]
) -> _CompositionUnit:
    return min(
        (units[unit_id] for unit_id in component),
        key=lambda unit: (
            bool(unit.relation_tags),
            -unit.play_count,
            unit.primary_l1_id,
        ),
    )


def _state_digest(
    units: dict[int, _CompositionUnit],
    recording_groups: list[dict[str, Any]],
    composition_groups: list[dict[str, Any]],
    force_separate: set[tuple[int, int]],
    force_merge: list[tuple[int, int]],
) -> str:
    payload = {
        "units": [vars(unit) for unit in units.values()],
        "recording_groups": recording_groups,
        "composition_groups": composition_groups,
        "force_separate": sorted(force_separate),
        "force_merge": sorted(force_merge),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _assign_targets(desired: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
    used: set[int] = set()
    for item in desired:
        members = set(item["member_l1_ids"])
        candidates = []
        for group in groups:
            overlap = members & set(group["member_l1_ids"])
            if not overlap or int(group["group_id"]) in used:
                continue
            candidates.append(
                (
                    -int(bool(group["is_manual"])),
                    -int(group["primary_l1_id"] in members),
                    -len(overlap),
                    int(group["group_id"]),
                    group,
                )
            )
        target = min(candidates)[-1] if candidates else None
        item["target_group_id"] = int(target["group_id"]) if target else None
        item["target_is_manual"] = bool(target["is_manual"]) if target else False
        if target:
            used.add(int(target["group_id"]))
            if target["is_manual"] and int(target["primary_l1_id"]) in members:
                item["primary_l1_id"] = int(target["primary_l1_id"])
                item["primary_track_id"] = int(target["primary_track_id"])
                item["canonical_name"] = str(target["canonical_name"])
        expected_identity = bool(
            target
            and (
                bool(target["is_manual"])
                or (
                    target["automatic_artist_id"] == item["automatic_artist_id"]
                    and target["automatic_title_key"] == item["base_title"]
                    and (target["automatic_version_tag"] or "") == ""
                    and target["identity_policy_version"] == L3_AUTO_MERGE_POLICY_VERSION
                )
            )
        )
        expected_parents = {
            int(group_id): int(target["group_id"]) if target else None
            for group_id in item["recording_group_ids"]
        }
        current_parents = {
            int(group["group_id"]): group["parent_group_id"] for group in item["recording_groups"]
        }
        item["action"] = (
            "unchanged"
            if target
            and set(target["member_l1_ids"]) == members
            and expected_identity
            and current_parents == expected_parents
            else "update"
            if target
            else "create"
        )


def build_l3_track_merge_plan(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build a complete read-only L3 reconciliation plan over L2 units."""

    units, recording_groups = _load_units(conn)
    composition_groups = _composition_groups(conn)
    unit_by_l1 = _unit_by_l1(units)
    explicit_separate, explicit_merge = _load_overrides(conn)
    unit_separate = {
        pair
        for l1_pair in explicit_separate
        if (pair := _unit_pair(l1_pair, unit_by_l1)) is not None
    }
    dsu = _UnitSets(units, set(unit_separate))
    accepted_edges: list[dict[str, Any]] = []
    blocked_edges: list[dict[str, Any]] = []
    warning_edges: list[dict[str, Any]] = []
    decided: set[tuple[int, int]] = set()

    def add_edge(
        left: int,
        right: int,
        evidence_type: str,
        confidence: float,
        *,
        require_shared_artist: bool,
    ) -> None:
        pair = (min(left, right), max(left, right))
        if pair in decided:
            return
        decided.add(pair)
        if dsu.union(left, right, require_shared_artist=require_shared_artist):
            accepted_edges.append(
                {
                    "left_l1_id": units[left].primary_l1_id,
                    "right_l1_id": units[right].primary_l1_id,
                    "left_unit_id": left,
                    "right_unit_id": right,
                    "evidence_type": evidence_type,
                    "confidence": confidence,
                    "relation_tags": sorted(
                        set(units[left].relation_tags) | set(units[right].relation_tags)
                    ),
                }
            )
            for warning in _pair_warnings(units[left], units[right]):
                warning_edges.append(
                    {
                        "left_l1_id": units[left].primary_l1_id,
                        "right_l1_id": units[right].primary_l1_id,
                        "warning": warning,
                    }
                )
        else:
            blocked_edges.append(
                {
                    "left_l1_id": units[left].primary_l1_id,
                    "right_l1_id": units[right].primary_l1_id,
                    "left_unit_id": left,
                    "right_unit_id": right,
                    "evidence_type": evidence_type,
                    "reason": "force_separate"
                    if pair in dsu.cannot_link
                    else "component_artist_intersection_empty",
                    "status": "rejected",
                }
            )

    for l1_pair in sorted(explicit_separate):
        pair = _unit_pair(l1_pair, unit_by_l1)
        if pair is None:
            continue
        decided.add(pair)
        blocked_edges.append(
            {
                "left_l1_id": units[pair[0]].primary_l1_id,
                "right_l1_id": units[pair[1]].primary_l1_id,
                "left_unit_id": pair[0],
                "right_unit_id": pair[1],
                "evidence_type": "force_separate",
                "reason": "force_separate",
                "status": "rejected",
            }
        )

    for l1_pair in sorted(explicit_merge):
        pair = _unit_pair(l1_pair, unit_by_l1)
        if pair is not None and pair not in decided:
            add_edge(*pair, "force_merge", 1.0, require_shared_artist=False)

    manual_component_seeds: set[int] = set()
    for group in composition_groups:
        if not group["is_manual"]:
            continue
        group_units = sorted(
            {unit_by_l1[l1_id] for l1_id in group["member_l1_ids"] if l1_id in unit_by_l1}
        )
        if not group_units:
            continue
        manual_component_seeds.update(group_units)
        anchor = group_units[0]
        for member in group_units[1:]:
            pair = (min(anchor, member), max(anchor, member))
            if pair not in decided:
                add_edge(*pair, "existing_manual_group", 1.0, require_shared_artist=False)

    by_base: dict[str, list[int]] = defaultdict(list)
    for unit in units.values():
        if unit.base_title:
            by_base[unit.base_title].append(unit.unit_id)
    # Install every fail-closed relation before connecting any automatic edge.
    # Otherwise a blocked unit could enter a component transitively through an
    # earlier pair in combinations() order.
    for same_title_units in by_base.values():
        for left, right in itertools.combinations(sorted(same_title_units), 2):
            pair = (left, right)
            if pair in decided:
                continue
            left_unit = units[left]
            right_unit = units[right]
            blockers = sorted(set(left_unit.blocker_tags) | set(right_unit.blocker_tags))
            if blockers:
                decided.add(pair)
                dsu.cannot_link.add(pair)
                blocked_edges.append(
                    {
                        "left_l1_id": left_unit.primary_l1_id,
                        "right_l1_id": right_unit.primary_l1_id,
                        "left_unit_id": left,
                        "right_unit_id": right,
                        "evidence_type": "canonical_artist_composition_title",
                        "reason": "blocked_composition_relation",
                        "blocker_tags": blockers,
                        "status": "rejected",
                    }
                )
    for same_title_units in by_base.values():
        for left, right in itertools.combinations(sorted(same_title_units), 2):
            pair = (left, right)
            if pair in decided:
                continue
            left_unit = units[left]
            right_unit = units[right]
            left_artists = set(left_unit.artist_ids)
            right_artists = set(right_unit.artist_ids)
            if left_artists == right_artists:
                add_edge(
                    left,
                    right,
                    "canonical_artist_composition_title",
                    1.0,
                    require_shared_artist=True,
                )
                continue
            collaboration = "collaboration_variant" in (
                set(left_unit.relation_tags) | set(right_unit.relation_tags)
            )
            if collaboration and left_artists & right_artists:
                add_edge(
                    left,
                    right,
                    "collaboration_variant_shared_artist",
                    0.98,
                    require_shared_artist=True,
                )
            elif collaboration:
                decided.add(pair)
                blocked_edges.append(
                    {
                        "left_l1_id": left_unit.primary_l1_id,
                        "right_l1_id": right_unit.primary_l1_id,
                        "left_unit_id": left,
                        "right_unit_id": right,
                        "evidence_type": "collaboration_variant",
                        "reason": "original_main_artist_absent",
                        "status": "rejected",
                    }
                )

    recording_by_id = {int(group["group_id"]): group for group in recording_groups}
    accepted_by_unit: dict[int, set[str]] = defaultdict(set)
    for edge in accepted_edges:
        accepted_by_unit[int(edge["left_unit_id"])].add(str(edge["evidence_type"]))
        accepted_by_unit[int(edge["right_unit_id"])].add(str(edge["evidence_type"]))
    desired: list[dict[str, Any]] = []
    for component in sorted(dsu.members.values(), key=min):
        if len(component) < 2 and not (component & manual_component_seeds):
            continue
        members = sorted({l1_id for unit_id in component for l1_id in units[unit_id].member_l1_ids})
        if len(members) < 2:
            continue
        primary = _choose_primary_unit(component, units)
        shared_artists = set.intersection(*(set(units[value].artist_ids) for value in component))
        automatic_artist_id = min(shared_artists) if shared_artists else min(primary.artist_ids)
        recording_group_ids = sorted(
            int(units[value].recording_group_id)
            for value in component
            if units[value].recording_group_id is not None
        )
        desired.append(
            {
                "unit_ids": sorted(component),
                "member_l1_ids": members,
                "recording_group_ids": recording_group_ids,
                "recording_groups": [recording_by_id[value] for value in recording_group_ids],
                "primary_l1_id": primary.primary_l1_id,
                "primary_track_id": primary.primary_track_id,
                "canonical_name": primary.canonical_name,
                "base_title": primary.base_title,
                "automatic_artist_id": automatic_artist_id,
                "relation_tags": sorted(
                    {tag for value in component for tag in units[value].relation_tags}
                ),
                "evidence_types": sorted(
                    {evidence for value in component for evidence in accepted_by_unit[value]}
                ),
            }
        )
    _assign_targets(desired, composition_groups)
    target_ids = {
        int(item["target_group_id"]) for item in desired if item["target_group_id"] is not None
    }
    archived_group_ids = sorted(
        int(group["group_id"])
        for group in composition_groups
        if int(group["group_id"]) not in target_ids
    )
    desired_parent_by_recording = {
        int(group_id): item["target_group_id"]
        for item in desired
        for group_id in item["recording_group_ids"]
    }
    parent_change_count = sum(
        group["parent_group_id"] != desired_parent_by_recording.get(int(group["group_id"]))
        for group in recording_groups
    )
    changed = bool(
        archived_group_ids
        or parent_change_count
        or any(item["action"] != "unchanged" for item in desired)
    )
    revision_row = conn.execute(
        "SELECT current_revision FROM track_identity_state WHERE state_id=1"
    ).fetchone()
    return {
        "policy_version": L3_AUTO_MERGE_POLICY_VERSION,
        "state_digest": _state_digest(
            units,
            recording_groups,
            composition_groups,
            explicit_separate,
            explicit_merge,
        ),
        "track_identity_revision": int(revision_row[0]) if revision_row else 0,
        "units_scanned": len(units),
        "recording_unit_count": sum(unit.recording_group_id is not None for unit in units.values()),
        "singleton_unit_count": sum(unit.recording_group_id is None for unit in units.values()),
        "desired_group_count": len(desired),
        "changed": changed,
        "groups_to_create": sum(item["action"] == "create" for item in desired),
        "groups_to_update": sum(item["action"] == "update" for item in desired),
        "groups_unchanged": sum(item["action"] == "unchanged" for item in desired),
        "groups_to_archive": len(archived_group_ids),
        "archived_group_ids": archived_group_ids,
        "recording_parent_changes": parent_change_count,
        "force_separate_pairs": [list(pair) for pair in sorted(explicit_separate)],
        "accepted_edges": accepted_edges,
        "blocked_edges": blocked_edges,
        "warning_edges": warning_edges,
        "edge_status_counts": {
            "accepted": len(accepted_edges),
            "rejected": len(blocked_edges),
            "pending": 0,
        },
        "warning_reason_counts": {
            warning: sum(edge["warning"] == warning for edge in warning_edges)
            for warning in sorted({edge["warning"] for edge in warning_edges})
        },
        "groups": desired,
    }


def _group_by_composition_member(conn: sqlite3.Connection) -> dict[int, int]:
    return {
        int(row["l1_id"]): int(row["group_id"])
        for row in conn.execute(
            """SELECT members.l1_id, members.group_id
                 FROM track_group_l1_members members
                 JOIN track_groups groups ON groups.group_id=members.group_id
                WHERE groups.scope='composition' AND groups.group_status='active'"""
        ).fetchall()
    }


def _upsert_candidate_evidence(
    conn: sqlite3.Connection, plan: dict[str, Any], group_by_member: dict[int, int]
) -> int:
    warnings: dict[tuple[int, int], list[str]] = defaultdict(list)
    for edge in plan["warning_edges"]:
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        pair = (min(left, right), max(left, right))
        warnings[pair].append(str(edge["warning"]))
    decisions: dict[tuple[int, int], tuple[str, float, dict[str, Any]]] = {}
    for edge in plan["accepted_edges"]:
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        if group_by_member.get(left) != group_by_member.get(right):
            continue
        pair = (min(left, right), max(left, right))
        decisions[pair] = (
            "accepted",
            float(edge["confidence"]),
            {
                "policy_version": plan["policy_version"],
                "evidence_type": edge["evidence_type"],
                "relation_tags": edge.get("relation_tags", []),
                "warnings": sorted(set(warnings.get(pair, []))),
                "automatic": edge["evidence_type"] not in {"force_merge", "existing_manual_group"},
            },
        )
    for edge in plan["blocked_edges"]:
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        pair = (min(left, right), max(left, right))
        decisions[pair] = (
            "rejected",
            0.0,
            {
                "policy_version": plan["policy_version"],
                "evidence_type": edge["evidence_type"],
                "reason": edge["reason"],
                "blocker_tags": edge.get("blocker_tags", []),
                "automatic": edge["evidence_type"] != "force_separate",
            },
        )
    for (left, right), (status, confidence, evidence) in decisions.items():
        payload = json.dumps(evidence, ensure_ascii=False, sort_keys=True)
        updated = conn.execute(
            """UPDATE track_group_candidates
                  SET confidence=?, evidence_json=?, status=?
                WHERE scope='composition'
                  AND MIN(original_l1_id, candidate_l1_id)=?
                  AND MAX(original_l1_id, candidate_l1_id)=?""",
            (confidence, payload, status, left, right),
        ).rowcount
        if not updated:
            conn.execute(
                """INSERT INTO track_group_candidates(
                       scope, original_l1_id, candidate_l1_id,
                       confidence, evidence_json, status
                   ) VALUES ('composition', ?, ?, ?, ?, ?)""",
                (left, right, confidence, payload, status),
            )
    return len(decisions)


def apply_l3_track_merge_plan(
    conn: sqlite3.Connection,
    plan: dict[str, Any] | None = None,
    *,
    commit: bool = False,
    bump_revision: bool = True,
) -> dict[str, Any]:
    """Apply one current L3 plan without rebuilding downstream snapshots."""

    current = build_l3_track_merge_plan(conn)
    if plan is not None and plan.get("state_digest") != current["state_digest"]:
        return {
            "status": "stale",
            "message": "L3 composition identity inputs changed after the dry-run",
            "expected_state_digest": plan.get("state_digest"),
            "current_state_digest": current["state_digest"],
        }
    plan = current
    if not plan["changed"]:
        candidate_count = _upsert_candidate_evidence(conn, plan, _group_by_composition_member(conn))
        if commit:
            conn.commit()
        return {
            "status": "unchanged",
            "changed": False,
            "policy_version": plan["policy_version"],
            "group_count": plan["desired_group_count"],
            "groups_created": 0,
            "groups_updated": 0,
            "groups_archived": 0,
            "members_added": 0,
            "members_removed": 0,
            "recording_parents_updated": 0,
            "candidate_evidence_upserted": candidate_count,
            "revision_bumped": False,
            "track_identity_revision": plan["track_identity_revision"],
        }

    before_groups = {
        int(group["group_id"]): set(group["member_l1_ids"]) for group in _composition_groups(conn)
    }
    before_parents = {
        int(group["group_id"]): group["parent_group_id"] for group in _recording_groups(conn)
    }
    conn.execute("SAVEPOINT l3_track_auto_merge")
    try:
        conn.execute(
            """UPDATE track_groups SET group_status='archived'
                WHERE scope='composition' AND group_status='active'"""
        )
        conn.execute(
            """UPDATE track_groups SET parent_group_id=NULL
                WHERE scope='recording' AND group_status='active'"""
        )
        created = 0
        updated = 0
        group_by_member: dict[int, int] = {}
        for item in plan["groups"]:
            target_group_id = item["target_group_id"]
            if target_group_id is None:
                cursor = conn.execute(
                    """INSERT INTO track_groups(
                           canonical_name, primary_track_id, primary_l1_id,
                           scope, is_manual, group_status,
                           automatic_artist_id, automatic_title_key,
                           automatic_version_tag, identity_policy_version
                       ) VALUES (?, ?, ?, 'composition', 0, 'archived', ?, ?, '', ?)""",
                    (
                        item["canonical_name"],
                        int(item["primary_track_id"]),
                        int(item["primary_l1_id"]),
                        int(item["automatic_artist_id"]),
                        item["base_title"],
                        plan["policy_version"],
                    ),
                )
                target_group_id = int(cursor.lastrowid)
                item["target_group_id"] = target_group_id
                created += 1
            else:
                target_group_id = int(target_group_id)
                if item["action"] == "update":
                    updated += 1
                conn.execute(
                    "DELETE FROM track_group_l1_members WHERE group_id=?",
                    (target_group_id,),
                )
                if not item["target_is_manual"]:
                    conn.execute(
                        """UPDATE track_groups
                              SET canonical_name=?, primary_track_id=?, primary_l1_id=?,
                                  automatic_spotify_track_id=NULL,
                                  automatic_artist_id=?, automatic_title_key=?,
                                  automatic_version_tag='', identity_policy_version=?
                            WHERE group_id=?""",
                        (
                            item["canonical_name"],
                            int(item["primary_track_id"]),
                            int(item["primary_l1_id"]),
                            int(item["automatic_artist_id"]),
                            item["base_title"],
                            plan["policy_version"],
                            target_group_id,
                        ),
                    )
            for l1_id in item["member_l1_ids"]:
                conn.execute(
                    "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
                    (target_group_id, int(l1_id)),
                )
                group_by_member[int(l1_id)] = target_group_id
            conn.execute(
                "UPDATE track_groups SET group_status='active' WHERE group_id=?",
                (target_group_id,),
            )
            for recording_group_id in item["recording_group_ids"]:
                conn.execute(
                    "UPDATE track_groups SET parent_group_id=? WHERE group_id=?",
                    (target_group_id, int(recording_group_id)),
                )
        candidate_count = _upsert_candidate_evidence(conn, plan, group_by_member)
        after_groups = {
            int(group["group_id"]): set(group["member_l1_ids"])
            for group in _composition_groups(conn)
        }
        after_parents = {
            int(group["group_id"]): group["parent_group_id"] for group in _recording_groups(conn)
        }
        members_added = sum(
            len(after_groups.get(group_id, set()) - before_groups.get(group_id, set()))
            for group_id in set(before_groups) | set(after_groups)
        )
        members_removed = sum(
            len(before_groups.get(group_id, set()) - after_groups.get(group_id, set()))
            for group_id in set(before_groups) | set(after_groups)
        )
        parents_updated = sum(
            before_parents.get(group_id) != after_parents.get(group_id)
            for group_id in set(before_parents) | set(after_parents)
        )
        revision = plan["track_identity_revision"]
        revision_bumped = False
        if bump_revision:
            from backend.domains.metadata.track_identity import bump_track_identity_revision

            revision = bump_track_identity_revision(conn)
            revision_bumped = True
        conn.execute("RELEASE SAVEPOINT l3_track_auto_merge")
        if commit:
            conn.commit()
        return {
            "status": "applied",
            "changed": True,
            "policy_version": plan["policy_version"],
            "group_count": plan["desired_group_count"],
            "groups_created": created,
            "groups_updated": updated,
            "groups_archived": len(plan["archived_group_ids"]),
            "members_added": members_added,
            "members_removed": members_removed,
            "recording_parents_updated": parents_updated,
            "candidate_evidence_upserted": candidate_count,
            "revision_bumped": revision_bumped,
            "track_identity_revision": revision,
        }
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT l3_track_auto_merge")
        conn.execute("RELEASE SAVEPOINT l3_track_auto_merge")
        raise
