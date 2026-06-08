"""Phase 5 architecture guardrails."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit


ROOT = Path(__file__).resolve().parents[3]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "path",
    [
        "backend/services/wikipedia_service.py",
        "backend/services/release_cycle_service.py",
    ],
)
def test_business_services_do_not_create_urllib_requests(path):
    source = _read(path)

    assert "urllib.request.Request" not in source
    assert "urllib.request.urlopen" not in source
    assert "urlopen(" not in source


@pytest.mark.parametrize(
    "path",
    [
        "backend/core/spotify_utils.py",
        "backend/core/version_merge.py",
    ],
)
def test_core_spotify_paths_do_not_create_urllib_requests(path):
    source = _read(path)

    assert "urllib.request.Request" not in source
    assert "urllib.request.urlopen" not in source
    assert "urlopen(" not in source
