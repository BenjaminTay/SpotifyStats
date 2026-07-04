from backend.domains.ai_reports.editorial_agent.llm_steps import extract_json_object
from backend.domains.ai_reports.editorial_agent.models import (
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
)
from backend.domains.ai_reports.editorial_agent.storyline_planner import plan_storyline


def test_extract_json_object_reads_fenced_json():
    text = """模型说明
```json
{"title": "音乐年记", "sections": [1, 2]}
```
"""

    assert extract_json_object(text) == {"title": "音乐年记", "sections": [1, 2]}


def test_extract_json_object_returns_empty_dict_for_invalid_json():
    assert extract_json_object("不是 json") == {}


def _brief():
    return ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(
            EvidenceItem(
                id="top_artist_taylor",
                claim="Taylor Swift 以 1115 次播放位列年度艺人第一。",
                source="top_artists[0]",
                kind="playback_rank",
            ),
        ),
        story_candidates=(
            StoryCandidate(
                id="stable_top_artist",
                title="Taylor Swift 是稳定回访对象",
                why_it_matters="它解释年度重心。",
                evidence_refs=("top_artist_taylor",),
            ),
        ),
        tensions=(),
        forbidden_inferences=("不能编造生活事件。",),
    )


def test_plan_storyline_uses_llm_json_when_valid():
    def fake_chat(system_prompt: str, user_content: str, temperature: float) -> str:
        assert "年度音乐报告策划编辑" in system_prompt
        assert "stable_top_artist" in user_content
        assert temperature == 0.1
        return """
        {"thesis":"稳定回访构成上半年主线","title":"2026 音乐年记","subtitle":"稳定和变化同时存在","section_plan":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"must_not_write":["不要写成榜单摘要"]}
        """

    plan = plan_storyline(_brief(), chat_fn=fake_chat)

    assert plan.thesis == "稳定回访构成上半年主线"
    assert plan.section_plan[0].evidence_refs == ("top_artist_taylor",)


def test_plan_storyline_falls_back_when_llm_empty():
    plan = plan_storyline(_brief(), chat_fn=lambda *_args: "")

    assert plan.title
    assert plan.thesis
    assert plan.section_plan
    assert plan.section_plan[0].id == "opening"


def test_plan_storyline_fallback_still_builds_article_backbone():
    plan = plan_storyline(_brief(), chat_fn=lambda *_args: "")

    assert len(plan.section_plan) >= 5
    assert len({section.id for section in plan.section_plan}) == len(plan.section_plan)
    assert any(section.evidence_refs for section in plan.section_plan)
