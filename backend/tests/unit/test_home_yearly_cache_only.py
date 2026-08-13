from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.services import yearly_review_service

pytestmark = pytest.mark.unit


def test_home_preview_cache_helper_never_calls_builder(monkeypatch):
    prepared = SimpleNamespace(cache_key="exact-key")
    artifact = {"report": {"year": 2026}, "record_catalog": []}
    monkeypatch.setattr(yearly_review_service, "_prepare_artifact", lambda *_args: prepared)
    monkeypatch.setattr(
        yearly_review_service,
        "load_persisted_artifact",
        lambda key: artifact if key == "exact-key" else None,
    )
    monkeypatch.setattr(yearly_review_service, "has_persisted_artifact", lambda _key: True)
    monkeypatch.setattr(
        yearly_review_service,
        "_build_prepared_artifact",
        lambda *_args: pytest.fail("cache-only preview must not build"),
    )

    assert (
        yearly_review_service.get_cached_yearly_review_artifact(2026, SimpleNamespace()) == artifact
    )


def test_home_preview_cache_miss_is_none(monkeypatch):
    monkeypatch.setattr(
        yearly_review_service,
        "_prepare_artifact",
        lambda *_args: SimpleNamespace(cache_key="missing"),
    )
    monkeypatch.setattr(yearly_review_service, "load_persisted_artifact", lambda _key: None)
    monkeypatch.setattr(yearly_review_service, "has_persisted_artifact", lambda _key: False)

    assert yearly_review_service.get_cached_yearly_review_artifact(2026, SimpleNamespace()) is None
