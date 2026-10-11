from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pandas as pd
import pytest

from backend.core.frame_cache import FrameCacheBudget, retained_frame_bytes
from backend.domains.playback.logical_timeline import attach_listening_duration_frame

pytestmark = pytest.mark.unit


def test_frame_budget_counts_linked_intervals_and_evicts_across_loaders():
    frame = pd.DataFrame({"track_id": [1], "_listening_intervals_ns": [((1, 2),)]})
    attached = pd.DataFrame({"track_id": [2], "name": ["x" * 200]})
    attach_listening_duration_frame(frame, attached)
    weight = retained_frame_bytes(frame)
    assert weight > int(frame.memory_usage(deep=True).sum()) + int(
        attached.memory_usage(deep=True).sum()
    )
    budget = FrameCacheBudget(weight + 1)
    first = budget.cached()(lambda key: frame.copy())
    second = budget.cached()(lambda key: frame.copy())
    first(1)
    assert first(1) is first(1)
    second(1)
    assert first.cache_info().currsize == 0
    assert second.cache_info().currsize == 1
    assert budget.bytes <= budget.max_bytes
    second.cache_clear()
    assert budget.bytes == 0


def test_oversized_frame_is_correct_without_becoming_resident():
    budget = FrameCacheBudget(1)
    calls = []

    @budget.cached()
    def load(key):
        calls.append(key)
        return pd.DataFrame({"value": [key]})

    assert load(7).equals(load(7))
    assert calls == [7, 7]
    assert load.cache_info().currsize == 0


def test_invalidation_during_build_does_not_retain_old_generation():
    budget = FrameCacheBudget(1024)
    entered, release = Event(), Event()

    @budget.cached()
    def load():
        entered.set()
        assert release.wait(3)
        return pd.DataFrame({"value": [1]})

    with ThreadPoolExecutor(1) as pool:
        result = pool.submit(load)
        assert entered.wait(3)
        load.cache_clear()
        release.set()
        assert result.result(timeout=3)["value"].tolist() == [1]
    assert load.cache_info().currsize == budget.bytes == 0
