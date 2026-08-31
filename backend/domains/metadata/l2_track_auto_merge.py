"""Machine-first reconciliation of L2 recording groups.

The planner is read-only and serialisable.  The applier reconciles all active
recording groups in one savepoint and bumps the track identity revision at
most once.  It deliberately does not rebuild album projects or caches; batch
callers do that once after all metadata work has completed.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from backend.domains.metadata.track_title_identity import (
    L2_TITLE_IDENTITY_POLICY_VERSION,
    normalize_l2_track_title,
)

L2_AUTO_MERGE_POLICY_VERSION = f"canonical_artist_title_v3:{L2_TITLE_IDENTITY_POLICY_VERSION}"

_STRUCTURAL_TITLE_PATTERN = re.compile(
    r"^(?:(?:the)\s+)?(?:intro|outro|interlude|overture|ouverture|prelude|"
    r"prologue|epilogue|theme|序曲|间奏|前奏|尾声|主题曲?)(?:\s|$)",
    re.IGNORECASE,
)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        is not None
    )


@dataclass(frozen=True)
class _TrackNode:
    l1_id: int
    representative_track_id: int
    track_name: str
    artist_ids: tuple[int, ...]
    normalized_title: str
    semantic_version_tags: tuple[str, ...]
    source_context_tags: tuple[str, ...]
    play_count: int
    external_id_count: int
    isrc_durations: tuple[tuple[str, int | None], ...]
    is_noncanonical_alias: bool

    @property
    def title_key(self) -> tuple[tuple[int, ...], str, tuple[str, ...]]:
        return self.artist_ids, self.normalized_title, self.semantic_version_tags


class _DisjointSets:
    def __init__(self, values: list[int], cannot_link: set[tuple[int, int]]):
        self.parent = {value: value for value in values}
        self.members = {value: {value} for value in values}
        self.cannot_link = cannot_link

    def find(self, value: int) -> int:
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: int, right: int) -> bool:
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
        if (len(left_members), -left_root) < (len(right_members), -right_root):
            left_root, right_root = right_root, left_root
            left_members, right_members = right_members, left_members
        self.parent[right_root] = left_root
        left_members.update(right_members)
        del self.members[right_root]
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


def _load_nodes(
    conn: sqlite3.Connection, noncanonical_l1_ids: set[int] | None = None
) -> dict[int, _TrackNode]:
    noncanonical_l1_ids = noncanonical_l1_ids or set()
    rows = conn.execute(
        """SELECT li.l1_id, li.representative_track_id, t.track_name,
                  COALESCE(SUM(CASE WHEN links.evidence_type='play_at_time'
                                    THEN links.observed_plays ELSE 0 END), 0) AS play_count
             FROM track_l1_identities li
             JOIN tracks t ON t.track_id=li.representative_track_id
             LEFT JOIN track_l1_source_links links ON links.l1_id=li.l1_id
            WHERE li.identity_status='active'
            GROUP BY li.l1_id
            ORDER BY li.l1_id"""
    ).fetchall()
    representative_ids = [int(row["representative_track_id"]) for row in rows]
    artist_signatures = _canonical_artist_signatures(conn, representative_ids)
    metadata: dict[int, list[tuple[str, int | None]]] = defaultdict(list)
    external_id_counts: dict[int, int] = {}
    if _table_exists(conn, "track_l1_external_ids"):
        external_id_counts = {
            int(row["l1_id"]): int(row["external_id_count"])
            for row in conn.execute(
                """SELECT l1_id, COUNT(*) AS external_id_count
                     FROM track_l1_external_ids
                    GROUP BY l1_id"""
            ).fetchall()
        }
    if _table_exists(conn, "track_l1_external_ids") and _table_exists(conn, "spotify_track_meta"):
        for row in conn.execute(
            """SELECT external.l1_id, UPPER(TRIM(meta.isrc)) AS isrc,
                      meta.duration_ms
                 FROM track_l1_external_ids external
                 JOIN spotify_track_meta meta
                   ON external.provider='spotify'
                  AND meta.spotify_track_id=external.external_track_id
                WHERE NULLIF(TRIM(meta.isrc), '') IS NOT NULL
                ORDER BY external.l1_id, isrc, meta.duration_ms"""
        ).fetchall():
            value = (str(row["isrc"]), int(row["duration_ms"]) if row["duration_ms"] else None)
            if value not in metadata[int(row["l1_id"])]:
                metadata[int(row["l1_id"])].append(value)

    nodes: dict[int, _TrackNode] = {}
    for row in rows:
        l1_id = int(row["l1_id"])
        representative_track_id = int(row["representative_track_id"])
        artist_ids = artist_signatures.get(representative_track_id)
        if not artist_ids:
            continue
        title = normalize_l2_track_title(str(row["track_name"]))
        if not title.base_title:
            continue
        nodes[l1_id] = _TrackNode(
            l1_id=l1_id,
            representative_track_id=representative_track_id,
            track_name=str(row["track_name"]),
            artist_ids=artist_ids,
            normalized_title=title.base_title,
            semantic_version_tags=title.semantic_version_tags,
            source_context_tags=title.source_context_tags,
            play_count=int(row["play_count"] or 0),
            external_id_count=external_id_counts.get(l1_id, 0),
            isrc_durations=tuple(metadata.get(l1_id, ())),
            is_noncanonical_alias=l1_id in noncanonical_l1_ids,
        )
    return nodes


def _load_overrides(conn: sqlite3.Connection) -> tuple[set[tuple[int, int]], list[tuple[int, int]]]:
    force_separate: set[tuple[int, int]] = set()
    force_merge: list[tuple[int, int]] = []
    if not _table_exists(conn, "track_merge_overrides"):
        return force_separate, force_merge
    rows = conn.execute(
        """SELECT left_l1_id, right_l1_id, action
             FROM track_merge_overrides
            WHERE scope='recording'
            ORDER BY MIN(left_l1_id, right_l1_id), MAX(left_l1_id, right_l1_id)"""
    ).fetchall()
    for row in rows:
        left = int(row["left_l1_id"])
        right = int(row["right_l1_id"])
        pair: tuple[int, int] = (min(left, right), max(left, right))
        if str(row["action"]) == "force_separate":
            force_separate.add(pair)
        elif str(row["action"]) == "force_merge":
            force_merge.append(pair)
    return force_separate, force_merge


def _active_recording_groups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT groups.group_id, groups.canonical_name, groups.primary_l1_id,
                  groups.parent_group_id, groups.is_manual, members.l1_id
                  , groups.automatic_artist_id, groups.automatic_title_key,
                    groups.automatic_version_tag, groups.identity_policy_version
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
                "primary_l1_id": (
                    int(row["primary_l1_id"]) if row["primary_l1_id"] is not None else None
                ),
                "parent_group_id": (
                    int(row["parent_group_id"]) if row["parent_group_id"] is not None else None
                ),
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


def _noncanonical_candidate_rows(
    conn: sqlite3.Connection, noncanonical_l1_ids: set[int]
) -> list[dict[str, Any]]:
    if not noncanonical_l1_ids or not _table_exists(conn, "track_group_candidates"):
        return []
    placeholders = ",".join("?" for _value in noncanonical_l1_ids)
    values = sorted(noncanonical_l1_ids)
    rows = conn.execute(
        f"""SELECT original_l1_id, candidate_l1_id, status, evidence_json
              FROM track_group_candidates
             WHERE scope='recording'
               AND (original_l1_id IN ({placeholders})
                    OR candidate_l1_id IN ({placeholders}))
             ORDER BY MIN(original_l1_id, candidate_l1_id),
                      MAX(original_l1_id, candidate_l1_id)""",
        (*values, *values),
    ).fetchall()
    return [
        {
            "left_l1_id": min(int(row["original_l1_id"]), int(row["candidate_l1_id"])),
            "right_l1_id": max(int(row["original_l1_id"]), int(row["candidate_l1_id"])),
            "status": str(row["status"]),
            "evidence_json": str(row["evidence_json"]),
        }
        for row in rows
    ]


def _durations_compatible(left: int | None, right: int | None) -> bool:
    if left is None or right is None or left <= 0 or right <= 0:
        return False
    tolerance = max(2_000, round(max(left, right) * 0.01))
    return abs(left - right) <= tolerance


def _shared_isrc_evidence(left: _TrackNode, right: _TrackNode) -> list[str]:
    if (
        left.artist_ids != right.artist_ids
        or left.semantic_version_tags != right.semantic_version_tags
    ):
        return []
    matches: list[str] = []
    for left_isrc, left_duration in left.isrc_durations:
        for right_isrc, right_duration in right.isrc_durations:
            if left_isrc == right_isrc and _durations_compatible(left_duration, right_duration):
                matches.append(left_isrc)
    return sorted(set(matches))


def _has_disjoint_isrcs(left: _TrackNode, right: _TrackNode) -> bool:
    left_isrcs = {isrc for isrc, _duration in left.isrc_durations}
    right_isrcs = {isrc for isrc, _duration in right.isrc_durations}
    return bool(left_isrcs and right_isrcs and left_isrcs.isdisjoint(right_isrcs))


def _has_strong_duration_conflict(left: _TrackNode, right: _TrackNode) -> bool:
    left_durations = [duration for _isrc, duration in left.isrc_durations if duration]
    right_durations = [duration for _isrc, duration in right.isrc_durations if duration]
    if not left_durations or not right_durations:
        return False
    return (
        min(
            abs(left_duration - right_duration)
            for left_duration in left_durations
            for right_duration in right_durations
        )
        >= 10_000
    )


def _has_internal_identity_conflict(node: _TrackNode) -> bool:
    isrcs = {isrc for isrc, _duration in node.isrc_durations}
    durations = [duration for _isrc, duration in node.isrc_durations if duration]
    return len(isrcs) >= 2 and len(durations) >= 2 and max(durations) - min(durations) >= 10_000


def _is_structural_title(node: _TrackNode) -> bool:
    if _STRUCTURAL_TITLE_PATTERN.match(node.normalized_title):
        return True
    tokens = node.normalized_title.split()
    if len(tokens) <= 3 and tokens and tokens[-1] == "theme":
        return True
    return node.normalized_title.endswith(("主题", "主题曲")) and len(node.normalized_title) <= 8


def _pair_audit_warnings(left: _TrackNode, right: _TrackNode) -> list[str]:
    warnings: list[str] = []
    if left.source_context_tags or right.source_context_tags:
        warnings.append("source_context_present")
    if _has_disjoint_isrcs(left, right):
        warnings.append("disjoint_isrc")
    if _has_strong_duration_conflict(left, right):
        warnings.append("strong_duration_conflict")
    if _has_internal_identity_conflict(left) or _has_internal_identity_conflict(right):
        warnings.append("internal_identity_conflict")
    if (
        left.play_count == 0
        and right.play_count == 0
        and left.external_id_count == 0
        and right.external_id_count == 0
    ):
        warnings.append("zero_play_zero_external_evidence")
    return warnings


def _automatic_pair_decision(left: _TrackNode, right: _TrackNode) -> tuple[str, str] | None:
    """Return a title-level decision before inferred edges are connected."""

    if left.artist_ids != right.artist_ids or left.normalized_title != right.normalized_title:
        return None
    if left.is_noncanonical_alias or right.is_noncanonical_alias:
        return "rejected", "noncanonical_identity_requires_owner_repair"
    if _is_structural_title(left) or _is_structural_title(right):
        return "rejected", "structural_title_requires_explicit_merge"
    if left.semantic_version_tags != right.semantic_version_tags:
        return "rejected", "semantic_version_conflict"
    return None


def _choose_primary(component: set[int], nodes: dict[int, _TrackNode]) -> int:
    return min(component, key=lambda value: (-nodes[value].play_count, value))


def _state_digest(
    nodes: dict[int, _TrackNode],
    groups: list[dict[str, Any]],
    force_separate: set[tuple[int, int]],
    force_merge: list[tuple[int, int]],
    noncanonical_l1_ids: set[int],
    noncanonical_candidate_rows: list[dict[str, Any]],
) -> str:
    payload = {
        "nodes": [
            {
                "l1_id": node.l1_id,
                "representative_track_id": node.representative_track_id,
                "track_name": node.track_name,
                "artist_ids": node.artist_ids,
                "normalized_title": node.normalized_title,
                "semantic_version_tags": node.semantic_version_tags,
                "source_context_tags": node.source_context_tags,
                "play_count": node.play_count,
                "external_id_count": node.external_id_count,
                "isrc_durations": node.isrc_durations,
                "is_noncanonical_alias": node.is_noncanonical_alias,
            }
            for node in nodes.values()
        ],
        "groups": groups,
        "force_separate": sorted(force_separate),
        "force_merge": sorted(force_merge),
        "noncanonical_l1_ids": sorted(noncanonical_l1_ids),
        "noncanonical_candidate_rows": noncanonical_candidate_rows,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _assign_existing_targets(desired: list[dict[str, Any]], groups: list[dict[str, Any]]) -> None:
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
            if target["is_manual"] and target["primary_l1_id"] in members:
                item["primary_l1_id"] = int(target["primary_l1_id"])
                item["canonical_name"] = str(target["canonical_name"])
        current_members = set(target["member_l1_ids"]) if target else set()
        expected_artist_id = int(item["artist_ids"][0]) if len(item["artist_ids"]) == 1 else None
        expected_title_key = (
            str(item["normalized_title"]) if expected_artist_id is not None else None
        )
        expected_version_tag = (
            "\x1f".join(str(tag) for tag in item["semantic_version_tags"])
            if expected_artist_id is not None
            else None
        )
        identity_matches = bool(
            target
            and (
                bool(target["is_manual"])
                or (
                    target["automatic_artist_id"] == expected_artist_id
                    and target["automatic_title_key"] == expected_title_key
                    and target["automatic_version_tag"] == expected_version_tag
                    and target["identity_policy_version"] == L2_AUTO_MERGE_POLICY_VERSION
                )
            )
        )
        item["action"] = (
            "unchanged"
            if target and current_members == members and identity_matches
            else "update"
            if target
            else "create"
        )


def build_l2_track_merge_plan(conn: sqlite3.Connection) -> dict[str, Any]:
    """Build a complete, read-only reconciliation plan for recording groups."""

    noncanonical_l1_ids = _load_noncanonical_l1_ids(conn)
    nodes = _load_nodes(conn, noncanonical_l1_ids)
    groups = _active_recording_groups(conn)
    noncanonical_candidate_rows = _noncanonical_candidate_rows(conn, noncanonical_l1_ids)
    force_separate, force_merge = _load_overrides(conn)
    # The DSU adds policy-derived cannot-link edges while it evaluates the
    # graph.  Keep that mutable working set separate from the durable manual
    # overrides so the serialised plan does not misreport inferred conflicts
    # as user-authored force-separate decisions.
    explicit_force_separate = set(force_separate)
    node_ids = sorted(nodes)
    dsu = _DisjointSets(node_ids, set(force_separate))
    accepted_edges: list[dict[str, Any]] = []
    blocked_edges: list[dict[str, Any]] = []
    warning_edges: list[dict[str, Any]] = []

    parent_by_member: dict[int, int] = {}
    for group in groups:
        if group["parent_group_id"] is not None:
            for member in group["member_l1_ids"]:
                parent_by_member[int(member)] = int(group["parent_group_id"])

    def add_edge(left: int, right: int, evidence_type: str, confidence: float) -> None:
        if left not in nodes or right not in nodes or left == right:
            return
        left_parent = parent_by_member.get(left)
        right_parent = parent_by_member.get(right)
        if left_parent is not None and right_parent is not None and left_parent != right_parent:
            blocked_edges.append(
                {
                    "left_l1_id": min(left, right),
                    "right_l1_id": max(left, right),
                    "evidence_type": evidence_type,
                    "reason": "composition_parent_conflict",
                    "status": "rejected",
                }
            )
            return
        if dsu.union(left, right):
            accepted_edges.append(
                {
                    "left_l1_id": min(left, right),
                    "right_l1_id": max(left, right),
                    "evidence_type": evidence_type,
                    "confidence": confidence,
                }
            )
        else:
            blocked_edges.append(
                {
                    "left_l1_id": min(left, right),
                    "right_l1_id": max(left, right),
                    "evidence_type": evidence_type,
                    "reason": "force_separate",
                    "status": "rejected",
                }
            )

    # Explicit decisions outrank every inferred relation.
    for left, right in sorted(force_merge):
        add_edge(left, right, "force_merge", 1.0)

    # Existing manually curated groups remain connected unless force_separate
    # explicitly breaks them.
    for group in groups:
        members = [member for member in group["member_l1_ids"] if member in nodes]
        if not group["is_manual"] or len(members) < 2:
            continue
        anchor = members[0]
        for member in members[1:]:
            add_edge(anchor, member, "existing_manual_group", 1.0)

    # Semantic versions, structural titles and noncanonical aliases must not
    # be bypassed through a third inferred title edge. Explicit force-merge and
    # existing manual groups were already connected above and remain authoritative.
    automatic_decisions: dict[tuple[int, int], tuple[str, str]] = {}
    for left, right in sorted(force_separate):
        automatic_decisions[(left, right)] = ("rejected", "force_separate")
        if not any(
            edge["left_l1_id"] == left
            and edge["right_l1_id"] == right
            and edge["reason"] == "force_separate"
            for edge in blocked_edges
        ):
            blocked_edges.append(
                {
                    "left_l1_id": left,
                    "right_l1_id": right,
                    "evidence_type": "force_separate",
                    "reason": "force_separate",
                    "status": "rejected",
                }
            )
    for candidate in noncanonical_candidate_rows:
        pair = (int(candidate["left_l1_id"]), int(candidate["right_l1_id"]))
        left, right = pair
        if pair in automatic_decisions:
            continue
        if left in nodes and right in nodes and dsu.find(left) == dsu.find(right):
            continue
        decision = ("rejected", "noncanonical_identity_requires_owner_repair")
        automatic_decisions[pair] = decision
        if left in nodes and right in nodes:
            dsu.cannot_link.add(pair)
        blocked_edges.append(
            {
                "left_l1_id": left,
                "right_l1_id": right,
                "evidence_type": "noncanonical_candidate_reconciliation",
                "reason": decision[1],
                "status": decision[0],
            }
        )
    by_base_title: dict[tuple[tuple[int, ...], str], list[int]] = defaultdict(list)
    for node in nodes.values():
        by_base_title[(node.artist_ids, node.normalized_title)].append(node.l1_id)
    for members in by_base_title.values():
        for left, right in itertools.combinations(sorted(set(members)), 2):
            if (left, right) in automatic_decisions:
                continue
            decision = _automatic_pair_decision(nodes[left], nodes[right])
            if decision is None or dsu.find(left) == dsu.find(right):
                continue
            automatic_decisions[(left, right)] = decision
            dsu.cannot_link.add((left, right))
            status, reason = decision
            blocked_edges.append(
                {
                    "left_l1_id": left,
                    "right_l1_id": right,
                    "evidence_type": "canonical_artist_normalized_title",
                    "reason": reason,
                    "status": status,
                }
            )

    by_title: dict[tuple[tuple[int, ...], str, tuple[str, ...]], list[int]] = defaultdict(list)
    for node in nodes.values():
        by_title[node.title_key].append(node.l1_id)
    for members in by_title.values():
        if len(members) < 2:
            continue
        for left, right in itertools.combinations(sorted(set(members)), 2):
            if (left, right) in automatic_decisions:
                continue
            for warning in _pair_audit_warnings(nodes[left], nodes[right]):
                warning_edges.append(
                    {
                        "left_l1_id": left,
                        "right_l1_id": right,
                        "warning": warning,
                    }
                )
            add_edge(left, right, "canonical_artist_normalized_title", 1.0)

    # Shared ISRC remains a conservative fallback for spelling differences.
    # Same-title merges above never require it and never let it veto identity.
    by_isrc: dict[tuple[tuple[int, ...], str, tuple[str, ...]], list[int]] = defaultdict(list)
    for node in nodes.values():
        for isrc, _duration in node.isrc_durations:
            by_isrc[(node.artist_ids, isrc, node.semantic_version_tags)].append(node.l1_id)
    for (_artists, isrc, _tags), members in by_isrc.items():
        for left, right in itertools.combinations(sorted(set(members)), 2):
            pair = (left, right)
            if nodes[left].normalized_title == nodes[right].normalized_title:
                continue
            if dsu.find(left) != dsu.find(right) and (
                nodes[left].is_noncanonical_alias or nodes[right].is_noncanonical_alias
            ):
                if pair not in automatic_decisions:
                    automatic_decisions[pair] = (
                        "rejected",
                        "noncanonical_identity_requires_owner_repair",
                    )
                    dsu.cannot_link.add(pair)
                    blocked_edges.append(
                        {
                            "left_l1_id": left,
                            "right_l1_id": right,
                            "evidence_type": "same_isrc_compatible_duration",
                            "reason": "noncanonical_identity_requires_owner_repair",
                            "status": "rejected",
                        }
                    )
                continue
            if dsu.find(left) != dsu.find(right) and (
                _is_structural_title(nodes[left]) or _is_structural_title(nodes[right])
            ):
                if pair not in automatic_decisions:
                    automatic_decisions[pair] = (
                        "rejected",
                        "structural_title_requires_explicit_merge",
                    )
                    dsu.cannot_link.add(pair)
                    blocked_edges.append(
                        {
                            "left_l1_id": left,
                            "right_l1_id": right,
                            "evidence_type": "same_isrc_compatible_duration",
                            "reason": "structural_title_requires_explicit_merge",
                            "status": "rejected",
                        }
                    )
                continue
            if isrc in _shared_isrc_evidence(nodes[left], nodes[right]):
                add_edge(left, right, "same_isrc_compatible_duration", 0.99)

    warning_edges = [
        {
            "left_l1_id": left,
            "right_l1_id": right,
            "warning": warning,
        }
        for left, right, warning in sorted(
            {
                (int(edge["left_l1_id"]), int(edge["right_l1_id"]), str(edge["warning"]))
                for edge in warning_edges
            }
        )
    ]

    edges_by_member: dict[int, set[str]] = defaultdict(set)
    for edge in accepted_edges:
        edges_by_member[int(edge["left_l1_id"])].add(str(edge["evidence_type"]))
        edges_by_member[int(edge["right_l1_id"])].add(str(edge["evidence_type"]))

    desired: list[dict[str, Any]] = []
    for component in sorted(dsu.members.values(), key=lambda values: min(values)):
        if len(component) < 2:
            continue
        primary = _choose_primary(component, nodes)
        desired.append(
            {
                "member_l1_ids": sorted(component),
                "primary_l1_id": primary,
                "primary_track_id": nodes[primary].representative_track_id,
                "canonical_name": nodes[primary].track_name,
                "artist_ids": list(nodes[primary].artist_ids),
                "normalized_title": nodes[primary].normalized_title,
                "semantic_version_tags": list(nodes[primary].semantic_version_tags),
                "evidence_types": sorted(
                    set().union(*(edges_by_member[member] for member in component))
                ),
            }
        )
    _assign_existing_targets(desired, groups)
    target_ids = {
        int(item["target_group_id"]) for item in desired if item["target_group_id"] is not None
    }
    archived_group_ids = sorted(
        int(group["group_id"]) for group in groups if int(group["group_id"]) not in target_ids
    )
    changed = bool(archived_group_ids or any(item["action"] != "unchanged" for item in desired))
    state_digest = _state_digest(
        nodes,
        groups,
        force_separate,
        force_merge,
        noncanonical_l1_ids,
        noncanonical_candidate_rows,
    )
    revision_row = (
        conn.execute(
            "SELECT current_revision FROM track_identity_state WHERE state_id=1"
        ).fetchone()
        if _table_exists(conn, "track_identity_state")
        else None
    )
    blocked_status_counts = {
        status: sum(edge.get("status", "rejected") == status for edge in blocked_edges)
        for status in ("pending", "rejected")
    }
    return {
        "policy_version": L2_AUTO_MERGE_POLICY_VERSION,
        "state_digest": state_digest,
        "track_identity_revision": int(revision_row[0]) if revision_row else 0,
        "nodes_scanned": len(nodes),
        "desired_group_count": len(desired),
        "changed": changed,
        "groups_to_create": sum(item["action"] == "create" for item in desired),
        "groups_to_update": sum(item["action"] == "update" for item in desired),
        "groups_unchanged": sum(item["action"] == "unchanged" for item in desired),
        "groups_to_archive": len(archived_group_ids),
        "archived_group_ids": archived_group_ids,
        "force_separate_pairs": [list(pair) for pair in sorted(explicit_force_separate)],
        "derived_cannot_link_pair_count": len(dsu.cannot_link - explicit_force_separate),
        "edge_status_counts": {
            "accepted": len(accepted_edges),
            **blocked_status_counts,
        },
        "strong_internal_identity_conflict_node_count": sum(
            _has_internal_identity_conflict(node) for node in nodes.values()
        ),
        "noncanonical_identity_node_count": sum(
            node.is_noncanonical_alias for node in nodes.values()
        ),
        "noncanonical_candidate_rejection_count": sum(
            edge.get("reason") == "noncanonical_identity_requires_owner_repair"
            for edge in blocked_edges
        ),
        "unsubstantiated_zero_evidence_pair_count": sum(
            edge.get("warning") == "zero_play_zero_external_evidence" for edge in warning_edges
        ),
        "warning_reason_counts": {
            warning: sum(edge["warning"] == warning for edge in warning_edges)
            for warning in sorted({edge["warning"] for edge in warning_edges})
        },
        "accepted_edges": accepted_edges,
        "blocked_edges": blocked_edges,
        "warning_edges": warning_edges,
        "groups": desired,
    }


def _upsert_candidate_evidence(
    conn: sqlite3.Connection, plan: dict[str, Any], group_by_member: dict[int, int]
) -> int:
    if not _table_exists(conn, "track_group_candidates"):
        return 0
    decisions: dict[tuple[int, int], tuple[int, str, float, dict[str, Any]]] = {}
    warnings_by_pair: dict[tuple[int, int], list[str]] = defaultdict(list)
    for edge in plan.get("warning_edges", []):
        pair = (int(edge["left_l1_id"]), int(edge["right_l1_id"]))
        warning = str(edge["warning"])
        if warning not in warnings_by_pair[pair]:
            warnings_by_pair[pair].append(warning)

    for edge in plan["accepted_edges"]:
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        if group_by_member.get(left) != group_by_member.get(right):
            continue
        evidence_type = str(edge["evidence_type"])
        priority = {
            "force_merge": 100,
            "existing_manual_group": 90,
            "same_isrc_compatible_duration": 80,
            "canonical_artist_normalized_title": 70,
        }.get(evidence_type, 60)
        decisions[(left, right)] = (
            priority,
            "accepted",
            float(edge["confidence"]),
            {
                "policy_version": plan["policy_version"],
                "evidence_type": evidence_type,
                "automatic": evidence_type not in {"force_merge", "existing_manual_group"},
                "warnings": sorted(warnings_by_pair.get((left, right), [])),
            },
        )

    for edge in plan["blocked_edges"]:
        left = int(edge["left_l1_id"])
        right = int(edge["right_l1_id"])
        status = str(edge.get("status") or "rejected")
        reason = str(edge["reason"])
        priority = 110 if reason == "force_separate" else 50 if status == "rejected" else 40
        pair = (left, right)
        existing = decisions.get(pair)
        if existing is not None and existing[0] >= priority:
            continue
        decisions[pair] = (
            priority,
            status,
            0.0,
            {
                "policy_version": plan["policy_version"],
                "evidence_type": edge["evidence_type"],
                "reason": reason,
                "automatic": reason != "force_separate",
            },
        )

    for (left, right), (_priority, status, confidence, evidence_payload) in decisions.items():
        evidence = json.dumps(evidence_payload, ensure_ascii=False, sort_keys=True)
        updated = conn.execute(
            """UPDATE track_group_candidates
                  SET confidence=?, evidence_json=?, status=?
                WHERE scope='recording'
                  AND MIN(original_l1_id, candidate_l1_id)=?
                  AND MAX(original_l1_id, candidate_l1_id)=?""",
            (confidence, evidence, status, left, right),
        ).rowcount
        if not updated:
            conn.execute(
                """INSERT INTO track_group_candidates(
                       scope, original_l1_id, candidate_l1_id,
                       confidence, evidence_json, status
                   ) VALUES ('recording', ?, ?, ?, ?, ?)""",
                (left, right, confidence, evidence, status),
            )
    return len(decisions)


def _group_by_active_recording_member(conn: sqlite3.Connection) -> dict[int, int]:
    return {
        int(row["l1_id"]): int(row["group_id"])
        for row in conn.execute(
            """SELECT members.l1_id, members.group_id
                 FROM track_group_l1_members members
                 JOIN track_groups groups ON groups.group_id=members.group_id
                WHERE groups.scope='recording' AND groups.group_status='active'"""
        ).fetchall()
    }


def apply_l2_track_merge_plan(
    conn: sqlite3.Connection,
    plan: dict[str, Any] | None = None,
    *,
    commit: bool = False,
    bump_revision: bool = True,
) -> dict[str, Any]:
    """Apply one current plan atomically without rebuilding dependents.

    A stale dry-run is rejected. Callers that already own a larger metadata
    transaction should keep ``commit=False`` and may set ``bump_revision=False``
    so the outer governance transaction advances the revision exactly once.
    Standalone callers retain the default revision bump.
    """

    current = build_l2_track_merge_plan(conn)
    if plan is not None and plan.get("state_digest") != current["state_digest"]:
        return {
            "status": "stale",
            "message": "L2 track identity inputs changed after the dry-run",
            "expected_state_digest": plan.get("state_digest"),
            "current_state_digest": current["state_digest"],
        }
    plan = current
    if not plan["changed"]:
        candidate_count = _upsert_candidate_evidence(
            conn, plan, _group_by_active_recording_member(conn)
        )
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
            "candidate_evidence_upserted": candidate_count,
            "revision_bumped": False,
            "track_identity_revision": plan["track_identity_revision"],
        }

    before_groups = {
        int(group["group_id"]): set(group["member_l1_ids"])
        for group in _active_recording_groups(conn)
    }
    conn.execute("SAVEPOINT l2_track_auto_merge")
    try:
        conn.execute(
            """UPDATE track_groups SET group_status='archived'
                WHERE scope='recording' AND group_status='active'"""
        )
        group_by_member: dict[int, int] = {}
        created = 0
        updated = 0
        for item in plan["groups"]:
            automatic_artist_id = (
                int(item["artist_ids"][0]) if len(item["artist_ids"]) == 1 else None
            )
            automatic_title_key = (
                str(item["normalized_title"]) if automatic_artist_id is not None else None
            )
            automatic_version_tag = (
                "\x1f".join(str(tag) for tag in item["semantic_version_tags"])
                if automatic_artist_id is not None
                else None
            )
            target_group_id = item["target_group_id"]
            if target_group_id is None:
                cursor = conn.execute(
                    """INSERT INTO track_groups(
                           canonical_name, primary_track_id, primary_l1_id,
                           scope, is_manual, group_status,
                           automatic_spotify_track_id, automatic_artist_id,
                           automatic_title_key, automatic_version_tag,
                           identity_policy_version
                       ) VALUES (?, ?, ?, 'recording', 0, 'archived', NULL, ?, ?, ?, ?)""",
                    (
                        str(item["canonical_name"]),
                        int(item["primary_track_id"]),
                        int(item["primary_l1_id"]),
                        automatic_artist_id,
                        automatic_title_key,
                        automatic_version_tag,
                        str(plan["policy_version"]),
                    ),
                )
                target_group_id = int(cursor.lastrowid)
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
                                  automatic_version_tag=?, identity_policy_version=?
                            WHERE group_id=?""",
                        (
                            str(item["canonical_name"]),
                            int(item["primary_track_id"]),
                            int(item["primary_l1_id"]),
                            automatic_artist_id,
                            automatic_title_key,
                            automatic_version_tag,
                            str(plan["policy_version"]),
                            target_group_id,
                        ),
                    )
                else:
                    conn.execute(
                        """UPDATE track_groups SET primary_track_id=?, primary_l1_id=?
                            WHERE group_id=?""",
                        (
                            int(item["primary_track_id"]),
                            int(item["primary_l1_id"]),
                            target_group_id,
                        ),
                    )
            conn.executemany(
                "INSERT INTO track_group_l1_members(group_id, l1_id) VALUES (?, ?)",
                ((target_group_id, int(member)) for member in item["member_l1_ids"]),
            )
            conn.execute(
                "UPDATE track_groups SET group_status='active' WHERE group_id=?",
                (target_group_id,),
            )
            for member in item["member_l1_ids"]:
                group_by_member[int(member)] = target_group_id

        candidate_count = _upsert_candidate_evidence(conn, plan, group_by_member)
        if bump_revision:
            from backend.domains.metadata.track_identity import bump_track_identity_revision

            revision = bump_track_identity_revision(conn)
        else:
            revision = int(plan["track_identity_revision"])
        conn.execute("RELEASE SAVEPOINT l2_track_auto_merge")
        if commit:
            conn.commit()
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT l2_track_auto_merge")
        conn.execute("RELEASE SAVEPOINT l2_track_auto_merge")
        raise

    after_groups = {
        int(group["group_id"]): set(group["member_l1_ids"])
        for group in _active_recording_groups(conn)
    }
    before_pairs = {
        (group_id, member) for group_id, members in before_groups.items() for member in members
    }
    after_pairs = {
        (group_id, member) for group_id, members in after_groups.items() for member in members
    }
    return {
        "status": "applied",
        "changed": True,
        "policy_version": plan["policy_version"],
        "group_count": len(after_groups),
        "groups_created": created,
        "groups_updated": updated,
        "groups_archived": len(plan["archived_group_ids"]),
        "members_added": len(after_pairs - before_pairs),
        "members_removed": len(before_pairs - after_pairs),
        "candidate_evidence_upserted": candidate_count,
        "blocked_edge_count": len(plan["blocked_edges"]),
        "revision_bumped": bump_revision,
        "track_identity_revision": revision,
    }
