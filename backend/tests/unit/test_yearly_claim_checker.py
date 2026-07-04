from backend.domains.ai_reports.editorial_agent.claim_checker import check_article_claims
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    EvidenceItem,
    ResearchBrief,
)


def _article(text: str):
    return ArticleDraft(
        title="2026 音乐年记",
        subtitle="截至 2026-06-23",
        thesis="稳定和变化同时存在。",
        sections=(
            ArticleSection(
                id="opening",
                heading="重心出现",
                purpose="建立主论点",
                prose=text,
                evidence_refs=("top_artist_taylor",),
                chart_refs=(),
            ),
        ),
        closing="",
    )


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
            EvidenceItem(
                id="artist_monthly_turning_point",
                claim="Olivia Rodrigo 在 2026-05 达到 105 次，超过 Taylor Swift 的 67 次。",
                source="chart_data.artist_monthly_trend.observations[0]",
                kind="monthly_shift",
            ),
        ),
        story_candidates=(),
        tensions=(),
        forbidden_inferences=("不能编造通勤、考试、天气、地点、分手、旅行或加班。",),
    )


def test_claim_checker_passes_supported_entities_and_numbers():
    result = check_article_claims(
        _article("Taylor Swift 以 1115 次播放成为你当前年度艺人第一。"),
        _brief(),
    )

    assert result.ok is True
    assert result.claims
    assert result.claims[0].matched_evidence_refs == ("top_artist_taylor",)


def test_claim_checker_allows_interpretive_playback_language_without_new_numbers():
    result = check_article_claims(
        _article("Taylor Swift 的位置不是单纯播放排名，而是一条稳定回访的声音线。"),
        _brief(),
    )

    assert result.ok is True
    assert result.ambiguous_claims == ()


def test_claim_checker_flags_unsupported_life_event():
    result = check_article_claims(_article("这像一次通勤路上的陪伴。"), _brief())

    assert result.ok is False
    assert result.unsupported_claims == ("这像一次通勤路上的陪伴",)


def test_claim_checker_flags_external_billboard_scope_leak():
    result = check_article_claims(_article("这张专辑登上了官方 Billboard。"), _brief())

    assert result.ok is False
    assert result.scope_leaks == ("这张专辑登上了官方 Billboard",)


def test_claim_checker_allows_personal_billboard_interpretation_without_new_numbers():
    result = check_article_claims(
        _article("播放量和个人 Billboard 放在一起，能区分常听和长留。"),
        _brief(),
    )

    assert result.ok is True
    assert result.ambiguous_claims == ()


def test_claim_checker_allows_negated_external_billboard_scope():
    result = check_article_claims(
        _article("这里的个人 Billboard 基于本地播放记录，不是外部官方 Billboard。"),
        _brief(),
    )

    assert result.ok is True
    assert result.scope_leaks == ()
