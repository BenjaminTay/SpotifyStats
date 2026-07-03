from __future__ import annotations

import pytest

from backend.domains.ai_reports.editorial_critic import critique_yearly_article

pytestmark = pytest.mark.unit


def test_critic_rejects_data_listing_report():
    report = """
## 2026 年中音乐报告（截至 2026-06-23）
Taylor Swift 以 1115 次播放排在艺人榜首。Olivia Rodrigo 以 769 次播放位列第二。
单曲榜首是 Opalite（123 次）。专辑榜首是 The Life of a Showgirl（445 次）。
Opalite 位列单曲年榜第 1，在榜 19 周。The Life of a Showgirl 位列年度专辑第 1，在榜 24 周。
人格维度前三是 能量引擎 71.6 分、专一者 70.9 分、环球旅人 68.3 分。
"""

    critique = critique_yearly_article(
        report,
        {
            "is_partial_year": True,
            "min_length": 1400,
            "requires_billboard": True,
            "requires_playback_billboard_connection": True,
        },
    )

    codes = {issue.code for issue in critique.issues}
    assert critique.ok is False
    assert "too_short_for_longform" in codes
    assert "data_listing_too_heavy" in codes
    assert "billboard_underused" in codes
    assert "playback_billboard_not_connected" in codes
    assert "partial_year_annual_label" in codes


def test_critic_accepts_interpretive_longform_report():
    paragraph = (
        "Taylor Swift 的领先不是单点爆发，而是横跨艺人、专辑、单曲和个人 Billboard 的稳定中心。"
        "播放记录显示其艺人播放居首，个人 Billboard 又通过在榜周数和榜首周数说明这种中心并非短期波动。"
        "这种播放与个人 Billboard 的互相印证，意味着你的 2026 上半年仍有明确坐标，"
        "但 Zhang Zhen Yue 的进入改变了另一条线索，让核心稳定和版图外扩同时成立。"
    )
    report = "## Taylor Swift 仍是中心，但你的音乐版图正在外扩\n\n" + paragraph * 18

    critique = critique_yearly_article(
        report,
        {
            "is_partial_year": True,
            "min_length": 1400,
            "requires_billboard": True,
            "requires_playback_billboard_connection": True,
        },
    )

    assert critique.ok is True
    assert critique.issues == ()
