import json

from backend.domains.ai_reports.editorial_agent.pipeline import run_editorial_agent_pipeline


def test_pipeline_returns_article_sections_and_metadata():
    context = {
        "reporting_period": {"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
        "top_tracks": [{"name": "Opalite", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "weeks_on_chart": 24}]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            }
        },
    }

    def fake_chat(system_prompt: str, user_content: str, temperature: float) -> str:
        del user_content, temperature
        if "策划编辑" in system_prompt:
            return '{"thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","title":"2026 音乐年记","subtitle":"截至 2026-06-23","section_plan":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"must_not_write":["不要写成榜单摘要"]}'
        if "年度音乐年记作者" in system_prompt:
            return '{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 以 1115 次播放反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 也留在个人 Billboard 里。","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"closing":"这份记录还在展开。"}'
        return '{"revised_article":{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"Taylor Swift 的稳定回访和 Olivia Rodrigo 的阶段升温共同构成主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 以 1115 次播放反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 也留在个人 Billboard 里。","evidence_refs":["top_artist_taylor_swift","artist_monthly_turning_point"],"chart_refs":["artist_monthly_trend"]}],"closing":"这份记录还在展开。"},"edit_notes":["保留具体实体"],"risk_flags":[]}'

    result = run_editorial_agent_pipeline(
        context, chart_data=context["chart_data"], chat_fn=fake_chat
    )

    assert result["metadata"]["writer_pipeline_version"] == "yearly_editorial_agent_v1"
    assert result["metadata"]["claim_check_passed"] is True
    assert result["metadata"]["taste_score"]["total"] >= 26
    assert len(result["article"].sections) >= 5


def test_pipeline_fallback_writer_is_usable_when_llm_returns_empty():
    context = {
        "reporting_period": {"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        "top_artists": [
            {"name": "Taylor Swift", "plays": 1115},
            {"name": "Olivia Rodrigo", "plays": 769},
        ],
        "top_tracks": [{"name": "Opalite", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "weeks_on_chart": 24}]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            }
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143, "top_track_plays": 4},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_seen": "2026-03-09", "plays": 574}]
        },
    }

    result = run_editorial_agent_pipeline(
        context,
        chart_data=context["chart_data"],
        chat_fn=lambda _system_prompt, _user_content, _temperature: None,
    )

    assert result["metadata"]["claim_check_passed"] is True
    assert result["metadata"]["taste_score"]["ok"] is True
    assert "这一节需要围绕" not in result["article"].to_dict()["sections"][0]["prose"]
    assert result["article"].sections[0].chart_refs


def test_pipeline_rejects_editor_output_that_collapses_article_shape():
    context = _pipeline_context()

    def fake_chat(system_prompt: str, _user_content: str, _temperature: float) -> str:
        if "策划编辑" in system_prompt:
            return json.dumps(_plan_payload())
        if "年度音乐年记作者" in system_prompt:
            return json.dumps(_article_payload(section_count=5))
        return json.dumps(
            {
                "revised_article": _article_payload(section_count=1),
                "edit_notes": ["模型把文章改短了"],
                "risk_flags": [],
            }
        )

    result = run_editorial_agent_pipeline(
        context,
        chart_data=context["chart_data"],
        chat_fn=fake_chat,
    )

    assert len(result["article"].sections) >= 5
    assert result["metadata"]["claim_check_passed"] is True
    assert "编辑输出未通过质量门槛" in " ".join(result["edit_notes"])


def test_pipeline_removes_ambiguous_numeric_claims_before_final_metadata():
    context = _pipeline_context()

    def fake_chat(system_prompt: str, _user_content: str, _temperature: float) -> str:
        payload = _article_payload(section_count=5)
        payload["sections"][0]["prose"] += " Taylor Swift 有 9999 次隐藏播放。"
        if "策划编辑" in system_prompt:
            return json.dumps(_plan_payload())
        if "年度音乐年记作者" in system_prompt:
            return json.dumps(payload)
        return json.dumps(
            {
                "revised_article": payload,
                "edit_notes": ["保留原稿"],
                "risk_flags": [],
            }
        )

    result = run_editorial_agent_pipeline(
        context,
        chart_data=context["chart_data"],
        chat_fn=fake_chat,
    )

    article_text = "\n".join(section.prose for section in result["article"].sections)
    assert result["metadata"]["claim_check_passed"] is True
    assert "9999 次隐藏播放" not in article_text


def test_pipeline_uses_deterministic_longform_when_llm_claims_cannot_be_repaired():
    context = _pipeline_context()

    def fake_chat(system_prompt: str, _user_content: str, _temperature: float) -> str:
        if "策划编辑" in system_prompt:
            return json.dumps(_plan_payload())
        payload = _article_payload(section_count=5)
        for section in payload["sections"]:
            section["prose"] = "Taylor Swift 有 9999 次隐藏播放。" * 80
        payload["closing"] = "Taylor Swift 有 9999 次隐藏播放。" * 40
        if "年度音乐年记作者" in system_prompt:
            return json.dumps(payload)
        return json.dumps(
            {
                "revised_article": payload,
                "edit_notes": ["保留原稿"],
                "risk_flags": [],
            }
        )

    result = run_editorial_agent_pipeline(
        context,
        chart_data=context["chart_data"],
        chat_fn=fake_chat,
    )

    article_text = "\n".join(section.prose for section in result["article"].sections)
    assert result["metadata"]["claim_check_passed"] is True
    assert result["metadata"]["taste_score"]["ok"] is True
    assert len(article_text + result["article"].closing) >= 1800
    assert "9999 次隐藏播放" not in article_text
    assert "确定性长文兜底" in " ".join(result["edit_notes"])


def test_pipeline_restores_theme_and_chart_refs_after_editor_weakens_them():
    context = _pipeline_context()

    def fake_chat(system_prompt: str, _user_content: str, _temperature: float) -> str:
        if "策划编辑" in system_prompt:
            return json.dumps(_plan_payload())
        payload = _article_payload(section_count=5)
        payload["thesis"] = "稳定回访。"
        for section in payload["sections"]:
            section["chart_refs"] = []
        if "年度音乐年记作者" in system_prompt:
            return json.dumps(payload)
        return json.dumps(
            {
                "revised_article": payload,
                "edit_notes": ["编辑器弱化了主题和图表引用"],
                "risk_flags": [],
            }
        )

    result = run_editorial_agent_pipeline(
        context,
        chart_data=context["chart_data"],
        chat_fn=fake_chat,
    )

    assert result["metadata"]["taste_score"]["ok"] is True
    assert "共同" in result["article"].thesis or "构成" in result["article"].thesis
    assert any(section.chart_refs for section in result["article"].sections)


def _pipeline_context():
    return {
        "reporting_period": {"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        "top_artists": [{"name": "Taylor Swift", "plays": 1115}],
        "top_tracks": [{"name": "Opalite", "plays": 123}],
        "top_albums": [{"name": "The Life of a Showgirl", "plays": 445}],
        "personal_billboard_year_end": {
            "albums": [{"name": "The Life of a Showgirl", "weeks_on_chart": 24}]
        },
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。"
                ]
            }
        },
        "highlight_day_detail": {"date": "2026-04-03", "plays": 143, "top_track_plays": 4},
        "discovery_and_returns": {
            "new_artists": [{"name": "Zhang Zhen Yue", "first_seen": "2026-03-09", "plays": 574}]
        },
    }


def _plan_payload():
    return {
        "thesis": "Taylor Swift 的稳定回访、Opalite 和 The Life of a Showgirl 构成主线。",
        "title": "2026 音乐年记",
        "subtitle": "截至 2026-06-23",
        "section_plan": [
            {
                "id": "opening" if index == 0 else f"section_{index}",
                "heading": "重心已经出现" if index == 0 else f"年度线索 {index}",
                "purpose": "建立主论点",
                "evidence_refs": ["top_artist_taylor_swift", "top_track_opalite"],
                "chart_refs": ["artist_monthly_trend"] if index == 1 else [],
            }
            for index in range(5)
        ],
        "must_not_write": ["不要写成榜单摘要"],
    }


def _article_payload(*, section_count: int):
    long_prose = (
        "Taylor Swift 以 1115 次播放位列艺人榜第一。"
        "Opalite 以 123 次播放位列单曲榜第一。"
        "The Life of a Showgirl 的播放量和个人 Billboard 专辑表现对齐，个人榜在榜 24 周。"
        "这些事实说明报告需要解释稳定回访、单曲高频和专辑长留之间的关系。"
    ) * 4
    return {
        "title": "2026 音乐年记",
        "subtitle": "截至 2026-06-23",
        "thesis": "Taylor Swift 的稳定回访、Opalite 和 The Life of a Showgirl 构成主线。",
        "sections": [
            {
                "id": "opening" if index == 0 else f"section_{index}",
                "heading": "重心已经出现" if index == 0 else f"年度线索 {index}",
                "purpose": "建立主论点",
                "prose": long_prose,
                "evidence_refs": ["top_artist_taylor_swift", "top_track_opalite"],
                "chart_refs": ["artist_monthly_trend"] if index == 1 else [],
            }
            for index in range(section_count)
        ],
        "closing": "这份记录还在展开。" + long_prose,
    }
