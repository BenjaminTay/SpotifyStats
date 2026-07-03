from __future__ import annotations

import pytest

from backend.domains.ai_reports.dynamic_outline import plan_visual_yearly_outline

pytestmark = pytest.mark.unit


def test_outline_promotes_monthly_turning_point_when_second_artist_overtakes():
    context = {
        "chart_data": {
            "artist_monthly_trend": {
                "observations": [
                    "Olivia Rodrigo 在 2026-06 达到 366 次，超过 Taylor Swift 的 114 次。"
                ]
            },
            "discovery_timeline": {"new_artists": [{"name": "Zhang Zhen Yue", "plays": 574}]},
            "album_duality_compare": {"relation": "aligned"},
        }
    }

    outline = plan_visual_yearly_outline(context)

    roles = [section["role"] for section in outline]
    assert roles[0] == "opening"
    assert "turning_point" in roles
    assert "album_story" in roles
    assert "discovery" in roles


def test_outline_uses_billboard_divergence_when_album_relation_diverges():
    context = {
        "chart_data": {
            "album_duality_compare": {"relation": "divergent"},
            "playback_billboard_matrix": {"observations": ["某首歌播放不最高但长留。"]},
        }
    }

    outline = plan_visual_yearly_outline(context)

    roles = [section["role"] for section in outline]
    assert "billboard_divergence" in roles
    assert roles.index("billboard_divergence") < roles.index("closing")
