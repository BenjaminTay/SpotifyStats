"""Deterministic claim checks for editorial-agent yearly reports."""

from __future__ import annotations

import re

from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ClaimCheckResult,
    ExtractedClaim,
    ResearchBrief,
)

UNSUPPORTED_LIFE_TERMS = ("通勤", "考试", "天气", "下雨", "分手", "旅行", "加班")
EXTERNAL_BILLBOARD_TERMS = ("官方 Billboard", "外部 Billboard", "美国 Billboard")
SAFE_AMBIGUOUS_TERMS = ("当前", "上半年", "阶段", "音乐", "年记", "展开")


def check_article_claims(article: ArticleDraft, brief: ResearchBrief) -> ClaimCheckResult:
    evidence = _evidence_claims(brief)
    unsupported: list[str] = []
    ambiguous: list[str] = []
    scope_leaks: list[str] = []
    claims: list[ExtractedClaim] = []

    for sentence in _sentences(_article_text(article)):
        if any(term in sentence for term in UNSUPPORTED_LIFE_TERMS):
            unsupported.append(sentence)
            continue
        if any(term in sentence for term in EXTERNAL_BILLBOARD_TERMS) and not _is_negated_scope(
            sentence
        ):
            scope_leaks.append(sentence)
            continue
        if _contains_fact_signal(sentence):
            refs = _matched_refs(sentence, evidence)
            if refs:
                claims.append(
                    ExtractedClaim(
                        text=sentence,
                        claim_type="fact",
                        matched_evidence_refs=refs,
                        status="supported",
                    )
                )
            elif not _is_safe_context_sentence(sentence, brief):
                ambiguous.append(sentence)

    return ClaimCheckResult(
        claims=tuple(claims),
        unsupported_claims=tuple(unsupported),
        contradicted_claims=(),
        ambiguous_claims=tuple(ambiguous),
        scope_leaks=tuple(scope_leaks),
    )


def _evidence_claims(brief: ResearchBrief) -> dict[str, str]:
    evidence = {item.id: item.claim for item in brief.evidence_ledger}
    year = brief.period.get("year")
    end_date = str(brief.period.get("end_date") or "")
    if end_date:
        evidence["reporting_period"] = f"{year} 年报截至 {end_date}。"
    return evidence


def _article_text(article: ArticleDraft) -> str:
    return "\n".join(
        [
            article.title,
            article.subtitle,
            article.thesis,
            *(s.prose for s in article.sections),
            article.closing,
        ]
    )


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?；;\n]+", text) if part.strip()]


def _contains_fact_signal(sentence: str) -> bool:
    return bool(re.search(r"\d", sentence)) or any(
        token in sentence for token in ("第一", "超过", "高过")
    )


def _is_negated_scope(sentence: str) -> bool:
    return any(
        marker in sentence
        for marker in (
            "不是外部",
            "不是官方",
            "并非外部",
            "并非官方",
            "非外部",
            "非官方",
            "不属于外部",
            "不属于官方",
        )
    )


def _is_safe_context_sentence(sentence: str, brief: ResearchBrief) -> bool:
    end_date = str(brief.period.get("end_date") or "")
    if end_date and end_date in sentence:
        return True
    return not any(
        entity in sentence
        for entity in ("Taylor Swift", "Olivia Rodrigo", "The Life of a Showgirl")
    )


def _matched_refs(sentence: str, evidence: dict[str, str]) -> tuple[str, ...]:
    sentence_tokens = set(_tokens(sentence))
    refs: list[str] = []
    for evidence_id, claim in evidence.items():
        evidence_tokens = set(_tokens(claim))
        if not evidence_tokens:
            continue
        if len(sentence_tokens & evidence_tokens) >= min(3, len(evidence_tokens)):
            refs.append(evidence_id)
    return tuple(refs)


def _tokens(text: str) -> list[str]:
    tokens = re.findall(r"\d{4}-\d{2}-\d{2}|\d{4}-\d{2}|\d+\s*次|\d+\s*周|\d+", text)
    tokens.extend(re.findall(r"[A-Za-z][A-Za-z'&. -]{2,}", text))
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.append(phrase)
        tokens.extend(phrase[index : index + 2] for index in range(max(0, len(phrase) - 1)))
    cleaned = []
    for token in tokens:
        normalized = token.strip().casefold()
        if normalized and normalized not in SAFE_AMBIGUOUS_TERMS:
            cleaned.append(normalized)
    return cleaned
