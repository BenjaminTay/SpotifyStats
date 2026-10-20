"""Chart performances must follow complete song identity, not its display release."""

import pandas as pd
import pytest

from backend.core.db import get_db
from backend.domains.billboard.album_membership import load_chart_album_membership
from backend.domains.billboard.chart_summaries import compute_album_track_counts
from backend.domains.playback.album_projects import load_album_project_membership

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("representative", [905, 906])
def test_recording_owner_survives_representative_release_and_credit_changes(
    use_seed_db, representative
):
    # Remove only the single-side project candidate. The other recording member
    # remains in the album, even when the representative has no valid plays.
    conn = get_db(readonly=False)
    conn.execute("DELETE FROM album_project_tracks WHERE track_id=906")
    conn.execute(
        "UPDATE track_groups SET primary_track_id=?,primary_l1_id=? WHERE group_id=1",
        (representative, representative),
    )
    conn.commit()
    expected = load_album_project_membership(conn, 2, False)
    expected = expected[expected["canonical_song_key"] == f"group:{representative}"].iloc[0]
    conn.close()
    summary = pd.DataFrame(
        [
            dict(
                track_id=representative,
                track_name="Fixture Recording Song",
                artist_name="Corrected Performer, Guest",
                album_name="Standalone Single",
                peak_position=3,
                weeks_on_chart=3,
                weeks_at_no1=0,
            )
        ]
    )
    membership = load_chart_album_membership(summary, 2, False)
    assert len(membership) == 1
    assert membership.iloc[0]["album_project_id"] == expected["project_id"]
    weekly = pd.DataFrame(
        [
            dict(
                album_project_id=int(expected["project_id"]),
                album_name=expected["album_project_name"],
                artist_name=expected["artist_name"],
                rank=1,
                billboard_week="2026-03-06",
            )
        ]
    )
    counts, tracks = compute_album_track_counts(summary, membership, weekly)
    assert counts.iloc[0]["total_tracks"] == 1
    assert counts.iloc[0]["artist_name"] == expected["artist_name"]
    assert tracks.iloc[0]["artist_name"] == "Corrected Performer, Guest"
    assert tracks.iloc[0]["peak_position"] == 3


@pytest.mark.parametrize("level", [2, 3])
@pytest.mark.parametrize("compilations", [False, True])
def test_chart_binding_matches_formal_owner_and_exclusions(seed_conn, level, compilations):
    tracks = pd.read_sql_query(
        "SELECT l1_id AS track_id,t.track_name FROM track_l1_identities li JOIN tracks t ON t.track_id=li.representative_track_id",
        seed_conn,
    )
    membership = load_chart_album_membership(tracks, level, compilations)
    expected = load_album_project_membership(seed_conn, level, compilations)
    assert not membership.duplicated("track_id").any()
    assert set(zip(membership.canonical_song_key, membership.album_project_id)) == set(
        zip(expected.canonical_song_key, expected.project_id)
    )


def test_detail_overlay_keys_use_the_same_owner(seed_conn):
    import json
    from types import SimpleNamespace

    from backend.domains.music_search.detail_projection import build_entity_projections

    context = SimpleNamespace(merge_level=2, include_compilations=False)
    projections = {
        (kind, key): json.loads(payload)
        for kind, key, payload in build_entity_projections(seed_conn, context)
    }
    for (kind, project_id), members in projections.items():
        if kind == "membership":
            for member in members:
                for l1 in member["l1_ids"]:
                    assert (
                        projections[("track_album_owner", int(l1))]["album_project_id"]
                        == project_id
                    )
            assert projections[("album_track_keys", project_id)] == sorted(
                {int(l1) for member in members for l1 in member["l1_ids"]}
            )
