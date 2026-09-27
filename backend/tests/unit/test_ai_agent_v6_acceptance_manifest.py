from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ai_agent_v6_freeform_questions.json"


def test_v6_freeform_manifest_is_frozen_and_balanced() -> None:
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert len(cases) == 24
    assert len({case["id"] for case in cases}) == 24
    categories = {case["category"] for case in cases}
    assert categories == {
        "natural_rewrite",
        "reference",
        "multiturn",
        "ambiguity",
        "combined_dimensions",
        "steering",
    }
    assert all(sum(case["category"] == category for case in cases) == 4 for category in categories)
    assert all(case["question"].strip() and case["assertions"] for case in cases)
