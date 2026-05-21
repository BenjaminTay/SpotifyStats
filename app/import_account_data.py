"""Import Spotify Account Data JSON files into the SQLite database.

Each JSON source has its own import function for modularity. import_all()
aggregates all imports and returns summary statistics.
"""

import json
import os
from typing import Any, Optional

from .db import get_db
from .utils import convert_to_local_time

ACCOUNT_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "data", "account",
)


# ═══════════════════════════════════════════════════════════════════════════
# Wrapped 2025
# ═══════════════════════════════════════════════════════════════════════════

def import_wrapped_2025(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import Wrapped2025.json into wrapped_* tables."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "Wrapped2025.json")
    if not os.path.exists(filepath):
        return {"error": "Wrapped2025.json not found"}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    # topArtists
    conn.execute("DELETE FROM wrapped_top_artists")
    ta = data.get("topArtists", {})
    uris = ta.get("topArtistUris", [])
    ms_played = ta.get("topArtistMsPlayed", 0)
    percentile = ta.get("topNPercentileFan", 0)
    for i, uri in enumerate(uris, 1):
        conn.execute(
            "INSERT INTO wrapped_top_artists(rank, artist_uri, ms_played, percentile) VALUES (?, ?, ?, ?)",
            (i, uri, ms_played if i == 1 else 0, percentile),
        )

    # topTracks
    conn.execute("DELETE FROM wrapped_top_tracks")
    for i, t in enumerate(data.get("topTracks", {}).get("topTracks", []), 1):
        conn.execute(
            "INSERT INTO wrapped_top_tracks(rank, track_uri, play_count, ms_played) VALUES (?, ?, ?, ?)",
            (i, t.get("trackUri", ""), t.get("count", 0), t.get("msPlayed", 0)),
        )

    # topAlbums
    conn.execute("DELETE FROM wrapped_top_albums")
    ta_data = data.get("topAlbums", {})
    for i, uri in enumerate(ta_data.get("topAlbums", []), 1):
        conn.execute(
            "INSERT INTO wrapped_top_albums(rank, album_uri, play_count, ms_played) VALUES (?, ?, ?, ?)",
            (i, uri, 0, ta_data.get("topAlbumTimePlayed", 0) if i == 1 else 0),
        )

    # artistRace
    conn.execute("DELETE FROM wrapped_artist_race")
    for a in data.get("topArtistRace", {}).get("topArtists", []):
        for m in a.get("monthsStats", []):
            conn.execute(
                "INSERT INTO wrapped_artist_race(artist_uri, month, rank, trail_size) VALUES (?, ?, ?, ?)",
                (a.get("artistUri", ""), m.get("month", ""), m.get("rank", 0), m.get("trailSize", "")),
            )

    # clubs
    conn.execute("DELETE FROM wrapped_clubs")
    clubs = data.get("clubs", {})
    for uri in clubs.get("artists", []):
        conn.execute(
            "INSERT INTO wrapped_clubs(club_name, percent_in_club, role, artist_uri) VALUES (?, ?, ?, ?)",
            (clubs.get("userClub", ""), clubs.get("percentInClub", 0), clubs.get("role", ""), uri),
        )

    # party
    conn.execute("DELETE FROM wrapped_party")
    party = data.get("party", {})
    scalar_keys = [
        "avgTrackPopularityScore", "numSharesAllContent", "numListenedAlbums",
        "multilinguistRankingScore", "percentListenedExplicit", "absoluteChaosRankingScore",
        "percentListenedNight", "totalNumListeningMinutes", "totalNumListeningDays",
        "streakNumListeningDays", "numArtistsDiscovered", "percentHappyTracks",
        "percentLoveTracks", "percentPartyTracks",
    ]
    for k in scalar_keys:
        if k in party and not isinstance(party[k], (list, dict)):
            conn.execute(
                "INSERT INTO wrapped_party(metric, value) VALUES (?, ?)",
                (k, float(party[k])),
            )
    # Also store totalNumArtists and numUniqueTracks from top-level
    if "topTracks" in data:
        conn.execute(
            "INSERT OR REPLACE INTO wrapped_party(metric, value) VALUES (?, ?)",
            ("numUniqueTracks", float(data["topTracks"].get("numUniqueTracks", 0))),
        )
    if "topArtists" in data:
        conn.execute(
            "INSERT OR REPLACE INTO wrapped_party(metric, value) VALUES (?, ?)",
            ("numUniqueArtists", float(data["topArtists"].get("numUniqueArtists", 0))),
        )

    # listeningAge
    conn.execute("DELETE FROM wrapped_listening_age")
    la = data.get("listeningAge", {})
    conn.execute(
        "INSERT INTO wrapped_listening_age(listening_age, window_start_year, decade_phase) VALUES (?, ?, ?)",
        (la.get("listeningAge", 0), la.get("windowStartYear", 0), la.get("decadePhase", "")),
    )

    # archiveReports
    conn.execute("DELETE FROM wrapped_archive_reports")
    for r in data.get("archiveReports", {}).get("archiveReports", []):
        conn.execute(
            """INSERT INTO wrapped_archive_reports(column_qualifier, title, description, reason, minutes_listened, filed_under_tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (r.get("columnQualifier", ""), r.get("title", ""), r.get("description", ""),
             r.get("reason", ""), r.get("minutesListened", 0),
             json.dumps(r.get("filedUnderTags", []), ensure_ascii=False)),
        )

    # topGenres
    conn.execute("DELETE FROM wrapped_top_genres")
    for i, uri in enumerate(data.get("topGenres", {}).get("topGenres", []), 1):
        conn.execute("INSERT INTO wrapped_top_genres(rank, genre_uri) VALUES (?, ?)", (i, uri))

    # topPodcasts
    conn.execute("DELETE FROM wrapped_top_podcasts")
    for i, uri in enumerate(data.get("topPodcasts", {}).get("topPodcastsUri", []), 1):
        conn.execute("INSERT INTO wrapped_top_podcasts(rank, podcast_uri) VALUES (?, ?)", (i, uri))

    conn.commit()
    if close_conn:
        conn.close()
    return {
        "top_artists": len(uris),
        "top_tracks": len(data.get("topTracks", {}).get("topTracks", [])),
        "artist_race_months": len(data.get("topArtistRace", {}).get("topArtists", [])) * 11,
        "archive_reports": len(data.get("archiveReports", {}).get("archiveReports", [])),
    }


# ═══════════════════════════════════════════════════════════════════════════
# Your Library
# ═══════════════════════════════════════════════════════════════════════════

def import_your_library(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import YourLibrary.json into saved_* and banned_items tables."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "YourLibrary.json")
    if not os.path.exists(filepath):
        return {"error": "YourLibrary.json not found"}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    # saved tracks
    conn.execute("DELETE FROM saved_tracks")
    count_tracks = 0
    for item in data.get("tracks", []):
        conn.execute(
            "INSERT INTO saved_tracks(track_uri, track_name, artist_name, album_name) VALUES (?, ?, ?, ?)",
            (item.get("uri", ""), item.get("track", ""), item.get("artist", ""), item.get("album", "")),
        )
        count_tracks += 1

    # saved albums
    conn.execute("DELETE FROM saved_albums")
    count_albums = 0
    for item in data.get("albums", []):
        conn.execute(
            "INSERT INTO saved_albums(album_uri, album_name, artist_name) VALUES (?, ?, ?)",
            (item.get("uri", ""), item.get("album", ""), item.get("artist", "")),
        )
        count_albums += 1

    # saved artists
    conn.execute("DELETE FROM saved_artists")
    count_artists = 0
    for item in data.get("artists", []):
        conn.execute(
            "INSERT INTO saved_artists(artist_uri, artist_name) VALUES (?, ?)",
            (item.get("uri", ""), item.get("name", "")),
        )
        count_artists += 1

    # saved shows
    conn.execute("DELETE FROM saved_shows")
    count_shows = 0
    for item in data.get("shows", []):
        conn.execute(
            "INSERT INTO saved_shows(show_uri, show_name, publisher) VALUES (?, ?, ?)",
            (item.get("uri", ""), item.get("name", ""), item.get("publisher", "")),
        )
        count_shows += 1

    # banned items
    conn.execute("DELETE FROM banned_items")
    count_banned = 0
    for item in data.get("bannedTracks", []):
        conn.execute(
            "INSERT INTO banned_items(uri, item_name, item_type) VALUES (?, ?, 'track')",
            (item.get("uri", ""), item.get("track", "")),
        )
        count_banned += 1
    for item in data.get("bannedArtists", []):
        conn.execute(
            "INSERT INTO banned_items(uri, item_name, item_type) VALUES (?, ?, 'artist')",
            (item.get("uri", ""), item.get("name", "")),
        )
        count_banned += 1

    conn.commit()
    if close_conn:
        conn.close()
    return {
        "tracks": count_tracks,
        "albums": count_albums,
        "artists": count_artists,
        "shows": count_shows,
        "banned": count_banned,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Playlists
# ═══════════════════════════════════════════════════════════════════════════

def import_playlists(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import Playlist1.json into playlists + playlist_tracks tables."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "Playlist1.json")
    if not os.path.exists(filepath):
        return {"error": "Playlist1.json not found"}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM playlist_tracks")
    conn.execute("DELETE FROM playlists")

    playlists = data.get("playlists", [])
    playlist_count = 0
    track_count = 0

    for pl in playlists:
        conn.execute(
            "INSERT INTO playlists(playlist_name, last_modified_date, track_count, follower_count) VALUES (?, ?, ?, ?)",
            (pl.get("name", ""), pl.get("lastModifiedDate", ""),
             len(pl.get("items", [])), pl.get("numberOfFollowers", 0)),
        )
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        for item in pl.get("items", []):
            t = item.get("track", {})
            if t:
                conn.execute(
                    "INSERT INTO playlist_tracks(playlist_id, track_uri, track_name, artist_name, album_name, added_date) VALUES (?, ?, ?, ?, ?, ?)",
                    (pid, t.get("trackUri", ""), t.get("trackName", ""),
                     t.get("artistName", ""), t.get("albumName", ""),
                     item.get("addedDate", "")),
                )
                track_count += 1

        playlist_count += 1

    conn.commit()
    if close_conn:
        conn.close()
    return {"playlists": playlist_count, "playlist_tracks": track_count}


# ═══════════════════════════════════════════════════════════════════════════
# Search Queries
# ═══════════════════════════════════════════════════════════════════════════

def import_search_queries(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import SearchQueries.json into search_queries table."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "SearchQueries.json")
    if not os.path.exists(filepath):
        return {"error": "SearchQueries.json not found"}

    with open(filepath, encoding="utf-8") as f:
        records = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM search_queries")

    for rec in records:
        raw_time = rec.get("searchTime", "")
        # Parse "2026-02-19T14:21:59.403Z[UTC]" format
        time_info = convert_to_local_time(raw_time.replace("Z[UTC]", "Z"), "")

        interaction_uri = ""
        uris = rec.get("searchInteractionURIs", [])
        if uris:
            interaction_uri = uris[0]

        conn.execute(
            """INSERT INTO search_queries(query_text, search_time_utc, search_date, search_hour, search_dow, platform, interaction_uri)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (rec.get("searchQuery", ""), raw_time, time_info.get("ts_date", ""),
             time_info.get("ts_hour", 0), time_info.get("ts_dow", 0),
             rec.get("platform", ""), interaction_uri),
        )

    conn.commit()
    if close_conn:
        conn.close()
    return {"queries": len(records)}


# ═══════════════════════════════════════════════════════════════════════════
# Inferences
# ═══════════════════════════════════════════════════════════════════════════

def _classify_inference(text: str) -> str:
    """Classify an inference tag into a category."""
    if "ArtistAffinity_" in text:
        return "artist_affinity"
    if text.startswith("1P_Custom_"):
        return "first_party"
    if text.startswith("2P_"):
        return "third_party"
    if text.startswith("Interest |"):
        return "interest"
    if text.startswith("Custom Audience_"):
        return "custom_audience"
    return "other"


def import_inferences(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import Inferences.json into inferences table."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "Inferences.json")
    if not os.path.exists(filepath):
        return {"error": "Inferences.json not found"}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM inferences")

    inferences = data.get("inferences", [])
    for text in inferences:
        category = _classify_inference(text)
        conn.execute(
            "INSERT INTO inferences(inference_text, category) VALUES (?, ?)",
            (text, category),
        )

    conn.commit()
    if close_conn:
        conn.close()
    return {"inferences": len(inferences)}


# ═══════════════════════════════════════════════════════════════════════════
# Sound Capsule
# ═══════════════════════════════════════════════════════════════════════════

def import_sound_capsule(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import YourSoundCapsule.json into sound_capsule_* tables."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "YourSoundCapsule.json")
    if not os.path.exists(filepath):
        return {"error": "YourSoundCapsule.json not found"}

    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM sound_capsule_highlights")
    conn.execute("DELETE FROM sound_capsule_daily")

    highlights = data.get("highlights", [])
    for h in highlights:
        ht = h.get("highlightType", "")
        detail = {}
        if ht == "FIRST_TO_DISCOVER":
            ftd = h.get("firstToDiscoverHighlight", {})
            detail = {"entity": ftd.get("entity", ""), "country": ftd.get("country", ""),
                       "position": ftd.get("position", 0)}
        elif ht == "FANS_LIKE_YOU":
            fly = h.get("fansLikeYouHighlight", {})
            detail = {"artist_name": fly.get("artistName", ""),
                       "fans_percentile": fly.get("percentileFan", 0)}
        elif ht == "STREAKS":
            s = h.get("streakHighlight", {})
            detail = {"streak_days": s.get("streakDays", 0),
                       "entity_name": s.get("entityName", "")}
        elif ht == "MILESTONE":
            m = h.get("milestoneHighlight", {})
            detail = {"stream_count": m.get("streamCount", 0),
                       "entity_name": m.get("entityName", "")}
        elif ht == "ON_REPEAT":
            r = h.get("onRepeatHighlight", {})
            detail = {"track_name": r.get("trackName", ""),
                       "artist_name": r.get("artistName", ""),
                       "play_count": r.get("playCount", 0)}
        elif ht == "YOU_STAND_OUT":
            yso = h.get("youStandOutHighlight", {})
            detail = {"entity_name": yso.get("entityName", ""),
                       "genre": yso.get("genre", ""),
                       "percentile": yso.get("percentile", 0)}
        elif ht == "UNLIKE_COMBINATION":
            uc = h.get("unlikeCombinationHighlight", {})
            detail = {"genre": uc.get("genre", ""),
                       "entity_name": uc.get("entityName", "")}
        elif ht == "PROPORTION_LISTENING_ENTITY":
            ple = h.get("proportionListeningEntityHighlight", {})
            detail = {"entity_name": ple.get("entityName", ""),
                       "proportion": ple.get("proportion", 0)}
        conn.execute(
            "INSERT INTO sound_capsule_highlights(highlight_date, highlight_type, entity_name, detail_json) VALUES (?, ?, ?, ?)",
            (h.get("date", ""), ht, str(detail.get("entity_name", detail.get("track_name", ""))),
             json.dumps(detail, ensure_ascii=False)),
        )

    stats = data.get("stats", [])
    for s in stats:
        conn.execute(
            "INSERT INTO sound_capsule_daily(date, stream_count, seconds_played, top_data_json) VALUES (?, ?, ?, ?)",
            (s.get("date", ""), s.get("streamCount", 0), s.get("secondsPlayed", 0),
             json.dumps({
                 "topTracks": s.get("topTracks", []),
                 "topArtists": s.get("topArtists", []),
                 "topGenres": s.get("topGenres", []),
             }, ensure_ascii=False)),
        )

    conn.commit()
    if close_conn:
        conn.close()
    return {"highlights": len(highlights), "daily_stats": len(stats)}


# ═══════════════════════════════════════════════════════════════════════════
# Marquee
# ═══════════════════════════════════════════════════════════════════════════

def import_marquee(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import Marquee.json into marquee_impressions table."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR
    filepath = os.path.join(data_dir, "Marquee.json")
    if not os.path.exists(filepath):
        return {"error": "Marquee.json not found"}

    with open(filepath, encoding="utf-8") as f:
        records = json.load(f)

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM marquee_impressions")

    for rec in records:
        conn.execute(
            "INSERT INTO marquee_impressions(artist_name, segment) VALUES (?, ?)",
            (rec.get("artistName", ""), rec.get("segment", "")),
        )

    conn.commit()
    if close_conn:
        conn.close()
    return {"impressions": len(records)}


# ═══════════════════════════════════════════════════════════════════════════
# Podcast Data
# ═══════════════════════════════════════════════════════════════════════════

def import_podcast_data(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import all podcast-related Account Data JSONs."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM podcast_plays")
    conn.execute("DELETE FROM podcast_interactions")

    # StreamingHistory_podcast_0.json
    ph_path = os.path.join(data_dir, "StreamingHistory_podcast_0.json")
    podcast_play_count = 0
    if os.path.exists(ph_path):
        with open(ph_path, encoding="utf-8") as f:
            records = json.load(f)
        for rec in records:
            end_time = rec.get("endTime", "")
            # Parse "2025-06-13 10:11" format
            try:
                parts = end_time.split(" ")
                date_part = parts[0]
                hour = int(parts[1].split(":")[0]) if len(parts) > 1 else 0
            except (ValueError, IndexError):
                date_part = end_time[:10]
                hour = 0
            conn.execute(
                """INSERT INTO podcast_plays(end_time, podcast_name, episode_name, ms_played, play_date, play_hour)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (end_time, rec.get("podcastName", ""), rec.get("episodeName", ""),
                 rec.get("msPlayed", 0), date_part, hour),
            )
            podcast_play_count += 1

    # Podcast interactivity files
    interaction_count = 0

    # Comments
    ci_path = os.path.join(data_dir, "PodcastInteractivityComments.json")
    if os.path.exists(ci_path):
        with open(ci_path, encoding="utf-8") as f:
            cdata = json.load(f)
        for c in cdata.get("comments", []):
            conn.execute(
                "INSERT INTO podcast_interactions(interaction_type, entity_uri, content_json, created_at) VALUES (?, ?, ?, ?)",
                ("comment", c.get("entityUri", ""),
                 json.dumps({"commentText": c.get("commentText", "")}, ensure_ascii=False),
                 c.get("postedDate", "")),
            )
            interaction_count += 1

    # Ratings
    ri_path = os.path.join(data_dir, "PodcastInteractivityRatedShow.json")
    if os.path.exists(ri_path):
        with open(ri_path, encoding="utf-8") as f:
            rdata = json.load(f)
        for r in rdata.get("ratedShows", []):
            conn.execute(
                "INSERT INTO podcast_interactions(interaction_type, entity_uri, content_json, created_at) VALUES (?, ?, ?, ?)",
                ("rating", r.get("entityUri", ""),
                 json.dumps({"rating": r.get("rating", "")}, ensure_ascii=False),
                 r.get("ratedDate", "")),
            )
            interaction_count += 1

    # Polls
    pi_path = os.path.join(data_dir, "PodcastInteractivityVotedPollOption.json")
    if os.path.exists(pi_path):
        with open(pi_path, encoding="utf-8") as f:
            pdata = json.load(f)
        for p in pdata.get("votedPollOptionResponses", []):
            conn.execute(
                "INSERT INTO podcast_interactions(interaction_type, entity_uri, content_json, created_at) VALUES (?, ?, ?, ?)",
                ("poll", p.get("entityUri", ""),
                 json.dumps({"response": p.get("response", {})}, ensure_ascii=False),
                 p.get("postedDate", "")),
            )
            interaction_count += 1

    conn.commit()
    if close_conn:
        conn.close()
    return {"podcast_plays": podcast_play_count, "interactions": interaction_count}


# ═══════════════════════════════════════════════════════════════════════════
# Profile Data
# ═══════════════════════════════════════════════════════════════════════════

def import_profile_data(data_dir: Optional[str] = None, conn=None) -> dict:
    """Import Identity.json, UserAttributes.json, Follow.json, UserPrompts.json,
    Payments.json, DuoNewFamily.json into user_* tables."""
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR

    close_conn = conn is None
    if close_conn:
        conn = get_db(readonly=False)

    conn.execute("DELETE FROM user_profile")
    conn.execute("DELETE FROM user_follows")
    conn.execute("DELETE FROM user_prompts")

    entries = 0

    # Identity.json
    fp = os.path.join(data_dir, "Identity.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        for k in ["displayName", "firstName", "lastName", "imageUrl", "largeImageUrl",
                   "tasteMaker", "verified"]:
            if k in d:
                conn.execute("INSERT INTO user_profile(key, value) VALUES (?, ?)",
                             (f"identity_{k}", str(d[k])))
                entries += 1

    # UserAttributes.json
    fp = os.path.join(data_dir, "UserAttributes.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        safe_keys = ["username", "country", "birthdate", "gender", "postalCode"]
        for k in safe_keys:
            if k in d:
                conn.execute("INSERT INTO user_profile(key, value) VALUES (?, ?)",
                             (f"attr_{k}", str(d[k])))
                entries += 1
        # createdFromFacebook
        if "createdFromFacebook" in d:
            conn.execute("INSERT INTO user_profile(key, value) VALUES (?, ?)",
                         ("attr_createdFromFacebook", str(d["createdFromFacebook"])))
            entries += 1

    # Follow.json
    fp = os.path.join(data_dir, "Follow.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        for item in d.get("userIsFollowing", []):
            name = item if isinstance(item, str) else item.get("name", "")
            conn.execute(
                "INSERT INTO user_follows(relationship_type, display_name) VALUES (?, ?)",
                ("following", name),
            )
            entries += 1
        for item in d.get("userIsFollowedBy", []):
            name = item if isinstance(item, str) else item.get("name", "")
            conn.execute(
                "INSERT INTO user_follows(relationship_type, display_name) VALUES (?, ?)",
                ("followed_by", name),
            )
            entries += 1
        for item in d.get("userIsBlocking", []):
            name = item if isinstance(item, str) else item.get("name", "")
            conn.execute(
                "INSERT INTO user_follows(relationship_type, display_name) VALUES (?, ?)",
                ("blocking", name),
            )
            entries += 1

    # UserPrompts.json
    fp = os.path.join(data_dir, "UserPrompts.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        conn.execute(
            "INSERT INTO user_prompts(message, created_timestamp) VALUES (?, ?)",
            (d.get("message", ""), d.get("created_timestamp", "")),
        )

    # Payments.json (non-sensitive info only)
    fp = os.path.join(data_dir, "Payments.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        if "payment_method" in d:
            conn.execute("INSERT INTO user_profile(key, value) VALUES (?, ?)",
                         ("payment_method", d["payment_method"]))

    # DuoNewFamily.json (only address for profile)
    fp = os.path.join(data_dir, "DuoNewFamily.json")
    if os.path.exists(fp):
        with open(fp, encoding="utf-8") as f:
            d = json.load(f)
        if "address" in d:
            conn.execute("INSERT INTO user_profile(key, value) VALUES (?, ?)",
                         ("family_address", d["address"]))

    conn.commit()
    if close_conn:
        conn.close()
    return {"profile_entries": entries}


# ═══════════════════════════════════════════════════════════════════════════
# Master import
# ═══════════════════════════════════════════════════════════════════════════

def import_all(
    data_dir: Optional[str] = None,
    progress_callback=None,
) -> dict[str, Any]:
    """Import all Account Data files. Each import is idempotent (DELETE + INSERT).

    Returns dict with summary statistics for each source.
    """
    if data_dir is None:
        data_dir = ACCOUNT_DATA_DIR

    conn = get_db(readonly=False)
    results: dict[str, Any] = {}

    importers = [
        ("Wrapped 2025", import_wrapped_2025),
        ("音乐库", import_your_library),
        ("歌单", import_playlists),
        ("搜索记录", import_search_queries),
        ("兴趣画像", import_inferences),
        ("Sound Capsule", import_sound_capsule),
        ("推广记录", import_marquee),
        ("播客数据", import_podcast_data),
        ("个人档案", import_profile_data),
    ]

    for i, (name, func) in enumerate(importers):
        if progress_callback:
            progress_callback(f"导入 {name}...", i / len(importers))
        try:
            r = func(data_dir=data_dir, conn=conn)
            results[name] = r
        except FileNotFoundError:
            results[name] = "skipped (file not found)"
        except Exception as e:
            results[name] = f"error: {e}"

    conn.close()
    if progress_callback:
        progress_callback("账号数据导入完成", 1.0)
    return results
