from backend.domains.ai_reports.editorial_agent.research_brief import build_research_brief


def _context():
    return {
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_plays": 7860, "total_minutes": 29882},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143, "top_track_plays": 4},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_seen": "2026-03-09", "plays": 574}]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            },
            "playback_billboard_matrix": {
                "observations": ["The Life of a Showgirl 是专辑里兼具高播放和长在榜的核心作品。"]
            },
        },
    }


def test_research_brief_builds_story_candidates_from_context():
    brief = build_research_brief(_context())
    payload = brief.to_dict()
    candidate_ids = {item["id"] for item in payload["story_candidates"]}
    evidence_ids = {item["id"] for item in payload["evidence_ledger"]}

    assert payload["period"]["end_date"] == "2026-06-23"
    assert "stable_top_artist" in candidate_ids
    assert "monthly_turning_point" in candidate_ids
    assert "album_playback_billboard_alignment" in candidate_ids
    assert "highlight_day_density" in candidate_ids
    assert "discovery_signal" in candidate_ids
    assert "top_artist_taylor_swift" in evidence_ids
    assert "album_life_of_a_showgirl_alignment" in evidence_ids
    assert "不能编造通勤、考试、天气、地点、分手、旅行或加班。" in payload["forbidden_inferences"]


def test_research_brief_omits_empty_candidates():
    context = {"reporting_period": {"year": 2026}}
    brief = build_research_brief(context)

    assert brief.period["year"] == 2026
    assert brief.story_candidates == ()
    assert brief.evidence_ledger == ()
