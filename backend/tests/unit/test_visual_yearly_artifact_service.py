from __future__ import annotations

import pytest

from backend.domains.ai_reports.agentic_models import EvidenceLedgerEntry

pytestmark = pytest.mark.unit


def test_visual_yearly_artifact_service_generates_artifact(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2025,
        "reporting_period": {
            "year": 2025,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_partial_year": False,
        },
        "hero": {"active_days": 364, "total_minutes": 68100, "total_plays": 17567},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 2629},
            {"name": "Michael Wong", "plays": 2087},
        ],
        "top_tracks": [{"name": "The Fate of Ophelia", "artist": "Taylor Swift", "plays": 190}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 1106}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "weeks_on_chart": 32,
                    "rank": 1,
                }
            ],
            "tracks": [
                {
                    "name": "The Fate of Ophelia",
                    "artist": "Taylor Swift",
                    "weeks_on_chart": 13,
                    "rank": 1,
                }
            ],
            "artists": [{"name": "Taylor Swift", "weeks_on_chart": 50, "rank": 1}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 16.7}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "JOLIN", "first_date": "2025-05-08", "plays": 108}]
        },
        "highlight_day_detail": {
            "date": "2025-02-14",
            "plays": 154,
            "interpretation_guidance": "多曲目活跃日",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2025},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    chart_contexts = []
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: (
            chart_contexts.append(context) or {spec["id"]: {"ok": True} for spec in chart_specs}
        ),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact(
        {
            "year": 2025,
            "min_ms": 45000,
            "music_only": False,
            "merge_enabled": False,
            "dynamic_threshold": True,
            "max_merge_gap_minutes": 12,
        }
    )

    assert result["success"] is True
    assert result["artifact"]["report_mode"] == "visual_yearly_artifact"
    assert result["metadata"]["contract_version"] == "visual_yearly_v1"
    assert result["metadata"]["section_count"] >= 6
    assert result["metadata"]["chart_count"] >= 4
    assert result["critic"]["ok"] is True
    assert result["fact_validation"]["ok"] is True
    assert "Taylor Swift" in result["report"]
    assert "The Fate of Ophelia" in result["report"]
    assert "光良「回憶裡的瘋狂」巡迴演唱會" in result["report"]
    assert chart_contexts[0]["request_filters"] == {
        "year": 2025,
        "min_ms": 45000,
        "music_only": False,
        "merge_enabled": False,
        "dynamic_threshold": True,
        "max_merge_gap_minutes": 12,
    }


def test_visual_yearly_artifact_service_avoids_duplicate_partial_cutoff(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "多曲目活跃日",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview",
                    params={"year": 2026},
                    result_summary="summary",
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert "截至 2026-06-23" in result["report"]
    assert "截至 2026-06-23，截至 2026-06-23" not in result["report"]


def test_visual_yearly_artifact_service_handles_aligned_album_without_false_contrast(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert "The Life of a Showgirl 和 The Life of a Showgirl" not in result["report"]
    assert "两种不同的喜欢" not in result["report"]
    assert any(phrase in result["report"] for phrase in ("重合", "同一张", "同一个专辑"))


def test_visual_yearly_artifact_service_sanitizes_editorial_leakage(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 14.4}, {"name": "c-pop", "share": 14.4}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})
    prose = result["report"]

    assert "Olivia Rodrigo 让年度画像多了一条不同的情绪线。它把华语、回望和现场感" not in prose
    assert "不要写成" not in prose
    assert "证据强度可以先放在" not in prose
    assert prose.count("图表负责回答") <= 1


def test_visual_yearly_artifact_service_passes_full_context_to_visual_critic(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1}],
            "artists": [{"name": "Taylor Swift", "rank": 1}],
        },
        "genre_distribution": {"top_genres": [{"name": "pop", "share": 30.0}]},
        "discovery_and_returns": {"new_artists": []},
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {spec["id"]: {"ok": True} for spec in chart_specs},
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    def fake_critic(artifact, context):
        del artifact
        captured["context"] = context
        return {"ok": True, "issues": []}

    monkeypatch.setattr(svc, "critique_visual_yearly_artifact", fake_critic)

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert result["critic"]["ok"] is True
    critic_context = captured["context"]
    assert critic_context["is_partial_year"] is True
    assert critic_context["top_albums"][0]["name"] == "The Life of a Showgirl"
    assert (
        critic_context["personal_billboard_year_end"]["albums"][0]["name"]
        == "The Life of a Showgirl"
    )


def test_visual_yearly_artifact_service_reads_chart_observations_in_sections(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    observations = {
        "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
        "highlight_day_timeline": "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。",
        "playback_billboard_matrix": "Opalite 是单曲里兼具高播放和长在榜的核心作品。",
    }
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(observations),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert result["critic"]["ok"] is True
    report = result["report"]
    assert observations["artist_monthly_trend"] not in report
    assert "到 2026-06，Olivia Rodrigo 的月度播放已经来到 366 次" in report
    assert observations["highlight_day_timeline"] not in report
    assert "2026-04-03 的 143 次播放并没有集中到单曲循环上" in report
    assert observations["playback_billboard_matrix"] not in report
    assert "Opalite 同时出现在高播放和长在榜证据里" in report


def test_visual_yearly_artifact_service_uses_chart_data_for_dynamic_outline(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(
            {
                "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
            }
        ),
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    roles = [section["role"] for section in result["artifact"]["visual_brief"]["outline_sections"]]
    assert "turning_point" in roles
    assert "billboard_divergence" in roles
    assert "second_thread" not in roles


def test_visual_yearly_artifact_service_partial_year_avoids_full_year_labels(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: (
            [
                EvidenceLedgerEntry(
                    tool_name="yearly_overview", params={"year": 2026}, result_summary="summary"
                )
            ],
            context,
        ),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: _chart_data_with_observations(
            {
                "artist_monthly_trend": "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。",
            }
        ),
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert result["fact_validation"]["ok"] is True
    assert "年度排名" not in result["report"]
    visible_payload = " ".join(
        [
            result["report"],
            " ".join(
                str(card.get("label") or "") + str(card.get("caption") or "")
                for card in result["artifact"]["insight_cards"]
            ),
            " ".join(
                str(chart.get("title") or "")
                + str(chart.get("insight") or "")
                + str(chart.get("fallback") or "")
                for chart in result["artifact"]["chart_specs"]
            ),
        ]
    )
    assert "全年陪伴密度" not in visible_payload
    assert "年度高光日" not in visible_payload
    assert "年度声音线索" not in visible_payload
    assert "阶段陪伴密度" in visible_payload


def test_visual_yearly_artifact_exposes_editorial_metadata(monkeypatch):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "rank": 1, "weeks_on_chart": 24}],
            "tracks": [{"name": "Opalite", "rank": 1, "weeks_on_chart": 19}],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {"top_genres": [{"name": "mandopop", "share": 14.4}]},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143},
    }

    monkeypatch.setattr(
        svc,
        "_run_visual_research",
        lambda request, emit_event=None: ([], context),
    )
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            "artist_monthly_trend": {
                "ok": True,
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ],
            },
            "album_duality_compare": {"ok": True, "relation": "aligned"},
            "playback_billboard_matrix": {
                "ok": True,
                "observations": ["Opalite 是单曲里兼具高播放和长在榜的核心作品。"],
            },
            "highlight_day_timeline": {
                "ok": True,
                "observations": ["2026-04-03 是播放最密集的一天，共 143 次。"],
            },
            "genre_language_mix": {"ok": True},
            "discovery_timeline": {"ok": True, "new_artists": [{"name": "Zhang Zhen Yue"}]},
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    metadata = result["artifact"]["metadata"]
    assert metadata["editorial_plan_version"] == "yearly_editorial_v1"
    assert metadata["fact_count"] >= 5
    assert "turning_point" in metadata["section_roles"]
    assert any(
        "artist_monthly_trend_primary_observation" in section["evidence_refs"]
        for section in result["artifact"]["sections"]
    )


def test_visual_yearly_artifact_respects_language_budget_and_avoids_overview_repetition(
    monkeypatch,
):
    from backend.domains.ai_reports import visual_yearly_artifact_service as svc

    context = _quality_polish_context()
    monkeypatch.setattr(svc, "_run_visual_research", lambda request, emit_event=None: ([], context))
    monkeypatch.setattr(
        svc,
        "build_visual_chart_data",
        lambda context, chart_specs: {
            spec["id"]: {"ok": True, "observations": []} for spec in chart_specs
        },
    )
    monkeypatch.setattr(
        svc,
        "_validate_visual_fact_safety",
        lambda report, artifact, context: {"ok": True, "issues": []},
    )

    result = svc.generate_visual_yearly_artifact({"year": 2026})

    assert result["critic"]["ok"] is True
    metadata = result["artifact"]["metadata"]
    assert metadata["language_budget"]
    visible_text = _artifact_section_text(result["artifact"])
    report_text = result["report"]
    for text in (report_text, visible_text):
        assert text.count("174 个活跃日") <= 1
        assert text.count("7860 次播放") <= 1
        for phrase in ("入口", "坐标", "地图", "声音线", "主线"):
            assert text.count(phrase) <= metadata["language_budget"][phrase]
        assert "通勤" not in text
        assert "下雨" not in text


def _artifact_section_text(artifact: dict) -> str:
    parts: list[str] = []
    for section in artifact["sections"]:
        parts.extend(str(section.get(key) or "") for key in ("deck", "prose", "pull_quote"))
    return "\n".join(parts)


def _quality_polish_context() -> dict:
    return {
        "year": 2026,
        "reporting_period": {
            "year": 2026,
            "start_date": "2026-01-01",
            "end_date": "2026-06-23",
            "is_partial_year": True,
        },
        "hero": {"active_days": 174, "total_minutes": 29882, "total_plays": 7860},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "artist": "Taylor Swift", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "artist": "Taylor Swift", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [
                {
                    "name": "光良「回憶裡的瘋狂」巡迴演唱會",
                    "artist": "Michael Wong",
                    "rank": 1,
                    "weeks_on_chart": 32,
                }
            ],
            "tracks": [
                {"name": "Opalite", "artist": "Taylor Swift", "rank": 1, "weeks_on_chart": 19}
            ],
            "artists": [{"name": "Taylor Swift", "rank": 1, "weeks_on_chart": 25}],
        },
        "genre_distribution": {
            "top_genres": [{"name": "mandopop", "share": 14.4}, {"name": "c-pop", "share": 14.4}],
            "caveat": "Spotify 流派标签可能重叠。",
        },
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_date": "2026-03-09", "plays": 574}]
        },
        "highlight_day_detail": {
            "date": "2026-04-03",
            "plays": 143,
            "interpretation_guidance": "当天最高单曲播放不高，不要写成重度单曲循环。",
        },
    }


def _chart_data_with_observations(observations: dict[str, str]) -> dict:
    return {
        "listening_calendar": {"ok": True, "active_days": 174},
        "artist_monthly_trend": {
            "ok": True,
            "observations": [observations["artist_monthly_trend"]],
        },
        "album_duality_compare": {
            "ok": True,
            "relation": "divergent",
            "playback_leader": {"name": "The Life of a Showgirl"},
            "chart_leader": {"name": "光良「回憶裡的瘋狂」巡迴演唱會"},
        },
        "highlight_day_timeline": {
            "ok": True,
            "observations": [
                observations.get(
                    "highlight_day_timeline",
                    "2026-04-03 有 143 次播放，但最高单曲只有 4 次，更像多曲目密集漫游。",
                )
            ],
        },
        "genre_language_mix": {"ok": True},
        "discovery_timeline": {"ok": True, "new_artists": [{"name": "Zhang Zhen Yue"}]},
        "playback_billboard_matrix": {
            "ok": True,
            "observations": [
                observations.get(
                    "playback_billboard_matrix", "Opalite 是单曲里兼具高播放和长在榜的核心作品。"
                )
            ],
        },
    }
