from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    ClaimCheckResult,
    EvidenceItem,
    ResearchBrief,
    StoryCandidate,
    StorylinePlan,
)


def test_research_brief_serializes_story_candidates():
    evidence = EvidenceItem(
        id="top_artist_taylor_2026",
        claim="Taylor Swift 以 1115 次播放位列 2026 当前艺人第一。",
        source="yearly_top_entities.artists[0]",
        kind="playback_rank",
        confidence="high",
    )
    candidate = StoryCandidate(
        id="stable_center",
        title="Taylor Swift 是稳定回访对象",
        why_it_matters="它解释了年度重心，而不是只给出艺人榜第一。",
        evidence_refs=("top_artist_taylor_2026",),
        risk_notes=("不能写成外部官方 Billboard。",),
    )
    brief = ResearchBrief(
        period={"year": 2026, "end_date": "2026-06-23", "is_partial_year": True},
        evidence_ledger=(evidence,),
        story_candidates=(candidate,),
        tensions=(),
        forbidden_inferences=("不能编造通勤、考试、天气或地点。",),
    )

    payload = brief.to_dict()

    assert payload["period"]["year"] == 2026
    assert payload["evidence_ledger"][0]["id"] == "top_artist_taylor_2026"
    assert payload["story_candidates"][0]["evidence_refs"] == ["top_artist_taylor_2026"]


def test_storyline_plan_and_article_sections_round_trip():
    plan = StorylinePlan(
        thesis="2026 上半年由稳定回访和阶段转折共同构成。",
        title="一份还在展开的音乐年记",
        subtitle="截至 2026-06-23，稳定和变化同时存在。",
        section_plan=(
            ArticleSection(
                id="opening",
                heading="今年还没有结束，但重心已经出现",
                purpose="建立阶段性年报边界和主论点",
                prose="",
                evidence_refs=("period_2026_ytd",),
                chart_refs=(),
            ),
        ),
        must_not_write=("不要按固定榜单模块展开。",),
    )
    draft = ArticleDraft(
        title=plan.title,
        subtitle=plan.subtitle,
        thesis=plan.thesis,
        sections=plan.section_plan,
        closing="继续观察下半年是否延续。",
    )

    assert draft.to_dict()["sections"][0]["heading"] == "今年还没有结束，但重心已经出现"
    assert StorylinePlan.from_dict(plan.to_dict()).thesis == plan.thesis


def test_claim_check_result_requires_all_supported_for_pass():
    passed = ClaimCheckResult(
        claims=(),
        unsupported_claims=(),
        contradicted_claims=(),
        ambiguous_claims=(),
        scope_leaks=(),
    )
    failed = ClaimCheckResult(
        claims=(),
        unsupported_claims=("没有证据的生活事件",),
        contradicted_claims=(),
        ambiguous_claims=(),
        scope_leaks=(),
    )

    assert passed.ok is True
    assert failed.ok is False
