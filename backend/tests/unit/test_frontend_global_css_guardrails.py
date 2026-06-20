from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.unit


def test_global_css_reserves_stable_scrollbar_gutter() -> None:
    css = (ROOT / "frontend" / "src" / "index.css").read_text(encoding="utf-8")

    assert "scrollbar-gutter: stable" in css
