import json

from backend.domains.ai_reports.editorial_agent.editor import edit_article
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.writer import write_article


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


def _plan():
    sections = []
    for index in range(5):
        sections.append(
            ArticleSection(
                id="opening" if index == 0 else f"section_{index}",
                heading="重心已经出现" if index == 0 else f"年度线索 {index}",
                purpose="建立主论点",
                prose="",
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            )
        )
    return StorylinePlan(
        thesis="稳定回访构成上半年主线。",
        title="2026 音乐年记",
        subtitle="截至 2026-06-23，稳定和变化同时存在。",
        section_plan=tuple(sections),
        must_not_write=("不要写成榜单摘要。",),
    )


def test_write_article_uses_llm_sections():
    def fake_chat(_system_prompt: str, user_content: str, _temperature: float) -> str:
        assert "top_artist_taylor" in user_content
        long_prose = (
            "Taylor Swift 不是偶然出现的名字，而是你上半年反复回到的声音。"
            "这段话故意写得足够完整，用来证明 writer 不会把短稿当作合格年报。"
            "它把年度第一解释成持续回访，而不是只复述排行榜。"
        ) * 5
        return json.dumps(
            {
                "title": "2026 音乐年记",
                "subtitle": "截至 2026-06-23，稳定和变化同时存在。",
                "thesis": "稳定回访构成上半年主线。",
                "sections": [
                    {
                        "id": "opening" if index == 0 else f"section_{index}",
                        "heading": "重心已经出现" if index == 0 else f"年度线索 {index}",
                        "purpose": "建立主论点",
                        "prose": long_prose,
                        "evidence_refs": ["top_artist_taylor"],
                        "chart_refs": [],
                    }
                    for index in range(5)
                ],
                "closing": "这份记录还在展开。" + long_prose,
            }
        )

    draft = write_article(_brief(), _plan(), chart_data={}, chat_fn=fake_chat)

    assert draft.sections[0].prose.startswith("Taylor Swift")
    assert draft.closing.startswith("这份记录还在展开。")


def test_write_article_rejects_short_llm_draft_and_falls_back_to_full_article():
    def short_chat(_system_prompt: str, _user_content: str, _temperature: float) -> str:
        return """
        {"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"稳定回访构成上半年主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 是第一。","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"closing":"继续观察。"}
        """

    draft = write_article(_brief(), _plan(), chart_data={}, chat_fn=short_chat)
    article_text = "\n".join(section.prose for section in draft.sections) + "\n" + draft.closing

    assert len(draft.sections) >= 5
    assert len(article_text) >= 1800
    assert "这一节需要" not in article_text


def test_edit_article_accepts_revised_article_and_notes():
    draft = ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="稳定回访构成上半年主线。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心已经出现",
                purpose="建立主论点",
                prose="证据说明 Taylor Swift 是稳定中心。证据说明 Taylor Swift 是稳定中心。",
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            ),
        ),
        closing="继续观察走势。",
    )

    def fake_chat(_system_prompt: str, _user_content: str, _temperature: float) -> str:
        return """
        {"revised_article":{"title":"2026 音乐年记","subtitle":"截至 2026-06-23","thesis":"稳定回访构成上半年主线。","sections":[{"id":"opening","heading":"重心已经出现","purpose":"建立主论点","prose":"Taylor Swift 更像你上半年反复回到的声音。","evidence_refs":["top_artist_taylor"],"chart_refs":[]}],"closing":"这份记录还在展开。"},"edit_notes":["删除重复句"],"risk_flags":[]}
        """

    edited = edit_article(_brief(), _plan(), draft, chat_fn=fake_chat)

    assert edited.article.sections[0].prose == "Taylor Swift 更像你上半年反复回到的声音。"
    assert edited.edit_notes == ("删除重复句",)
