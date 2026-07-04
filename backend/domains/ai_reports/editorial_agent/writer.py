"""Longform article writer for yearly editorial-agent reports."""

from __future__ import annotations

import re

from backend.domains.ai_reports.editorial_agent.llm_steps import ChatFn, call_json_step
from backend.domains.ai_reports.editorial_agent.models import (
    ArticleDraft,
    ArticleSection,
    ResearchBrief,
    StorylinePlan,
)
from backend.domains.ai_reports.editorial_agent.prompts import WRITER_SYSTEM_PROMPT

_FALLBACK_CHART_REFS = {
    "opening": ("listening_calendar",),
    "stable_top_artist": ("listening_calendar",),
    "monthly_turning_point": ("artist_monthly_trend",),
    "album_playback_billboard_alignment": ("album_duality_compare", "playback_billboard_matrix"),
    "album_playback_billboard_tension": ("album_duality_compare", "playback_billboard_matrix"),
    "highlight_day_density": ("highlight_day_timeline",),
    "discovery_signal": ("discovery_timeline",),
}


def write_article(
    brief: ResearchBrief,
    plan: StorylinePlan,
    *,
    chart_data: dict,
    chat_fn: ChatFn | None = None,
) -> ArticleDraft:
    parsed = call_json_step(
        WRITER_SYSTEM_PROMPT,
        {
            "research_brief": brief.to_dict(),
            "storyline_plan": plan.to_dict(),
            "chart_data_keys": sorted(chart_data),
        },
        temperature=0.35,
        chat_fn=chat_fn,
    )
    draft = ArticleDraft.from_dict(parsed)
    return draft if _draft_is_usable(draft, plan, brief) else _fallback_draft(brief, plan)


def fallback_article(brief: ResearchBrief, plan: StorylinePlan) -> ArticleDraft:
    """Return the deterministic longform article used when LLM drafts fail quality gates."""
    return _fallback_draft(brief, plan)


def _draft_is_usable(draft: ArticleDraft, plan: StorylinePlan, brief: ResearchBrief) -> bool:
    if not draft.title or not draft.sections:
        return False
    expected_sections = max(5, min(8, max(1, len(plan.section_plan))))
    if len(draft.sections) < expected_sections:
        return False
    if not any(section.evidence_refs for section in draft.sections):
        return False
    text = "\n".join(section.prose for section in draft.sections) + "\n" + (draft.closing or "")
    if len(text) < _minimum_article_chars(brief):
        return False
    return True


def _fallback_draft(brief: ResearchBrief, plan: StorylinePlan) -> ArticleDraft:
    evidence_by_id = {item.id: item.claim for item in brief.evidence_ledger}
    plan_sections = _sections_with_backbone(brief, plan)
    sections = tuple(
        section.__class__(
            id=section.id,
            heading=_soften_heading(section.heading),
            purpose=section.purpose,
            prose=_fallback_section_prose(
                section.id,
                _soften_heading(section.heading),
                [evidence_by_id[ref] for ref in section.evidence_refs if ref in evidence_by_id],
            ),
            evidence_refs=section.evidence_refs,
            chart_refs=section.chart_refs or _FALLBACK_CHART_REFS.get(section.id, ()),
        )
        for section in plan_sections
    )
    base_closing = (
        "这份记录保留了当前数据能支持的音乐变化。它不替你编造某一天发生了什么，"
        "也不把每个排名都写成夸张结论，而是把稳定回访、阶段变化、专辑长留、"
        "密集播放日和新声音并排放好。等下一次再看这份年记时，真正值得比较的不是"
        "某个数字有没有变大，而是这些关系有没有改变：最常回到的声音是否还在，"
        "阶段性变亮的支线是否留下，新出现的名字是否继续长大，常听和长留是否仍然靠近。"
        "如果后面这些关系发生移动，变化会比单独的榜首更有意思；如果它们仍然稳定，"
        "那也说明某些声音已经从一时喜欢变成了日常里的固定坐标。这样读下来，播放记录就不只是"
        "统计表，而是一份关于你怎样使用音乐、怎样在熟悉和新鲜之间分配注意力的私人档案。"
    )
    return ArticleDraft(
        title=plan.title,
        subtitle=plan.subtitle,
        thesis=plan.thesis,
        sections=sections,
        closing=_closing_with_length_floor(brief, sections, base_closing),
    )


def _fallback_section_prose(section_id: str, heading: str, facts: list[str]) -> str:
    fact_text = " ".join(facts)
    if section_id not in _FALLBACK_CHART_REFS:
        inferred = _infer_section_id_from_facts(fact_text)
        if inferred:
            return _fallback_section_prose(inferred, heading, facts)
    if section_id == "opening":
        return (
            f"{fact_text} 把这些线索放在一起看，这份年记的重点不是重排榜单，"
            "而是看音乐怎样在当前统计期反复出现：有稳定回访，也有阶段转亮。"
            "一个年度故事不能只从最高名次开始，也不能停在总播放量结束。"
            "更有意思的是，不同尺度会给出不同答案：艺人榜看见你反复回到谁，"
            "月份变化看见哪条声音曾经突然变亮，专辑关系看见常听和长留是否指向同一处。"
            "这些线索合在一起，才像一份真正能回看的音乐年记。"
            "它既需要承认数据的边界，也需要给数字之间的关系留出空间：谁承担了稳定感，"
            "谁代表了阶段性的兴奋，哪张专辑只是被密集点开，哪张又在更长时间里留下。"
            "所以接下来的叙述会把榜单当作证据，而不是把榜单本身当作结论。"
        )
    if section_id == "stable_top_artist":
        return (
            f"{fact_text} 这让年度第一不只是一个名次，"
            "而是一条你持续回到的声音线。它说明最熟悉的选择仍然占据可靠位置。"
            "稳定并不等于单调，它更像一种低阻力的回访：当不知道听什么时，"
            "这个声音仍然容易被选中；当歌单里有许多新名字时，它也没有被挤出核心位置。"
            "所以这一节不只是在说谁排第一，而是在说哪一个声音承担了最多次的返回。"
            "这种返回感很重要，因为它通常不是一次性爆发，而是很多个普通时刻的重复选择。"
            "它可能出现在工作间隙、路上、休息前，也可能只是你打开播放器时最不用犹豫的答案。"
            "年度报告真正能补上的，是把这些零散选择重新连成一条线。"
        )
    if section_id == "monthly_turning_point":
        return (
            f"{fact_text} 这个变化提醒我们，累计排名之外还存在月份里的变化。"
            "有些声音不是全年一直领先，却会在某个阶段忽然变得更清楚。"
            "如果只看累计总量，这种阶段变化很容易被压平；但把月份摊开后，"
            "你会看到偏好并不是一条直线。它会在某些时段靠近熟悉对象，"
            "也会在某些时段被另一种情绪暂时接管。年度报告的价值，正在于把这种移动留下来。"
            "这些变化不一定意味着旧偏好被推翻，更像是在原有版图上多出一块临时亮起的区域。"
            "它让这份报告拥有时间感：不是所有喜欢都以同样速度发生，也不是所有主线都从一月延续到最后。"
        )
    if section_id in {"album_playback_billboard_alignment", "album_playback_billboard_tension"}:
        return (
            f"{fact_text} 专辑段最值得看的，是常听和长留之间的关系。"
            "播放次数更接近当下反复选择，个人榜单则保留跨周持续性，两者合在一起才更完整。"
            "如果两条线索指向同一张专辑，那它就不只是短期高频，也不是只靠榜单惯性留下，"
            "而是在即时热度和更长周期里都占据位置。"
            "如果两条线索分开，它也不是互相矛盾，而是在提醒我们：喜欢可以有不同形态，"
            "有的作品适合密集点开，有的作品则适合隔一段时间仍然回来。"
            "这也是个人 Billboard 应该进入年报的原因：它不是外部权威榜单，而是一种把你的播放记录重新按周沉淀的视角。"
            "它让报告能区分“最近特别常听”和“在更长时间里一直有存在感”这两种不同的喜欢。"
        )
    if section_id == "highlight_day_density":
        return (
            f"{fact_text} 这一天更适合被理解为播放密度升高，"
            "而不是被写成某个确定生活事件。它只说明那天音乐明显更靠前。"
            "高光日的意义不一定来自单曲循环，也不一定需要一个外部故事来解释。"
            "只要播放片段在同一天突然变多，它就已经形成了年度里的一个截面。"
            "这种截面保留的是节奏变化：某一天，音乐从背景里向前走了一步。"
            "如果当天最高单曲并没有压倒性循环，这个高光就更像一种分散但密集的陪伴，"
            "说明你不是被一首歌困住，而是在同一天让很多声音轮流出现。这样的日子很适合用图表呈现，"
            "因为它的重点不是戏剧性，而是密度。"
        )
    if section_id == "discovery_signal":
        return (
            f"{fact_text} 新声音的意义不在于立刻成为主角，而在于它已经开始改变原本熟悉的听歌路径。"
            "一个新名字进入记录，通常先是一条小支线：它可能继续长大，"
            "也可能只是这一阶段清楚出现过的岔路。无论最后是哪一种，"
            "它都证明这份年记不是被旧偏好完全占满，你的耳朵仍然给新方向留了位置。"
            "这类线索往往比年度第一更脆弱，也更值得保留：它们记录的是偏好刚刚打开时的样子。"
            "之后它可能变成新的主线，也可能只留下短暂的印记，但在当下，它已经改变了年度叙事的颜色。"
        )
    if section_id == "year_shape":
        return (
            f"{fact_text} 年度概览真正有用的地方，不是把分钟数和播放次数摆在开头，"
            "而是用它们判断这一年的听歌方式。播放量说明音乐出现的频率，活跃日说明它是否持续进入日常，"
            "不同曲目和艺人数则说明你有没有把注意力分给更多对象。"
            "如果总量下降但覆盖面上升，这通常不是简单的“少听了”，而是听法发生变化："
            "你可能减少了机械循环，却让更多作品进入候选。"
            "这种变化比单一数字更接近生活里的真实听感，因为一个人如何使用音乐，往往同时包含专注、分散、回访和探索。"
        )
    if section_id == "chart_relationship":
        return (
            f"{fact_text} 个人 Billboard 的价值在这里变得清楚：它不是拿外部榜单给你的口味背书，"
            "而是把本地播放记录按周重新组织，让短期热度和长期停留分开说话。"
            "播放排行回答“你点开了多少次”，个人榜单回答“它在多少个周期里持续有位置”。"
            "年报如果只讲播放排行，会把所有喜欢压成同一种强度；加入个人 Billboard 后，"
            "就能看见某些作品虽然不是瞬时播放最多，却更耐留，某些作品则是阶段性燃得很亮。"
            "这会让报告从总结变成解释。"
        )
    if section_id == "turning_points":
        return (
            f"{fact_text} 阶段变化是年度报告里最容易被遗漏、也最值得写的部分。"
            "它可能是一位新艺人出现，也可能是一张专辑突然占据更多时间，或者某一天播放密度明显升高。"
            "这些变化不一定会改写年终第一，但它们会改变这一年被记住的方式。"
            "如果说稳定对象构成背景，那么这些变化就是画面里突然亮起的地方。"
            "它们让报告拥有陪伴感：你不是在看一张静止榜单，而是在回看音乐如何随时间靠近又离开。"
        )
    if section_id == "taste_reading":
        return (
            f"{fact_text} 把这些数字合起来看，你的口味并不是单纯追逐新鲜，也不是完全守在旧歌里。"
            "更准确的说法是：稳定对象提供安全感，阶段性发现提供变化，个人 Billboard 保留长期关系，"
            "高光日则记录音乐突然被需要的密度。"
            "这种结构让年度报告有了人的形状。它不需要替你解释每一次播放背后的现实原因，"
            "只需要诚实地指出：你把大量普通时刻交给了哪些声音，又在哪些地方给新东西开了门。"
            "这比单纯说“你最喜欢谁”更接近实际的听歌体验。"
        )
    return (
        f"{fact_text} {heading} 不是孤立数字，"
        "它需要被放回年度时间线里理解：哪些声音留下，哪些变化刚刚出现。"
        "当数据被写成文章时，重点不是把每个名次念完，"
        "而是说明这些名次之间形成了什么关系。"
        "这个关系可能是稳定和探索之间的拉扯，也可能是播放量和个人榜单之间的互补。"
        "只有把这些关系讲出来，年报才不会像页面内容的重述，而会变成一次真正的年度回看。"
    )


def _infer_section_id_from_facts(fact_text: str) -> str:
    if "超过" in fact_text or "高过" in fact_text:
        return "monthly_turning_point"
    if "个人 Billboard" in fact_text or "个人榜在榜" in fact_text:
        return "album_playback_billboard_alignment"
    if "播放密度" in fact_text or re.search(r"\d{4}-\d{2}-\d{2} 有 \d+ 次播放", fact_text):
        return "highlight_day_density"
    if "首次出现" in fact_text or "新声音" in fact_text:
        return "discovery_signal"
    if "艺人榜第一" in fact_text:
        return "stable_top_artist"
    return ""


def _soften_heading(value: str) -> str:
    return (
        value.replace("证据", "痕迹")
        .replace("结构", "听歌版图")
        .replace("画像", "样子")
        .replace("重心", "位置")
    )


def _minimum_article_chars(brief: ResearchBrief) -> int:
    return 1800 if brief.period.get("is_partial_year") else 2800


def _closing_with_length_floor(
    brief: ResearchBrief,
    sections: tuple[ArticleSection, ...],
    base_closing: str,
) -> str:
    closing = base_closing
    current_text = "\n".join(section.prose for section in sections) + "\n" + closing
    for paragraph in _FALLBACK_CLOSING_EXTENSIONS:
        if len(current_text) >= _minimum_article_chars(brief):
            break
        closing += paragraph
        current_text = "\n".join(section.prose for section in sections) + "\n" + closing
    return closing


_FALLBACK_CLOSING_EXTENSIONS = (
    (
        "还有一点值得保留：年报里的“喜欢”不应该只被最高播放次数定义。"
        "有些声音提供的是稳定背景，有些作品提供的是阶段性出口，有些专辑则通过个人 Billboard "
        "证明自己不是短暂经过。把这些层次放在一起，你看到的不是一份获奖名单，"
        "而是一种听歌秩序：哪些声音最容易被你信任，哪些变化让这一年不至于只重复旧答案。"
    ),
    (
        "因此，这份报告更适合被当作一封写给未来自己的旁注。以后再回看这些图表时，"
        "你不只会知道哪首歌排第一，也会更容易想起那一年音乐在生活里承担的功能："
        "它有时是日常燃料，有时是情绪缓冲，有时只是让某个普通日子变得更容易被记住。"
        "这些解释都来自播放记录本身，而不是外加的剧情。"
    ),
    (
        "如果要给这份年记留下一个继续观察的问题，那就是：稳定位置会不会继续稳定，"
        "新出现的支线会不会长成新的中心，播放量和个人 Billboard 是否还会指向同一批作品。"
        "这些问题比单次排名更适合作为下一阶段的线索，也让 AI 年报真正区别于普通统计页面。"
    ),
)


def _sections_with_backbone(
    brief: ResearchBrief,
    plan: StorylinePlan,
) -> tuple[ArticleSection, ...]:
    sections = list(plan.section_plan)
    existing_ids = {section.id for section in sections}
    for candidate in brief.story_candidates:
        if len(sections) >= 6:
            break
        if candidate.id in existing_ids:
            continue
        sections.append(
            ArticleSection(
                id=candidate.id,
                heading=candidate.title,
                purpose=candidate.why_it_matters,
                prose="",
                evidence_refs=candidate.evidence_refs,
                chart_refs=(),
            )
        )
        existing_ids.add(candidate.id)
    for section in _generic_backbone_sections(brief):
        if len(sections) >= 6:
            break
        if section.id in existing_ids:
            continue
        sections.append(section)
        existing_ids.add(section.id)
    return tuple(sections)


def _generic_backbone_sections(brief: ResearchBrief) -> tuple[ArticleSection, ...]:
    return (
        ArticleSection(
            id="year_shape",
            heading="这一年的听歌方式先变成一种样子",
            purpose="解释概览数字背后的听法变化。",
            prose="",
            evidence_refs=_evidence_refs(brief, ("playback_rank", "monthly_shift")),
            chart_refs=("listening_calendar",),
        ),
        ArticleSection(
            id="chart_relationship",
            heading="个人 Billboard 让喜欢多了一层时间感",
            purpose="解释播放量和个人榜单的互补。",
            prose="",
            evidence_refs=_evidence_refs(brief, ("playback_billboard_relation", "playback_rank")),
            chart_refs=("playback_billboard_matrix",),
        ),
        ArticleSection(
            id="turning_points",
            heading="密集播放日和新声音是阶段变化的入口",
            purpose="保留年度里的阶段性变化。",
            prose="",
            evidence_refs=_evidence_refs(brief, ("monthly_shift", "day_density", "discovery")),
            chart_refs=("highlight_day_timeline", "discovery_timeline"),
        ),
        ArticleSection(
            id="taste_reading",
            heading="这些数字合在一起，更像一种使用音乐的方式",
            purpose="把统计结果转译为偏好解释。",
            prose="",
            evidence_refs=_evidence_refs(
                brief,
                ("playback_rank", "playback_billboard_relation", "day_density", "discovery"),
            ),
            chart_refs=("genre_map",),
        ),
    )


def _evidence_refs(brief: ResearchBrief, kinds: tuple[str, ...]) -> tuple[str, ...]:
    refs = [item.id for item in brief.evidence_ledger if item.kind in kinds]
    if not refs:
        refs = [item.id for item in brief.evidence_ledger[:3]]
    return tuple(refs[:4])
