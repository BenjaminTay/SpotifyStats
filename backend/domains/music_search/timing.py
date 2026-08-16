"""Small request-scoped timing collector for music-search diagnostics."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from time import perf_counter


@dataclass
class MusicSearchTiming:
    """Collect named durations without retaining the raw search query."""

    clock: Callable[[], float] = perf_counter
    durations_ms: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def measure(self, name: str) -> Iterator[None]:
        started_at = self.clock()
        try:
            yield
        finally:
            elapsed_ms = max((self.clock() - started_at) * 1000.0, 0.0)
            self.durations_ms[name] = self.durations_ms.get(name, 0.0) + elapsed_ms

    def as_dict(self) -> dict[str, float]:
        return {name: round(duration_ms, 3) for name, duration_ms in self.durations_ms.items()}

    def server_timing_header(self) -> str:
        return ", ".join(
            f"{name};dur={duration_ms:.3f}" for name, duration_ms in self.durations_ms.items()
        )


@contextmanager
def measure_search_phase(
    timing: MusicSearchTiming | None,
    name: str,
) -> Iterator[None]:
    if timing is None:
        yield
        return
    with timing.measure(name):
        yield
