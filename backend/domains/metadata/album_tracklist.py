"""Read release-local position evidence without network or writes."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from backend.providers.spotify.album_tracks import complete_track_ids


@dataclass(frozen=True)
class ReleasePositionEvidence:
    status: str
    positions: dict = field(default_factory=dict)


def release_position_evidence(conn, spotify_album_id):
    """Trust positions only when the entire evidence matches the current directory.

    last_status describes the latest attempt, not the validity of the retained LKG.
    A failed refresh may therefore still have usable, matching position evidence.
    """
    current = conn.execute(
        "SELECT track_list, total_tracks FROM spotify_album_meta WHERE spotify_album_id=?",
        (spotify_album_id,),
    ).fetchone()
    ids = complete_track_ids(current[0], current[1]) if current else None
    if ids is None:
        return ReleasePositionEvidence("directory_incomplete")
    if not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name='spotify_album_tracklist_evidence'"
    ).fetchone():
        return ReleasePositionEvidence("missing")
    row = conn.execute(
        "SELECT tracks_json, validated_total FROM spotify_album_tracklist_evidence WHERE spotify_album_id=?",
        (spotify_album_id,),
    ).fetchone()
    if not row or not row[0]:
        return ReleasePositionEvidence("missing")
    try:
        tracks = json.loads(row[0])
    except (TypeError, ValueError):
        return ReleasePositionEvidence("invalid")
    evidence_ids = complete_track_ids(tracks, row[1])
    if evidence_ids is None:
        return ReleasePositionEvidence("invalid")
    if row[1] != current[1] or evidence_ids != ids:
        return ReleasePositionEvidence("mismatch")
    previous = (0, 0)
    for index, track in enumerate(tracks):
        if (
            not isinstance(track, dict)
            or track.get("id") != ids[index]
            or not isinstance(track.get("name"), str)
            or not track["name"].strip()
        ):
            return ReleasePositionEvidence("invalid")
        disc, number = track.get("disc_number"), track.get("track_number")
        if type(disc) is not int or type(number) is not int or disc <= 0 or number <= 0:
            return ReleasePositionEvidence("invalid")
        if (disc, number) <= previous:
            return ReleasePositionEvidence("invalid")
        previous = (disc, number)
    return ReleasePositionEvidence("complete", {i: track for i, track in enumerate(tracks)})


def release_positions(conn, spotify_album_id):
    return release_position_evidence(conn, spotify_album_id).positions


def select_missing_position_evidence_ids(conn, limit=50):
    """Opt-in bounded maintenance candidates linked to actual playback.

    Complete legacy directories remain usable for membership. They are not part
    of the normal missing-directory refresh queue merely because positions lack
    evidence. Explicit Spotify IDs can also be repaired regardless of playback.
    """
    rows = conn.execute(
        """SELECT sam.spotify_album_id FROM spotify_album_meta sam
        WHERE EXISTS (SELECT 1 FROM album_spotify_links links
                      JOIN plays p ON p.source_album_id=links.album_id
                      WHERE links.spotify_album_id=sam.spotify_album_id)
           OR EXISTS (SELECT 1 FROM spotify_track_meta stm
                      JOIN tracks t ON t.spotify_track_id=stm.spotify_track_id
                      JOIN plays p ON p.track_id=t.track_id
                      WHERE stm.spotify_album_id=sam.spotify_album_id)
        ORDER BY sam.spotify_album_id"""
    )
    result = []
    for (sid,) in rows:
        status = release_position_evidence(conn, sid).status
        if status not in {"complete", "directory_incomplete"}:
            result.append(sid)
            if len(result) >= limit:
                break
    return result
