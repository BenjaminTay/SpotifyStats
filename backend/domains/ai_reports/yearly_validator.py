"""Validation for generated AI yearly reports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.domains.ai_reports.yearly_contract import UNSUPPORTED_SCENE_TERMS

PARTIAL_YEAR_FULL_YEAR_PHRASES = (
    "明年",
    "来年寄语",
    "全年总结",
    "完整全年",
    "这一年已经结束",
    "回望过去一年",
    "回顾过去一年",
    "过去这一年",
    "这一整年",
    "一整年",
    "年末回望",
    "年终总结",
    "年度专辑",
    "年度单曲",
    "年度歌曲",
    "年度曲目",
    "年度艺人",
    "年度冠军",
    "年度排名",
)

FULL_YEAR_PARTIAL_YEAR_PHRASES = (
    "年中",
    "上半年",
    "下半年观察",
    "阶段性总结",
    "阶段性报告",
    "未完整年份",
    "截至目前",
)

PARTIAL_YEAR_FULL_COMPARISON_PHRASES = (
    "去年全年",
    "上一年全年",
    "完整上一年",
    "完整的上一年",
    "去年整年",
    "上一整年",
    "比去年全年",
    "较去年全年",
    "和去年全年相比",
    "与去年全年相比",
)

ALLOWED_PARTIAL_COMPARISON_TERMS = (
    "去年同期",
    "上一年同期",
    "同周期",
    "同一时期",
    "同日起止",
    "截至同日",
    "同日",
    "YTD",
    "ytd",
)

COMPARISON_TERMS = (
    "少",
    "多",
    "降",
    "增",
    "下降",
    "增长",
    "减少",
    "增加",
    "降低",
    "提升",
    "少听",
    "多听",
    "少播放",
    "多播放",
    "一半",
    "%",
    "百分",
)

UNSUPPORTED_NARRATIVE_PHRASES = (
    "雨夜",
    "睡不着",
    "分手",
    "低谷",
    "人生拐点",
    "生活节奏",
    "重要转折",
)

POSITIVE_LOOP_OVERSTATEMENT_PHRASES = (
    "重度单曲循环",
    "重度循环",
    "疯狂循环",
    "反复循环",
    "整天循环",
    "单曲循环日",
    "循环播放",
)

MAX_YEARLY_REPORT_CHARS = 1400

UNSUPPORTED_INTENT_PHRASES = (
    "有意识地",
    "主动拓宽",
    "主动选择",
    "主动扩张",
    "主动扩大",
    "主动突破",
    "刻意",
    "学会了选择",
    "不再是漫无目的",
    "不再重播",
    "转身拥抱",
    "足见你对",
    "持续突破",
)

UNSUPPORTED_FIRST_PERSON_PHRASES = (
    "最让我",
    "让我",
    "我认为",
    "我觉得",
    "我们可以看到",
)

UNSUPPORTED_LYRIC_PHRASES = (
    "歌词中",
    "歌词里",
    "歌词充满",
    "歌词写",
    "歌词表达",
    "歌词讲",
    "歌词描述",
)

UNSUPPORTED_GENDER_PHRASES = (
    "女艺人",
    "女歌手",
    "男艺人",
    "男歌手",
    "两位女艺人",
    "两位男艺人",
    "她的播放",
    "她的歌曲",
    "她的专辑",
    "她的《",
    "她已",
    "她以",
    "他的播放",
    "他的歌曲",
    "他的专辑",
    "他的《",
    "他的存在",
    "她的存在",
    "他已",
    "他以",
)

UNSUPPORTED_TIME_OF_DAY_PHRASES = (
    "每晚平均",
    "夜晚平均",
    "深夜平均",
    "从早燃到晚",
    "从早听到晚",
)


@dataclass(frozen=True)
class YearlyReportIssue:
    code: str
    message: str
    severity: str = "high"


@dataclass(frozen=True)
class YearlyReportValidation:
    ok: bool
    issues: tuple[YearlyReportIssue, ...]

    def retry_instructions(self) -> str:
        if self.ok:
            return ""
        lines = ["请修正上一版年度报告中的问题："]
        lines.extend(f"- {issue.code}: {issue.message}" for issue in self.issues)
        return "\n".join(lines)


def validate_yearly_report(report: str, data: dict[str, Any]) -> YearlyReportValidation:
    issues: list[YearlyReportIssue] = []
    period = data.get("reporting_period")
    if not isinstance(period, dict):
        period = {}
    is_partial = bool(period.get("is_partial_year"))
    end_date = str(period.get("end_date") or "")

    if is_partial:
        if end_date and not _mentions_cutoff_date(report, end_date):
            issues.append(
                YearlyReportIssue(
                    "missing_partial_year_cutoff",
                    f"partial-year report must mention the data cutoff date {end_date}",
                )
            )
        if any(term in report for term in PARTIAL_YEAR_FULL_YEAR_PHRASES):
            issues.append(
                YearlyReportIssue(
                    "partial_year_written_as_full_year",
                    "partial-year report uses full-year or next-year phrasing",
                )
            )
        if _has_forbidden_partial_year_comparison(report):
            issues.append(
                YearlyReportIssue(
                    "partial_year_uses_full_year_comparison",
                    "partial-year report compares against last full year instead of same-period YTD",
                )
            )
    else:
        partial_phrase = _full_year_partial_phrase(report)
        if partial_phrase:
            issues.append(
                YearlyReportIssue(
                    "full_year_written_as_partial_year",
                    f"full-year report uses partial-year phrasing: {partial_phrase}",
                )
            )

    if len(report) > MAX_YEARLY_REPORT_CHARS:
        issues.append(
            YearlyReportIssue(
                "yearly_report_too_long",
                f"yearly report should stay concise; current length is {len(report)} chars",
            )
        )

    if any(term in report for term in ("前者", "后者")):
        issues.append(
            YearlyReportIssue(
                "ambiguous_entity_reference",
                "report should repeat entity names instead of using ambiguous 前者/后者 references",
            )
        )

    for artist in _required_names(data.get("top_artists"), limit=1):
        if artist not in report:
            issues.append(
                YearlyReportIssue(
                    "missing_top_artist",
                    f"report should mention top artist {artist}",
                )
            )
    for track in _required_names(data.get("top_tracks"), limit=1):
        if track not in report:
            issues.append(
                YearlyReportIssue(
                    "missing_top_track",
                    f"report should mention top track {track}",
                )
            )
    for album in _required_names(data.get("top_albums"), limit=1):
        if album not in report:
            issues.append(
                YearlyReportIssue(
                    "missing_top_album",
                    f"report should mention top album {album}",
                )
            )
    for artist in _required_names(data.get("new_artists"), limit=1):
        if artist not in report:
            issues.append(
                YearlyReportIssue(
                    "missing_new_artist",
                    f"report should mention new artist {artist}",
                )
            )

    billboard_year_end = data.get("billboard_year_end")
    if _has_available_billboard_year_end(billboard_year_end) and not _mentions_billboard_evidence(
        report,
        billboard_year_end,
    ):
        issues.append(
            YearlyReportIssue(
                "missing_billboard_year_end_evidence",
                "report should use personal Billboard Year-End evidence when available",
            )
        )
    if _has_available_billboard_year_end(billboard_year_end):
        if _misstates_billboard_scope(report):
            issues.append(
                YearlyReportIssue(
                    "billboard_scope_misstatement",
                    "report must not describe local personal Billboard evidence as official or external Billboard",
                )
            )
        elif not _mentions_personal_billboard_caveat(report):
            issues.append(
                YearlyReportIssue(
                    "missing_personal_billboard_caveat",
                    "report should state that Billboard evidence is local/personal or not official",
                )
            )

    if is_partial and _has_duplicated_same_period_comparison(report):
        issues.append(
            YearlyReportIssue(
                "duplicated_same_period_comparison",
                "same-period comparison should be summarized once, not repeated across sections",
            )
        )

    unsupported_intent = _unsupported_intent_phrase(report)
    if unsupported_intent:
        issues.append(
            YearlyReportIssue(
                "unsupported_intent_claim",
                f"report infers user intent without evidence: {unsupported_intent}",
            )
        )

    unsupported_first_person = _unsupported_first_person_phrase(report)
    if unsupported_first_person:
        issues.append(
            YearlyReportIssue(
                "unsupported_first_person_claim",
                f"report uses first-person narration without evidence: {unsupported_first_person}",
            )
        )

    unsupported_lyric = _unsupported_lyric_phrase(report)
    if unsupported_lyric:
        issues.append(
            YearlyReportIssue(
                "unsupported_lyric_claim",
                f"report interprets lyrics without lyric evidence: {unsupported_lyric}",
            )
        )

    unsupported_gender = _unsupported_gender_phrase(report)
    if unsupported_gender:
        issues.append(
            YearlyReportIssue(
                "unsupported_gender_claim",
                f"report infers artist gender without evidence: {unsupported_gender}",
            )
        )

    unsupported_alias = _unsupported_entity_alias(report, data)
    if unsupported_alias:
        issues.append(
            YearlyReportIssue(
                "unsupported_entity_alias",
                f"report introduces an entity alias not present in data: {unsupported_alias}",
            )
        )

    unsupported_time_of_day = _unsupported_time_of_day_phrase(report)
    if unsupported_time_of_day:
        issues.append(
            YearlyReportIssue(
                "unsupported_time_of_day_claim",
                f"report converts aggregate listening data into an unsupported time-of-day claim: {unsupported_time_of_day}",
            )
        )

    for term in (*UNSUPPORTED_SCENE_TERMS, *UNSUPPORTED_NARRATIVE_PHRASES):
        if term in report:
            issues.append(
                YearlyReportIssue(
                    "unsupported_scene",
                    f"report introduces unsupported narrative scene term: {term}",
                )
            )

    personality = data.get("personality_summary")
    if isinstance(personality, dict):
        for row in personality.get("top_dimensions") or []:
            if not isinstance(row, dict):
                continue
            label = str(row.get("label") or "")
            score = row.get("score")
            if label and _personality_score_without_paired_label(report, label, score):
                issues.append(
                    YearlyReportIssue(
                        "personality_score_without_label",
                        f"score {score} appears as a personality score without its paired label {label}",
                    )
                )

    genre_summary = data.get("genre_summary")
    if not isinstance(genre_summary, dict):
        genre_summary = {}
    if genre_summary.get("has_other_bucket") and "其他流派" not in report:
        issues.append(
            YearlyReportIssue(
                "missing_other_genre_bucket",
                "report omits the top '其他流派' bucket",
            )
        )
    if genre_summary.get("top_genres") and not _mentions_genre_caveat(report):
        issues.append(
            YearlyReportIssue(
                "missing_genre_caveat",
                "report should mention Spotify genre labels may overlap or are not mutually exclusive",
            )
        )

    if _overstates_low_confidence_highlight(report, data.get("most_active_day")):
        issues.append(
            YearlyReportIssue(
                "overstated_low_confidence_highlight",
                "report describes a low-repeat highlight day as heavy looping",
            )
        )

    high_severity = [issue for issue in issues if issue.severity == "high"]
    return YearlyReportValidation(ok=not high_severity, issues=tuple(issues))


def _has_forbidden_partial_year_comparison(report: str) -> bool:
    if any(term in report for term in PARTIAL_YEAR_FULL_COMPARISON_PHRASES):
        return True

    sentences = [part for part in re.split(r"[。！？!?；;\n]+", report) if part.strip()]
    for sentence in sentences:
        if "去年" not in sentence and "上一年" not in sentence:
            continue
        if any(term in sentence for term in ALLOWED_PARTIAL_COMPARISON_TERMS):
            continue
        if any(term in sentence for term in COMPARISON_TERMS):
            return True
    return False


def _full_year_partial_phrase(report: str) -> str:
    for phrase in FULL_YEAR_PARTIAL_YEAR_PHRASES:
        if phrase in report:
            return phrase
    return ""


def _has_available_billboard_year_end(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if value.get("available") is True:
        return True
    return any(
        isinstance(value.get(key), list) and value.get(key)
        for key in ("tracks", "albums", "artists")
    )


def _mentions_billboard_evidence(report: str, value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not any(term in report for term in ("Billboard", "billboard", "年榜", "在榜", "个人榜")):
        return False
    names = []
    for key in ("tracks", "albums", "artists"):
        rows = value.get(key)
        if not isinstance(rows, list):
            continue
        names.extend(_required_names(rows, limit=2))
    if names and not any(name in report for name in names):
        return False
    return any(
        term in report for term in ("排名", "第", "PK", "peak", "峰值", "在榜", "No.1", "冠军")
    )


def _misstates_billboard_scope(report: str) -> bool:
    for term in (
        "外部官方 Billboard",
        "官方 Billboard",
        "官方榜单",
        "全球 Billboard",
        "市场成绩",
    ):
        start = 0
        while True:
            index = report.find(term, start)
            if index < 0:
                break
            context = report[max(0, index - 8) : index + len(term) + 8]
            if not _is_negated_billboard_scope_context(context):
                return True
            start = index + len(term)
    return False


def _is_negated_billboard_scope_context(context: str) -> bool:
    return any(
        marker in context
        for marker in (
            "不是",
            "并非",
            "非官方",
            "非外部官方",
            "不是外部官方",
            "不是官方",
            "不属于官方",
            "并非官方",
        )
    )


def _mentions_personal_billboard_caveat(report: str) -> bool:
    if not any(term in report for term in ("Billboard", "billboard", "年榜", "个人榜")):
        return False
    return any(
        term in report
        for term in (
            "个人 Billboard",
            "个人年榜",
            "本地播放",
            "本地榜",
            "个人播放",
            "不是外部官方",
            "非外部官方",
            "非官方",
            "不是官方",
            "基于播放记录",
            "基于本地播放记录",
        )
    )


def _has_duplicated_same_period_comparison(report: str) -> bool:
    count = 0
    sentences = [part for part in re.split(r"[。！？!?；;\n]+", report) if part.strip()]
    for sentence in sentences:
        if not any(term in sentence for term in ALLOWED_PARTIAL_COMPARISON_TERMS):
            continue
        if any(term in sentence for term in COMPARISON_TERMS):
            count += 1
    return count > 1


def _unsupported_intent_phrase(report: str) -> str:
    for phrase in UNSUPPORTED_INTENT_PHRASES:
        if phrase in report:
            return phrase
    return ""


def _unsupported_lyric_phrase(report: str) -> str:
    for phrase in UNSUPPORTED_LYRIC_PHRASES:
        if phrase in report:
            return phrase
    return ""


def _unsupported_gender_phrase(report: str) -> str:
    for phrase in UNSUPPORTED_GENDER_PHRASES:
        if phrase in report:
            return phrase
    gender_match = re.search(
        r"(?<!其)[她他]的|(?<!其)[她他](?:已|以|是|在|也|则|会|曾|将|都|能|把|直接|迅速)", report
    )
    if gender_match:
        return gender_match.group(0)
    return ""


def _unsupported_first_person_phrase(report: str) -> str:
    for phrase in UNSUPPORTED_FIRST_PERSON_PHRASES:
        if phrase in report:
            return phrase
    return ""


def _unsupported_entity_alias(report: str, data: dict[str, Any]) -> str:
    known_names = set(_known_entity_names(data))
    if not known_names:
        return ""
    alias_pattern = re.compile(r"([\u4e00-\u9fff]{2,12})[（(]\s*([A-Za-z][^）)]{1,80})\s*[）)]")
    for match in alias_pattern.finditer(report):
        alias = match.group(1).strip()
        canonical = match.group(2).strip()
        if (
            canonical in known_names
            and alias not in known_names
            and _looks_like_entity_alias(alias)
        ):
            return f"{alias}({canonical})"
    return ""


def _looks_like_entity_alias(alias: str) -> bool:
    if len(alias) > 6 or alias.startswith(("和", "与", "及")):
        return False
    generic_terms = (
        "入口",
        "主线",
        "艺人",
        "专辑",
        "单曲",
        "音乐",
        "流派",
        "声音",
        "作品",
        "新发现",
    )
    return not any(term in alias for term in generic_terms)


def _known_entity_names(data: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for key in ("top_artists", "top_tracks", "top_albums", "new_artists"):
        names.extend(_required_names(data.get(key), limit=10))
    billboard = data.get("billboard_year_end")
    if isinstance(billboard, dict):
        for key in ("tracks", "albums", "artists"):
            names.extend(_required_names(billboard.get(key), limit=10))
    return names


def _unsupported_time_of_day_phrase(report: str) -> str:
    for phrase in UNSUPPORTED_TIME_OF_DAY_PHRASES:
        if phrase in report:
            return phrase
    return ""


def _mentions_cutoff_date(report: str, end_date: str) -> bool:
    normalized_report = _normalize_date_separators(report)
    normalized_end_date = _normalize_date_separators(end_date)
    if normalized_end_date in normalized_report:
        return True
    try:
        parsed = date.fromisoformat(end_date)
    except ValueError:
        return False
    candidates = {
        f"{parsed.year} 年 {parsed.month} 月 {parsed.day} 日",
        f"{parsed.year}年{parsed.month}月{parsed.day}日",
        f"{parsed.month} 月 {parsed.day} 日",
        f"{parsed.month}月{parsed.day}日",
    }
    return any(candidate in report for candidate in candidates)


def _normalize_date_separators(value: str) -> str:
    return value.replace("‑", "-").replace("–", "-").replace("—", "-").replace("−", "-")


def _personality_score_without_paired_label(report: str, label: str, score: Any) -> bool:
    variants = _score_variants(score)
    for variant in variants:
        start = 0
        while True:
            index = report.find(variant, start)
            if index < 0:
                break
            context = report[max(0, index - 28) : index + len(variant) + 28]
            if _looks_like_personality_score(context, variant) and label not in context:
                return True
            start = index + len(variant)
    return False


def _score_variants(score: Any) -> tuple[str, ...]:
    if not isinstance(score, (int, float)):
        return ()
    numeric = float(score)
    variants = {str(score), f"{numeric:.1f}", f"{numeric:g}"}
    return tuple(variant for variant in variants if variant and variant != "0")


def _looks_like_personality_score(context: str, score_text: str) -> bool:
    if re.search(rf"{re.escape(score_text)}\s*分(?!钟)", context):
        return True
    return any(term in context for term in ("得分", "人格", "维度", "指数", "score", "Score"))


def _mentions_genre_caveat(report: str) -> bool:
    return any(term in report for term in ("重叠", "不互斥", "并不互斥", "标签可能", "流派标签"))


def _overstates_low_confidence_highlight(report: str, most_active_day: Any) -> bool:
    if not isinstance(most_active_day, dict):
        return False
    top_track = most_active_day.get("top_track")
    if not isinstance(top_track, dict):
        top_track = {}
    if int(top_track.get("plays") or 0) >= 8:
        return False
    for term in POSITIVE_LOOP_OVERSTATEMENT_PHRASES:
        start = 0
        while True:
            index = report.find(term, start)
            if index < 0:
                break
            context = report[max(0, index - 8) : index + len(term)]
            if not _is_negated_looping_context(context):
                return True
            start = index + len(term)
    return False


def _is_negated_looping_context(context: str) -> bool:
    return any(marker in context for marker in ("不是", "并非", "非", "而非", "没有", "未"))


def _required_names(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value[:limit]:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names
