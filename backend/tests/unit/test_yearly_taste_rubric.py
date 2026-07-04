from backend.domains.ai_reports.editorial_agent.models import ArticleDraft, ArticleSection
from backend.domains.ai_reports.editorial_agent.taste_rubric import score_article_taste


def _article(prose: str, closing: str = "这份记录还在展开。"):
    return ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="Taylor Swift 的稳定回访、Olivia Rodrigo 的阶段升温和 The Life of a Showgirl 的长留共同构成主线。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心出现",
                purpose="建立主论点",
                prose=prose,
                evidence_refs=("top_artist_taylor",),
                chart_refs=("artist_monthly_trend",),
            ),
        ),
        closing=closing,
    )


def test_taste_rubric_rewards_article_with_thesis_and_specific_entities():
    score = score_article_taste(
        _article(
            "Taylor Swift 反复出现，Olivia Rodrigo 在 2026-05 变亮，The Life of a Showgirl 同时留在播放量和个人 Billboard 里。"
        )
    )

    assert score.total >= 26
    assert score.dimensions["年度主题"] >= 4
    assert score.dimensions["事实安全"] == 5


def test_taste_rubric_penalizes_jargon_and_weak_closing():
    score = score_article_taste(
        _article(
            "证据说明年度画像的结构和尺度形成稳定重心。综合来看，第二层证据构成三榜联动。",
            closing="后续观察走势。",
        )
    )

    assert score.total < 26
    assert score.dimensions["可读性"] < 4
