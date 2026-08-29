"""Self-replacement #1 and blocker king Billboard record families."""

import pandas as pd

from backend.core.db import fan_out_weekly_for_artists
from backend.domains.billboard.record_sorting import stable_record_sort


def compute_self_replacement_blocker_records(
    records,
    weekly,
    track_summary,
    weekly_album=None,
    weekly_artist=None,
    track_power_scores=None,
    album_power_scores=None,
    artist_power_scores=None,
):
    """Populate self-replacement at #1 and blocker king records."""

    # ── 15. Self-Replacement at #1 (冠军传承) ────────────────────────────
    no1_all = (
        weekly[weekly["rank"] == 1][["billboard_week", "track_id", "track_name", "artist_name"]]
        .drop_duplicates()
        .sort_values("billboard_week")
    )
    no1_credits = fan_out_weekly_for_artists(weekly[weekly["rank"] == 1])[
        ["billboard_week", "track_id", "artist_name"]
    ].drop_duplicates()
    artist_sets = (
        no1_credits.groupby(["billboard_week", "track_id"])["artist_name"].agg(set).to_dict()
    )
    replacements = []
    for i in range(1, len(no1_all)):
        prev = no1_all.iloc[i - 1]
        curr = no1_all.iloc[i]
        gap = (curr["billboard_week"] - prev["billboard_week"]).days
        shared_artists = artist_sets.get(
            (prev["billboard_week"], prev["track_id"]), set()
        ) & artist_sets.get((curr["billboard_week"], curr["track_id"]), set())
        if gap <= 8 and shared_artists and prev["track_id"] != curr["track_id"]:
            replacements.append(
                {
                    "周次": curr["billboard_week"],
                    "艺人": ", ".join(sorted(shared_artists)),
                    "前冠单_id": prev["track_id"],
                    "前冠单": prev["track_name"],
                    "新冠单_id": curr["track_id"],
                    "新冠单": curr["track_name"],
                }
            )
    records["self_replacement_no1"] = stable_record_sort(
        pd.DataFrame(replacements),
        [("周次", False)],
        stable_columns=("新冠单_id", "艺人", "前冠单_id", "新冠单"),
    )
    # Album version
    if weekly_album is not None:
        alb_no1_all = (
            weekly_album[weekly_album["rank"] == 1][["billboard_week", "album_name", "artist_name"]]
            .drop_duplicates()
            .sort_values("billboard_week")
        )
        alb_replacements = []
        for i in range(1, len(alb_no1_all)):
            prev = alb_no1_all.iloc[i - 1]
            curr = alb_no1_all.iloc[i]
            gap = (curr["billboard_week"] - prev["billboard_week"]).days
            if (
                gap <= 8
                and prev["artist_name"] == curr["artist_name"]
                and prev["album_name"] != curr["album_name"]
            ):
                alb_replacements.append(
                    {
                        "周次": curr["billboard_week"],
                        "艺人": curr["artist_name"],
                        "前冠专": prev["album_name"],
                        "新冠专": curr["album_name"],
                    }
                )
        records["self_replacement_no1_album"] = stable_record_sort(
            pd.DataFrame(alb_replacements),
            [("周次", False)],
            stable_columns=("新冠专", "艺人", "前冠专"),
        )
    else:
        records["self_replacement_no1_album"] = pd.DataFrame()

    # ── 16. Blocker King — #1 that blocked most #2 challengers (阻挡王) ─
    no1_weeks_all = weekly[weekly["rank"] == 1][["track_id", "billboard_week"]].drop_duplicates()
    no2_at_no1 = weekly[weekly["rank"] == 2][
        ["track_id", "track_name", "artist_name", "billboard_week"]
    ].drop_duplicates()
    if not no1_weeks_all.empty and not no2_at_no1.empty:
        merged_block = no1_weeks_all.merge(
            no2_at_no1, on="billboard_week", suffixes=("_no1", "_no2")
        )
        # Only count blocked songs that peaked at #2 (never reached #1)
        track_peaks = track_summary.set_index("track_id")["peak_position"].to_dict()
        merged_block["_peak_no2"] = merged_block["track_id_no2"].map(track_peaks)
        merged_block_true = merged_block[merged_block["_peak_no2"] == 2]
        blocker = (
            merged_block_true.groupby("track_id_no1")
            .agg(阻挡数=("track_id_no2", "nunique"))
            .reset_index()
        )
        blocker = blocker.merge(
            track_summary[["track_id", "track_name", "artist_name"]],
            left_on="track_id_no1",
            right_on="track_id",
            how="left",
        )
        # Merge power scores for secondary sort
        if track_power_scores is not None:
            blocker = blocker.merge(
                track_power_scores[["track_id", "power_score"]].rename(
                    columns={"power_score": "走势评分"}
                ),
                on="track_id",
                how="left",
            )
            blocker["走势评分"] = blocker["走势评分"].fillna(0).astype(int)
        else:
            blocker["走势评分"] = 0
        blocker = stable_record_sort(
            blocker,
            [("阻挡数", False), ("走势评分", False)],
            stable_columns=("track_id", "artist_name", "track_name"),
            limit=20,
        )
        records["blocker_king"] = blocker[
            ["track_id", "track_name", "artist_name", "阻挡数", "走势评分"]
        ]
        # Blocked tracks detail: for each #1 track, list the #2 tracks it blocked
        blocked_detail = (
            merged_block_true.groupby("track_id_no1")
            .apply(
                lambda g: [
                    {
                        "track_id": int(r["track_id_no2"]),
                        "track_name": str(r["track_name"]),
                        "artist_name": str(r["artist_name"]),
                    }
                    for r in g.drop_duplicates(subset=["track_id_no2"]).to_dict("records")
                ],
                include_groups=False,
            )
            .to_dict()
        )
        records["blocked_tracks_map"] = blocked_detail
    else:
        records["blocker_king"] = pd.DataFrame()
        records["blocked_tracks_map"] = {}

    # ── 16b. Album Blocker King — #1 album that blocked most #2 challengers ─
    if weekly_album is not None:
        alb_no1_weeks_all = weekly_album[weekly_album["rank"] == 1][
            ["album_name", "artist_name", "billboard_week"]
        ].drop_duplicates()
        alb_no2_at_no1 = weekly_album[weekly_album["rank"] == 2][
            ["album_name", "artist_name", "billboard_week"]
        ].drop_duplicates()
        if not alb_no1_weeks_all.empty and not alb_no2_at_no1.empty:
            alb_merged = alb_no1_weeks_all.merge(
                alb_no2_at_no1, on="billboard_week", suffixes=("_no1", "_no2")
            )
            # Only count blocked albums that peaked at #2
            if weekly_album is not None:
                album_peak_map = (
                    weekly_album.groupby(["album_name", "artist_name"])["rank"].min().to_dict()
                )
                alb_merged["_peak_no2"] = alb_merged.apply(
                    lambda r: album_peak_map.get((r["album_name_no2"], r["artist_name_no2"]), 99),
                    axis=1,
                )
            else:
                alb_merged["_peak_no2"] = 99
            alb_merged_true = alb_merged[alb_merged["_peak_no2"] == 2]
            if not alb_merged_true.empty:
                alb_blocker = (
                    alb_merged_true.groupby(["album_name_no1", "artist_name_no1"])
                    .agg(阻挡数=("album_name_no2", "nunique"))
                    .reset_index()
                )
                alb_blocker = alb_blocker.rename(
                    columns={
                        "album_name_no1": "album_name",
                        "artist_name_no1": "artist_name",
                    }
                )
                # Merge album power scores for secondary sort
                if album_power_scores is not None:
                    alb_blocker = alb_blocker.merge(
                        album_power_scores[["album_name", "artist_name", "power_score"]].rename(
                            columns={"power_score": "走势评分"}
                        ),
                        on=["album_name", "artist_name"],
                        how="left",
                    )
                    alb_blocker["走势评分"] = alb_blocker["走势评分"].fillna(0).astype(int)
                else:
                    alb_blocker["走势评分"] = 0
                alb_blocker = stable_record_sort(
                    alb_blocker,
                    [("阻挡数", False), ("走势评分", False)],
                    stable_columns=("album_name", "artist_name"),
                    limit=20,
                )
                records["blocker_king_album"] = alb_blocker[
                    ["album_name", "artist_name", "阻挡数", "走势评分"]
                ]
                # Blocked albums detail (string key: "album||artist")
                alb_blocked_detail = {}
                for (aname, aname_artist), grp in alb_merged_true.groupby(
                    ["album_name_no1", "artist_name_no1"]
                ):
                    alb_blocked_detail[f"{aname}||{aname_artist}"] = [
                        {
                            "album_name": str(r["album_name_no2"]),
                            "artist_name": str(r["artist_name_no2"]),
                        }
                        for r in grp.drop_duplicates(
                            subset=["album_name_no2", "artist_name_no2"]
                        ).to_dict("records")
                    ]
                records["blocked_albums_map"] = alb_blocked_detail
            else:
                records["blocker_king_album"] = pd.DataFrame()
                records["blocked_albums_map"] = {}
        else:
            records["blocker_king_album"] = pd.DataFrame()
            records["blocked_albums_map"] = {}
    else:
        records["blocker_king_album"] = pd.DataFrame()
        records["blocked_albums_map"] = {}

    # ── 16c. Artist Blocker King — #1 artist that blocked most #2 artists ─
    if weekly_artist is not None:
        art_no1_weeks_all = weekly_artist[weekly_artist["rank"] == 1][
            ["artist_name", "billboard_week"]
        ].drop_duplicates()
        art_no2_at_no1 = weekly_artist[weekly_artist["rank"] == 2][
            ["artist_name", "billboard_week"]
        ].drop_duplicates()
        if not art_no1_weeks_all.empty and not art_no2_at_no1.empty:
            art_merged = art_no1_weeks_all.merge(
                art_no2_at_no1, on="billboard_week", suffixes=("_no1", "_no2")
            )
            # Only count blocked artists that peaked at #2
            artist_peak_map = weekly_artist.groupby("artist_name")["rank"].min().to_dict()
            art_merged["_peak_no2"] = art_merged["artist_name_no2"].map(artist_peak_map)
            art_merged_true = art_merged[art_merged["_peak_no2"] == 2]
            if not art_merged_true.empty:
                art_blocker = (
                    art_merged_true.groupby("artist_name_no1")
                    .agg(阻挡数=("artist_name_no2", "nunique"))
                    .reset_index()
                )
                art_blocker = art_blocker.rename(columns={"artist_name_no1": "artist_name"})
                if artist_power_scores is not None:
                    art_blocker = art_blocker.merge(
                        artist_power_scores[["artist_name", "power_score"]].rename(
                            columns={"power_score": "走势评分"}
                        ),
                        on="artist_name",
                        how="left",
                    )
                    art_blocker["走势评分"] = art_blocker["走势评分"].fillna(0).astype(int)
                else:
                    art_blocker["走势评分"] = 0
                art_blocker = stable_record_sort(
                    art_blocker,
                    [("阻挡数", False), ("走势评分", False)],
                    stable_columns=("artist_name",),
                    limit=20,
                )
                records["blocker_king_artist"] = art_blocker[["artist_name", "阻挡数", "走势评分"]]
                art_blocked_detail = {}
                for aname, grp in art_merged_true.groupby("artist_name_no1"):
                    art_blocked_detail[aname] = [
                        {"artist_name": str(r["artist_name_no2"])}
                        for r in grp.drop_duplicates(subset=["artist_name_no2"]).to_dict("records")
                    ]
                records["blocked_artists_map"] = art_blocked_detail
            else:
                records["blocker_king_artist"] = pd.DataFrame()
                records["blocked_artists_map"] = {}
        else:
            records["blocker_king_artist"] = pd.DataFrame()
            records["blocked_artists_map"] = {}
    else:
        records["blocker_king_artist"] = pd.DataFrame()
        records["blocked_artists_map"] = {}
