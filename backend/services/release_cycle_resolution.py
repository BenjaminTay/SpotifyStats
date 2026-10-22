"""Resolve release anchors from project identity and installed provider evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.domains.metadata.artist_identity import get_artist_identity_map, resolve_artist_names
from backend.domains.metadata.release_dates import parse_release_date, release_anchor_sources
from backend.domains.metadata.spotify_album_credits import AlbumArtistResolver
from backend.domains.playback.album_project_identity import (
    AlbumProjectIdentity,
    _project_rows,
    _resolve_project_rows,
    normalize_album_project_lookup,
    resolve_album_project_identities,
)


@dataclass(frozen=True)
class ReleaseTarget:
    artist_name: str
    album_name: str
    identity: AlbumProjectIdentity | None = None
    artist_display_name: str | None = None
    release_date: str | None = None
    source_album_id: str | None = None
    reason: str | None = None
    requested_project_id: int | None = None

    def unavailable(self) -> dict:
        return {
            **(
                {"project_id": self.requested_project_id}
                if self.requested_project_id is not None
                else {}
            ),
            "artist_name": self.artist_name,
            "album_name": self.album_name,
            "status": "unavailable",
            "reason": self.reason,
        }


def resolve_release_targets(conn, items: list[dict], merge_level: int = 2) -> list[ReleaseTarget]:
    """Never replace a project's primary release with an unrelated namesake.

    Member-name requests keep their explicit edition's source anchor; canonical
    project requests use its primary release. Playback membership remains the
    selected L2/L3 project's membership in both cases.
    """
    identities = resolve_album_project_identities(conn, items, merge_level=merge_level)
    resolver = AlbumArtistResolver(conn)
    # Reuse canonical artist evidence for legacy aliases instead of guessing
    # from provider credit text or dropping the alias at a string comparison.
    artist_targets = resolve_artist_names(conn, [item["artist_name"] for item in items])
    mapping = get_artist_identity_map(conn)
    project_rows = _project_rows(conn)
    for index, (identity, artist) in enumerate(zip(identities, artist_targets)):
        if identity is None and artist is not None and items[index].get("project_id") is None:
            aliases = {
                raw_id
                for raw_id, value in mapping.items()
                if value.canonical_artist_id == artist.canonical_artist_id
            }
            identities[index] = _resolve_project_rows(
                [row for row in project_rows if row["artist_id"] in aliases],
                album_name=items[index]["album_name"],
                merge_level=merge_level,
            )
    result = []
    for item, identity, requested_artist in zip(items, identities, artist_targets):
        values: dict[str, Any] = {
            "artist_name": item["artist_name"],
            "album_name": item["album_name"],
        }
        values["requested_project_id"] = item.get("project_id")
        if identity is None:
            if item.get("project_id") is not None:
                result.append(ReleaseTarget(**values, reason="entity_not_found"))
                continue
            name = normalize_album_project_lookup(item["album_name"])
            matching = [
                row
                for row in project_rows
                if requested_artist is not None
                and row["artist_id"] in mapping
                and mapping[row["artist_id"]].canonical_artist_id
                == requested_artist.canonical_artist_id
                and name
                in {
                    normalize_album_project_lookup(str(row["canonical_name"])),
                    normalize_album_project_lookup(str(row["member_album_name"] or "")),
                }
            ]
            scope = "composition" if merge_level >= 3 else "release"
            preferred = [row for row in matching if row["scope"] == scope]
            matches = {row["project_id"] for row in (preferred or matching)}
            reason = "release_ambiguous" if len(matches) > 1 else "entity_not_found"
            result.append(ReleaseTarget(**values, reason=reason))
            continue
        values["identity"] = identity
        artist = mapping.get(identity.artist_id)
        values["artist_display_name"] = artist.display_name if artist else identity.artist_name
        album_id = identity.matched_album_id or identity.primary_album_id
        album = conn.execute(
            "SELECT album_name FROM albums WHERE album_id=?", (album_id,)
        ).fetchone()
        if album is None:
            result.append(ReleaseTarget(**values, reason="entity_not_found"))
            continue
        rows = release_anchor_sources(
            conn,
            album_id,
            project_id=identity.project_id,
            explicit_edition=identity.matched_album_id is not None,
        )
        if not rows:
            result.append(ReleaseTarget(**values, reason="release_source_unconfirmed"))
            continue
        verified = [
            row
            for row in rows
            if resolver.match(row["spotify_album_id"], identity.artist_id, identity.artist_name)
            == "verified_id"
            or (
                row["project_bound"]
                and resolver.read(row["spotify_album_id"])
                and all(
                    credit["spotify_artist_id"] for credit in resolver.read(row["spotify_album_id"])
                )
            )
        ]
        if not verified:
            result.append(ReleaseTarget(**values, reason="artist_identity_unconfirmed"))
            continue
        if any(row.get("independent_date_conflict") for row in verified):
            result.append(ReleaseTarget(**values, reason="release_date_conflict"))
            continue
        dates = [
            (row, parse_release_date(row["release_date"], row["release_date_precision"]))
            for row in verified
        ]
        confirmed = {
            (value.raw, value.precision) for _, value in dates if value.status == "confirmed"
        }
        exact = {value.exact_day for _, value in dates if value.exact_day is not None}
        if len(exact) > 1 or (
            exact
            and any(
                value.status == "confirmed" and not value.start <= next(iter(exact)) <= value.end
                for _, value in dates
            )
        ):
            result.append(ReleaseTarget(**values, reason="release_date_conflict"))
            continue
        if not exact:
            reason = "release_day_unconfirmed"
            if confirmed:
                reason = "release_date_coarse"
            elif any(value.status in {"invalid", "inconsistent"} for _, value in dates):
                reason = "release_date_invalid"
            result.append(ReleaseTarget(**values, reason=reason))
            continue
        day = next(iter(exact))
        source = next(row for row, value in dates if value.exact_day == day)
        project = conn.execute(
            "SELECT release_date,release_date_precision,is_manual FROM album_projects WHERE project_id=?",
            (identity.project_id,),
        ).fetchone()
        # A confirmed project date is a published anchor, never silently
        # contradicted by a source refresh. Explicit member editions have their
        # own anchors. Manual dates require matching evidence as well.
        if identity.matched_album_id is None and project is not None:
            project_date = parse_release_date(project[0], project[1])
            if (project_date.exact_day and project_date.exact_day != day) or (
                project[2] and project_date.raw != day.isoformat()
            ):
                result.append(ReleaseTarget(**values, reason="release_date_conflict"))
                continue
        result.append(
            ReleaseTarget(
                **values, release_date=day.isoformat(), source_album_id=source["spotify_album_id"]
            )
        )
    return result


def resolve_advance_singles(
    conn, target: ReleaseTarget, source_track_ids: tuple[int, ...]
) -> list[dict]:
    """Resolve shared-song single releases through the installed identity contract.

    A global title match cannot establish an artist, edition or release date.
    Each candidate must own the shared local album and resolve to a confirmed
    single source. Unresolved/conflicting candidates leave the existing impact
    formula's pre-release/all-time baseline fallback available.
    """
    if (
        target.reason
        or target.identity is None
        or target.release_date is None
        or not source_track_ids
    ):
        return []
    candidates = {}
    for offset in range(0, len(source_track_ids), 900):
        chunk = source_track_ids[offset : offset + 900]
        placeholders = ",".join("?" for _ in chunk)
        for row in conn.execute(
            f"""SELECT DISTINCT candidate.album_id,candidate.album_name
            FROM track_albums shared
            JOIN albums candidate ON candidate.album_id=shared.album_id
            WHERE shared.track_id IN ({placeholders})""",
            chunk,
        ):
            candidates[row[0]] = row[1]
    rows = sorted(candidates.items())
    if not rows:
        return []
    items = [{"artist_name": target.identity.artist_name, "album_name": row[1]} for row in rows]
    resolved = resolve_release_targets(conn, items, merge_level=2)
    result = {}
    for row, candidate in zip(rows, resolved):
        if candidate.reason or candidate.identity is None or not candidate.release_date:
            continue
        # The resolver's name compatibility must still refer to this actual
        # shared album, rather than a uniquely named but unrelated catalog row.
        if not conn.execute(
            "SELECT 1 FROM album_project_albums WHERE project_id=? AND album_id=?",
            (candidate.identity.project_id, row[0]),
        ).fetchone():
            continue
        source = conn.execute(
            "SELECT album_type FROM spotify_album_meta WHERE spotify_album_id=?",
            (candidate.source_album_id,),
        ).fetchone()
        if source is None or source[0] != "single" or candidate.release_date >= target.release_date:
            continue
        result[candidate.source_album_id] = {
            "single_name": candidate.album_name,
            "release_date": candidate.release_date,
            "source_album_id": candidate.source_album_id,
        }
    return sorted(result.values(), key=lambda row: (row["release_date"], row["source_album_id"]))
