import pandas as pd

from backend.domains.billboard.records_championship import compute_championship_records
from backend.domains.billboard.records_longevity import compute_longevity_records
from backend.domains.billboard.records_movement import compute_movement_records
from backend.domains.billboard.records_quirky import compute_quirky_records
from backend.domains.billboard.records_self_replacement_blocker import (
    compute_self_replacement_blocker_records,
)


def _weekly_rows():
    return pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-04"),
                "track_id": 1,
                "track_name": "Collab #1",
                "artist_name": "Taylor Swift, Ed Sheeran",
                "artist_names": ["Taylor Swift", "Ed Sheeran"],
                "album_name": "Album",
                "rank": 1,
                "play_count": 100,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-04"),
                "track_id": 3,
                "track_name": "Taylor Solo",
                "artist_name": "Taylor Swift",
                "artist_names": ["Taylor Swift"],
                "album_name": "Album",
                "rank": 2,
                "play_count": 90,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-11"),
                "track_id": 1,
                "track_name": "Collab #1",
                "artist_name": "Taylor Swift, Ed Sheeran",
                "artist_names": ["Taylor Swift", "Ed Sheeran"],
                "album_name": "Album",
                "rank": 2,
                "play_count": 80,
            },
            {
                "billboard_week": pd.Timestamp("2024-01-11"),
                "track_id": 2,
                "track_name": "Taylor New #1",
                "artist_name": "Taylor Swift",
                "artist_names": ["Taylor Swift"],
                "album_name": "Album",
                "rank": 1,
                "play_count": 110,
            },
        ]
    )


def _track_summary():
    return pd.DataFrame(
        [
            {
                "track_id": 1,
                "track_name": "Collab #1",
                "artist_name": "Taylor Swift, Ed Sheeran",
                "artist_names": ["Taylor Swift", "Ed Sheeran"],
                "peak_position": 1,
                "weeks_at_no1": 1,
                "weeks_on_chart": 2,
                "first_week": pd.Timestamp("2024-01-04"),
                "first_peak_week": pd.Timestamp("2024-01-04"),
                "last_week": pd.Timestamp("2024-01-11"),
            },
            {
                "track_id": 2,
                "track_name": "Taylor New #1",
                "artist_name": "Taylor Swift",
                "artist_names": ["Taylor Swift"],
                "peak_position": 1,
                "weeks_at_no1": 1,
                "weeks_on_chart": 1,
                "first_week": pd.Timestamp("2024-01-11"),
                "first_peak_week": pd.Timestamp("2024-01-11"),
                "last_week": pd.Timestamp("2024-01-11"),
            },
            {
                "track_id": 3,
                "track_name": "Taylor Solo",
                "artist_name": "Taylor Swift",
                "artist_names": ["Taylor Swift"],
                "peak_position": 2,
                "weeks_at_no1": 0,
                "weeks_on_chart": 1,
                "first_week": pd.Timestamp("2024-01-04"),
                "first_peak_week": pd.Timestamp("2024-01-04"),
                "last_week": pd.Timestamp("2024-01-04"),
            },
        ]
    )


def test_championship_counts_every_credited_artist_once():
    records = {}
    compute_championship_records(records, _weekly_rows(), _track_summary())

    rows = records["artist_most_no1"].set_index("artist_name")
    assert int(rows.loc["Taylor Swift", "冠单数"]) == 2
    assert int(rows.loc["Ed Sheeran", "冠单数"]) == 1
    assert int(rows.loc["Taylor Swift", "单曲冠军周数"]) == 2
    assert int(rows.loc["Ed Sheeran", "单曲冠军周数"]) == 1

    simul = records["artist_simul_list"]
    assert int(simul.loc[simul["artist_name"] == "Taylor Swift", "track_count"].max()) == 2


def test_championship_artist_lists_are_stable_under_input_permutation():
    expected = None
    for weekly in (_weekly_rows(), _weekly_rows().sample(frac=1, random_state=17)):
        records = {}
        compute_championship_records(records, weekly, _track_summary())
        current = {
            "most_no1": records["artist_most_no1"][
                ["artist_name", "冠单数", "单曲冠军周数"]
            ].to_dict("records"),
            "simul": records["artist_simul_list"][
                ["billboard_week", "artist_name", "track_count"]
            ].to_dict("records"),
        }
        if expected is None:
            expected = current
        else:
            assert current == expected


def test_self_replacement_matches_shared_credited_artist():
    weekly = _weekly_rows().query("track_id in [1, 2]").copy()
    weekly.loc[weekly["track_id"] == 1, "billboard_week"] = pd.Timestamp("2024-01-04")
    weekly.loc[weekly["track_id"] == 2, "billboard_week"] = pd.Timestamp("2024-01-11")
    track_one_index = weekly.index[weekly["track_id"] == 1][0]
    weekly.at[track_one_index, "artist_name"] = "Taylor Swift"
    weekly.at[track_one_index, "artist_names"] = ["Taylor Swift"]
    weekly.loc[weekly["track_id"] == 2, "artist_name"] = "Taylor Swift, Ed Sheeran"
    track_two_index = weekly.index[weekly["track_id"] == 2][0]
    weekly.at[track_two_index, "artist_names"] = ["Taylor Swift", "Ed Sheeran"]

    records = {}
    compute_self_replacement_blocker_records(records, weekly, _track_summary())

    assert len(records["self_replacement_no1"]) == 1
    assert records["self_replacement_no1"].iloc[0]["艺人"] == "Taylor Swift"


def test_movement_and_longevity_use_credited_artist_keys():
    weekly = _weekly_rows()
    track_summary = _track_summary()

    movement_records = {}
    compute_movement_records(movement_records, weekly, track_summary)
    assert movement_records["most_top10_simul"]["artist"] == "Taylor Swift"
    assert movement_records["most_top10_simul"]["count"] == 2

    longevity_records = {}
    compute_longevity_records(longevity_records, weekly, track_summary)
    span = longevity_records["longest_artist_span"]
    taylor = span.loc[span["artist_name"] == "Taylor Swift"].iloc[0]
    assert int(taylor["上榜歌曲数"]) == 3


def test_triple_no1_uses_credited_track_artist_not_display_label():
    weekly = _weekly_rows().query("track_id == 1").iloc[[0]].copy()
    weekly_album = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-04"),
                "album_name": "Album",
                "artist_name": "Taylor Swift",
                "rank": 1,
            }
        ]
    )
    weekly_artist = pd.DataFrame(
        [
            {
                "billboard_week": pd.Timestamp("2024-01-04"),
                "artist_name": "Taylor Swift",
                "rank": 1,
            }
        ]
    )

    records = {}
    compute_quirky_records(records, weekly, weekly_album, weekly_artist)

    assert len(records["triple_no1"]) == 1
    assert records["triple_no1"].iloc[0]["艺人"] == "Taylor Swift"
