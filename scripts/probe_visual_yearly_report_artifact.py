#!/usr/bin/env python3
"""Probe visual yearly report artifacts through the AI task API."""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

FORBIDDEN_TERMS = (
    "稳定中心",
    "之后度",
    "三榜联动",
    "第二层证据",
    "evidence ledger",
    "dynamic outline",
    "综合来看",
    "后续观察",
    "证据强度可以先放在",
    "不要写成",
    "interpretation_guidance",
    "safe_speculation_rules",
    "confidence high",
    "confidence medium",
    "confidence low",
    "confidence=high",
    "confidence=medium",
    "confidence=low",
    "confidence_level",
    "置信度",
)

REPEATED_META_PHRASE = "图表负责回答"
SAME_ENTITY_FALSE_CONTRAST_TERMS = (
    "两种不同",
    "两种喜欢",
    "不同喜欢",
    "不完全相同",
    "一边",
    "另一边",
    "一方面",
    "另一方面",
    "分歧",
)
SAME_ENTITY_FALSE_CONTRAST_NEGATIONS = (
    "不是两种",
    "不是不同",
    "不再生成",
    "不会写成",
    "避免",
    "不要",
    "并非",
)

GOLDEN_TERMS_BY_YEAR = {
    2025: (
        "Taylor Swift",
        "Michael Wong",
        "JOLIN",
        "The Life of a Showgirl",
        "光良「回憶裡的瘋狂」巡迴演唱會",
        "2025-02-14",
    ),
    2026: (
        "截至 2026-06-23",
        "Taylor Swift",
        "Olivia Rodrigo",
        "Zhang Zhen Yue",
        "The Life of a Showgirl",
    ),
}

PLACEHOLDER_TOKENS = ("NaN", "null", "undefined", "unknown")
INTERPRETATION_MARKERS = (
    "说明",
    "意味着",
    "更像",
    "不是",
    "而是",
    "因此",
    "这让",
    "这使",
    "可以看见",
)
INTERNAL_BRIEF_LEAK_PATTERNS = (
    re.compile(r"(?:^|\n)展示.{0,80}(播放量|个人榜单|偏好|关系|证据|趋势)"),
    re.compile(r"(?:^|\n)解释播放领先"),
    re.compile(r"(?:^|\n)揭示偏好深度"),
    re.compile(r"(?:^|\n)说明偏好会在特定月份"),
    re.compile(r"(interpretation_guidance|safe_speculation_rules|evidence_refs|chart_refs)"),
)


def request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Request failed for {url}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--year", type=int)
    parser.add_argument(
        "--mode",
        choices=("single", "changed", "full"),
        default="single",
        help="single probes --year; changed probes 2025 and 2026; full probes all locally meaningful yearly samples.",
    )
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument(
        "--writer-pipeline",
        choices=("editorial_agent_v1", "deterministic_visual_v1"),
        default="editorial_agent_v1",
    )
    parser.add_argument("--json-output", required=True)
    args = parser.parse_args()
    if args.mode == "single" and args.year is None:
        parser.error("--year is required when --mode single")

    base = args.base_url.rstrip("/")
    years = [int(args.year)] if args.year is not None else []
    if args.mode == "changed":
        years = [2025, 2026]
    elif args.mode == "full":
        years = [2022, 2023, 2024, 2025, 2026]

    summaries = [
        _probe_year(
            base=base,
            year=year,
            timeout=args.timeout,
            poll_interval=args.poll_interval,
            writer_pipeline=args.writer_pipeline,
        )
        for year in years
    ]
    if args.mode == "single":
        summary = summaries[0]
        Path(args.json_output).write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary["ok"] else 1

    aggregate = {
        "ok": all(summary["ok"] for summary in summaries),
        "mode": args.mode,
        "summaries": summaries,
        "issues": [
            f"{summary['year']}: {issue}" for summary in summaries for issue in summary["issues"]
        ],
    }
    Path(args.json_output).write_text(json.dumps(aggregate, ensure_ascii=False, indent=2))
    return 0 if aggregate["ok"] else 1


def _probe_year(
    *,
    base: str,
    year: int,
    timeout: int,
    poll_interval: float,
    writer_pipeline: str,
) -> dict[str, Any]:
    task = request_json(
        f"{base}/api/ai/tasks/report",
        method="POST",
        payload={
            "report_type": "yearly",
            "action": "generate",
            "report_mode": "visual_yearly_artifact",
            "writer_pipeline": writer_pipeline,
            "year": year,
            "force": True,
        },
    )
    task_id = str(task["task_id"])
    deadline = time.time() + timeout
    detail: dict[str, Any] = {}
    while time.time() < deadline:
        detail = request_json(f"{base}/api/ai/tasks/{task_id}")
        if detail.get("status") in {"done", "error", "cancelled"}:
            break
        time.sleep(poll_interval)

    return _build_summary(
        year=year,
        task_id=task_id,
        detail=detail,
        result=_dict(detail.get("result")),
        writer_pipeline=writer_pipeline,
    )


def _build_summary(
    *,
    year: int,
    task_id: str,
    detail: dict[str, Any],
    result: dict[str, Any],
    writer_pipeline: str,
) -> dict[str, Any]:
    result = _dict(result) or _dict(detail.get("result"))
    artifact = _dict(result.get("artifact"))
    metadata = _dict(result.get("metadata"))
    sections = _list(artifact.get("sections"))
    chart_specs = _list(artifact.get("chart_specs"))
    chart_data = _dict(artifact.get("chart_data"))
    prose = _artifact_text(result, artifact, sections)
    quality_checks = _quality_checks(
        year=year,
        artifact=artifact,
        sections=sections,
        chart_data=chart_data,
        prose=prose,
        writer_pipeline=writer_pipeline,
    )
    issues = _validate(
        year=year,
        detail=detail,
        result=result,
        artifact=artifact,
        metadata=metadata,
        sections=sections,
        chart_specs=chart_specs,
        chart_data=chart_data,
        prose=prose,
        writer_pipeline=writer_pipeline,
    )

    return {
        "ok": not issues,
        "issues": issues,
        "year": year,
        "task_id": task_id,
        "status": detail.get("status"),
        "metadata": metadata,
        "artifact_metadata": quality_checks["artifact_metadata"],
        "section_count": len(sections),
        "chart_count": len(chart_specs),
        "resolved_chart_data_count": len(chart_data),
        "insight_card_count": len(_list(artifact.get("insight_cards"))),
        "article_length": len(prose),
        "visual_brief_outline_roles": quality_checks["visual_brief_outline_roles"],
        "quality_checks": quality_checks,
        "title": artifact.get("title"),
        "subtitle": artifact.get("subtitle"),
        "preview": prose[:800],
    }


def _validate(
    *,
    year: int,
    detail: dict[str, Any],
    result: dict[str, Any],
    artifact: dict[str, Any],
    metadata: dict[str, Any],
    sections: list[dict[str, Any]],
    chart_specs: list[dict[str, Any]],
    chart_data: dict[str, Any],
    prose: str,
    writer_pipeline: str,
) -> list[str]:
    issues: list[str] = []
    quality_checks = _quality_checks(
        year=year,
        artifact=artifact,
        sections=sections,
        chart_data=chart_data,
        prose=prose,
        writer_pipeline=writer_pipeline,
    )
    if detail.get("status") != "done":
        issues.append(f"task status is {detail.get('status')}")
    if metadata.get("report_mode") != "visual_yearly_artifact":
        issues.append("metadata report_mode is not visual_yearly_artifact")
    if metadata.get("contract_version") != "visual_yearly_v1":
        issues.append("contract_version is not visual_yearly_v1")
    if artifact.get("contract_version") != "visual_yearly_v1":
        issues.append("artifact contract_version is not visual_yearly_v1")
    if writer_pipeline == "editorial_agent_v1":
        if metadata.get("writer_pipeline_version") != "yearly_editorial_agent_v1":
            issues.append("metadata writer_pipeline_version is not yearly_editorial_agent_v1")
        if metadata.get("writer_pipeline_status") == "accepted":
            if metadata.get("claim_check_passed") is not True:
                issues.append("metadata claim_check_passed is not true")
            taste_score = _dict(metadata.get("taste_score"))
            if taste_score.get("ok") is not True:
                issues.append("metadata taste_score.ok is not true")
    artifact_metadata = quality_checks["artifact_metadata"]
    if artifact_metadata.get("critic_passed") is not True:
        issues.append("artifact.metadata.critic_passed is not true")
    if artifact_metadata.get("fact_validation_passed") is not True:
        issues.append("artifact.metadata.fact_validation_passed is not true")
    if artifact_metadata.get("editorial_plan_version") != "yearly_editorial_v1":
        issues.append("artifact metadata editorial_plan_version is not yearly_editorial_v1")
    if not artifact_metadata.get("section_roles"):
        issues.append("artifact metadata section_roles is empty")
    if _safe_int(artifact_metadata.get("fact_count")) < 5:
        issues.append("artifact metadata fact_count < 5")
    if len(sections) < 6:
        issues.append("section_count < 6")
    if len(chart_specs) < 4:
        issues.append("chart_count < 4")
    if len(chart_data) < 4:
        issues.append("resolved chart_data count < 4")
    if len(_list(artifact.get("insight_cards"))) < 3:
        issues.append("insight_card_count < 3")
    if len(prose) < quality_checks["min_article_length"]:
        if quality_checks["is_partial_year"]:
            issues.append(f"partial-year prose length < {quality_checks['min_article_length']}")
        else:
            issues.append(f"full-year prose length < {quality_checks['min_article_length']}")
    if year >= 2026 and "截至" not in prose + str(artifact.get("subtitle") or ""):
        issues.append("partial-year report does not mention cutoff")

    missing_refs = sorted(
        {
            str(ref)
            for section in sections
            for ref in section.get("chart_refs", [])
            if ref not in chart_data
        }
    )
    if missing_refs:
        issues.append("missing chart refs: " + ", ".join(missing_refs))

    missing_observations = [
        f"{row['section_id']} -> {row['chart_id']}"
        for row in quality_checks["chart_observation_checks"]
        if not row["passed"]
    ]
    if missing_observations:
        issues.append("missing chart observations: " + ", ".join(missing_observations))
    echo_failures = [
        f"{row['section_id']} -> {row['chart_id']}"
        for row in quality_checks["chart_observation_checks"]
        if row.get("echo_failed")
    ]
    if echo_failures:
        issues.append("chart prose echo without interpretation: " + ", ".join(echo_failures))

    forbidden = _forbidden_terms(prose)
    if forbidden:
        issues.append("forbidden terms: " + ", ".join(forbidden))
    placeholder_tokens = quality_checks["invalid_placeholder_tokens"]
    if placeholder_tokens:
        issues.append("invalid placeholder tokens: " + ", ".join(placeholder_tokens))
    internal_brief_leaks = quality_checks["internal_brief_leaks"]
    if internal_brief_leaks:
        issues.append("internal brief leakage in sections: " + ", ".join(internal_brief_leaks))
    duplicate_chart_refs = quality_checks["duplicate_chart_refs"]
    if duplicate_chart_refs:
        issues.append("duplicate chart refs: " + ", ".join(duplicate_chart_refs))
    artifact_metadata = quality_checks["artifact_metadata"]
    if writer_pipeline == "editorial_agent_v1":
        if artifact_metadata.get("final_artifact_quality_passed") is not True:
            issues.append("metadata final_artifact_quality_passed is not true")
        final_quality = _dict(artifact_metadata.get("final_artifact_quality"))
        if final_quality and final_quality.get("ok") is not True:
            issues.append("metadata final_artifact_quality.ok is not true")
    if prose.count(REPEATED_META_PHRASE) > 1:
        issues.append("repeated meta prose: " + REPEATED_META_PHRASE)
    same_album_false_contrast = _same_album_false_contrast(artifact, prose)
    if same_album_false_contrast:
        issues.append("same-album false contrast: " + same_album_false_contrast)
    if _has_unsupported_olivia_claim(prose):
        issues.append("unsupported Olivia Rodrigo regional/live/nostalgia claim")
    if not _dict(result.get("critic")).get("ok"):
        issues.append("visual critic did not pass")
    if not _dict(result.get("fact_validation")).get("ok"):
        issues.append("fact validation did not pass")

    for term in GOLDEN_TERMS_BY_YEAR.get(year, ()):
        if term not in prose and term not in json.dumps(artifact, ensure_ascii=False):
            issues.append(f"missing golden term: {term}")
    if year == 2025 and not any(
        phrase in prose for phrase in ("两种不同的喜欢", "常听和长留", "播放量领先")
    ):
        issues.append("missing playback-vs-personal-chart interpretation")
    return issues


def _quality_checks(
    *,
    year: int,
    artifact: dict[str, Any],
    sections: list[dict[str, Any]],
    chart_data: dict[str, Any],
    prose: str,
    writer_pipeline: str,
) -> dict[str, Any]:
    artifact_metadata = _dict(artifact.get("metadata"))
    min_article_length = 1800 if _is_partial_year(year, artifact) else 2800
    chart_observation_checks = _chart_observation_checks(sections, chart_data)
    return {
        "artifact_metadata": {
            "critic_passed": artifact_metadata.get("critic_passed"),
            "fact_validation_passed": artifact_metadata.get("fact_validation_passed"),
            "editorial_plan_version": artifact_metadata.get("editorial_plan_version"),
            "writer_pipeline_version": artifact_metadata.get("writer_pipeline_version"),
            "writer_pipeline_status": artifact_metadata.get("writer_pipeline_status"),
            "claim_check_passed": artifact_metadata.get("claim_check_passed"),
            "taste_score": artifact_metadata.get("taste_score"),
            "section_roles": artifact_metadata.get("section_roles"),
            "fact_count": artifact_metadata.get("fact_count"),
            "final_artifact_quality_passed": artifact_metadata.get("final_artifact_quality_passed"),
            "final_artifact_quality": artifact_metadata.get("final_artifact_quality"),
        },
        "writer_pipeline": writer_pipeline,
        "is_partial_year": _is_partial_year(year, artifact),
        "article_length": len(prose),
        "min_article_length": min_article_length,
        "article_length_passed": len(prose) >= min_article_length,
        "chart_observation_checks": chart_observation_checks,
        "missing_chart_observation_refs": [
            f"{row['section_id']} -> {row['chart_id']}"
            for row in chart_observation_checks
            if not row["passed"]
        ],
        "visual_brief_outline_roles": _visual_brief_outline_roles(artifact),
        "invalid_placeholder_tokens": _invalid_placeholder_tokens(prose),
        "internal_brief_leaks": _internal_brief_leaks(artifact, sections),
        "duplicate_chart_refs": _duplicate_chart_refs(sections),
    }


def _is_partial_year(year: int, artifact: dict[str, Any]) -> bool:
    period = _dict(artifact.get("period"))
    if isinstance(period.get("is_partial_year"), bool):
        return bool(period["is_partial_year"])
    return year >= 2026


def _chart_observation_checks(
    sections: list[dict[str, Any]],
    chart_data: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        section_text = _section_body_text(section)
        for ref in section.get("chart_refs") or []:
            chart_id = str(ref)
            observations = _chart_observations(chart_data, chart_id)
            if not observations:
                continue
            matched = [
                observation
                for observation in observations
                if _uses_chart_observation(section_text, observation)
            ]
            echoed = [
                observation
                for observation in observations
                if _is_chart_echo(section_text, observation)
            ]
            checks.append(
                {
                    "section_id": section_id,
                    "chart_id": chart_id,
                    "observation_count": len(observations),
                    "matched_observation_count": len(matched),
                    "matched_observations": matched[:3],
                    "echoed_observations": echoed[:3],
                    "echo_failed": bool(echoed),
                    "passed": bool(matched),
                }
            )
    return checks


def _uses_chart_observation(section_text: str, observation: str) -> bool:
    if observation in section_text:
        return _has_interpretation_marker(section_text.replace(observation, "", 1))
    tokens = _observation_tokens(observation)
    if not tokens:
        return False
    matched = sum(1 for token in tokens if token in section_text)
    return matched >= min(3, len(tokens)) and _has_interpretation_marker(section_text)


def _is_chart_echo(section_text: str, observation: str) -> bool:
    return observation in section_text and not _has_interpretation_marker(
        section_text.replace(observation, "", 1)
    )


def _has_interpretation_marker(text: str) -> bool:
    return any(marker in text for marker in INTERPRETATION_MARKERS)


def _observation_tokens(observation: str) -> list[str]:
    tokens: list[str] = []
    tokens.extend(re.findall(r"\d{4}-\d{2}", observation))
    tokens.extend(re.findall(r"\d+\s*次", observation))
    tokens.extend(
        re.findall(
            r"\b[A-Z][A-Za-z0-9'&.-]*(?:\s+(?:[A-Z][A-Za-z0-9'&.-]*|of|a|the|and|de|la|van))*",
            observation,
        )
    )
    return list(dict.fromkeys(tokens))


def _chart_observations(chart_data: dict[str, Any], chart_id: str) -> list[str]:
    payload = _dict(chart_data.get(chart_id))
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return []
    return [item.strip() for item in observations if isinstance(item, str) and item.strip()]


def _section_body_text(section: dict[str, Any]) -> str:
    return "\n".join(
        str(part or "")
        for part in (
            section.get("deck"),
            section.get("prose"),
            section.get("pull_quote"),
        )
    )


def _internal_brief_leaks(artifact: dict[str, Any], sections: list[dict[str, Any]]) -> list[str]:
    leaks: list[str] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        visible = _section_body_text(section)
        if any(pattern.search(visible.strip()) for pattern in INTERNAL_BRIEF_LEAK_PATTERNS):
            leaks.append(section_id)
    for card in _list(artifact.get("insight_cards")):
        card_id = str(card.get("id") or card.get("label") or "unknown")
        visible = "\n".join(str(card.get(key) or "") for key in ("label", "value", "caption"))
        if any(pattern.search(visible.strip()) for pattern in INTERNAL_BRIEF_LEAK_PATTERNS):
            leaks.append(f"insight_card:{card_id}")
    return leaks


def _duplicate_chart_refs(sections: list[dict[str, Any]]) -> list[str]:
    owner: dict[str, str] = {}
    duplicates: list[str] = []
    for section in sections:
        section_id = str(section.get("id") or section.get("heading") or "unknown")
        for ref in section.get("chart_refs") or []:
            chart_id = str(ref)
            previous = owner.get(chart_id)
            if previous:
                duplicates.append(f"{chart_id}: {previous}, {section_id}")
            else:
                owner[chart_id] = section_id
    return duplicates


def _visual_brief_outline_roles(artifact: dict[str, Any]) -> list[str]:
    visual_brief = _dict(artifact.get("visual_brief"))
    return [
        str(section.get("role"))
        for section in _list(visual_brief.get("outline_sections"))
        if section.get("role")
    ]


def _invalid_placeholder_tokens(prose: str) -> list[str]:
    found: set[str] = set()
    for token in PLACEHOLDER_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", prose, re.IGNORECASE):
            found.add("NaN" if token.casefold() == "nan" else token.casefold())
    return sorted(found, key=str.casefold)


def _forbidden_terms(prose: str) -> list[str]:
    folded = prose.casefold()
    return [term for term in FORBIDDEN_TERMS if term.casefold() in folded]


def _artifact_text(
    result: dict[str, Any],
    artifact: dict[str, Any],
    sections: list[dict[str, Any]],
) -> str:
    section_text = _sections_text(sections)
    insight_cards_text = _insight_cards_text(artifact)
    fallback_report = "" if section_text else str(result.get("report") or "")
    return "\n".join(
        str(part or "")
        for part in (
            artifact.get("title"),
            artifact.get("subtitle"),
            insight_cards_text,
            section_text,
            fallback_report,
        )
    )


def _sections_text(sections: list[dict[str, Any]]) -> str:
    return "\n".join(
        "\n".join(
            str(part or "")
            for part in (
                section.get("heading"),
                section.get("deck"),
                section.get("prose"),
                section.get("pull_quote"),
            )
        )
        for section in sections
    )


def _insight_cards_text(artifact: dict[str, Any]) -> str:
    return "\n".join(
        "\n".join(
            str(part or "") for part in (card.get("label"), card.get("value"), card.get("caption"))
        )
        for card in _list(artifact.get("insight_cards"))
    )


def _has_unsupported_olivia_claim(prose: str) -> bool:
    unsupported_terms = ("华语", "中文", "现场感", "回望")
    negations = (
        "不是华语",
        "不属于华语",
        "不应强行绑定",
        "不能强行绑定",
        "不适合写成",
        "没有证据",
        "避免把",
        "不要把",
        "不得把",
        "而不是把",
    )
    sentences = [part for part in re.split(r"[。！？!?；;\n]+", prose) if part]
    for index, sentence in enumerate(sentences):
        has_entity = "Olivia Rodrigo" in sentence
        previous_has_entity = index > 0 and "Olivia Rodrigo" in sentences[index - 1]
        if not has_entity and not previous_has_entity:
            continue
        window = sentence if has_entity else f"{sentences[index - 1]}。{sentence}"
        if not any(term in window for term in unsupported_terms):
            continue
        if any(negation in window for negation in negations):
            continue
        return True
    return False


def _same_album_false_contrast(artifact: dict[str, Any], prose: str) -> str:
    period = _dict(artifact.get("period"))
    if not period:
        period = {}
    story = _dict(artifact.get("story_insights"))
    album = _dict(story.get("album_relation"))
    playback = str(album.get("playback_leader") or "")
    chart = str(album.get("chart_leader") or "")
    if not playback or not chart or playback.strip().casefold() != chart.strip().casefold():
        return ""
    album_mentions = prose.casefold().count(playback.casefold())
    if album_mentions < 1:
        return ""
    for sentence in re.split(r"[。！？!?；;\n]+", prose):
        if not any(term in sentence for term in SAME_ENTITY_FALSE_CONTRAST_TERMS):
            continue
        if any(negation in sentence for negation in SAME_ENTITY_FALSE_CONTRAST_NEGATIONS):
            continue
        if (
            playback in sentence
            or chart in sentence
            or "播放量" in sentence
            or "个人榜单" in sentence
        ):
            return playback
    return ""


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[dict[str, Any]]:
    return [row for row in value or [] if isinstance(row, dict)]


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
