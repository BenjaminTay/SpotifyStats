"""One conservative byte budget for playback and weighted DataFrame caches."""

from __future__ import annotations

from collections import OrderedDict, namedtuple
from functools import wraps
from threading import RLock

import pandas as pd

CacheInfo = namedtuple("CacheInfo", "hits misses maxsize currsize")


def retained_frame_bytes(frame: pd.DataFrame, seen=None) -> int:
    """Count columns plus attached frames, including nested interval tuples.

    Strings shared between frames may be counted twice. This is deliberately
    a conservative retention estimate, not a measurement of process RSS.
    """
    import sys

    seen = set() if seen is None else seen
    if id(frame) in seen:
        return 0
    seen.add(id(frame))
    size = int(frame.memory_usage(index=True, deep=True).sum())
    if "_listening_intervals_ns" in frame:
        for intervals in frame["_listening_intervals_ns"]:
            if isinstance(intervals, (tuple, list)):
                size += sum(
                    sys.getsizeof(interval) + sum(sys.getsizeof(v) for v in interval)
                    for interval in intervals
                )
    for value in frame.attrs.values():
        linked = value if isinstance(value, pd.DataFrame) else getattr(value, "frame", None)
        if isinstance(linked, pd.DataFrame):
            size += retained_frame_bytes(linked, seen)
    return size


class FrameCacheBudget:
    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self.bytes = 0
        self.entries: OrderedDict[tuple, tuple[pd.DataFrame, int]] = OrderedDict()
        self.lock = RLock()

    def cached(self, maxsize=16):
        def decorate(fn):
            token = object()
            hits = misses = generation = 0

            @wraps(fn)
            def wrapper(*args, **kwargs):
                nonlocal hits, misses
                key = (token, args, tuple(sorted(kwargs.items())))
                with self.lock:
                    if key in self.entries:
                        hits += 1
                        result, weight = self.entries.pop(key)
                        self.entries[key] = (result, weight)
                        return result
                    misses += 1
                    started_generation = generation
                result = fn(*args, **kwargs)
                weight = retained_frame_bytes(result)
                with self.lock:
                    if generation != started_generation:
                        return result
                    # Oversized values remain correct, invocation-local inputs.
                    if weight > self.max_bytes:
                        return result
                    old = self.entries.pop(key, None)
                    if old is not None:
                        self.bytes -= old[1]
                    owned = [k for k in self.entries if k[0] is token]
                    if len(owned) >= maxsize:
                        self.bytes -= self.entries.pop(owned[0])[1]
                    while self.entries and self.bytes + weight > self.max_bytes:
                        _, (_, removed) = self.entries.popitem(last=False)
                        self.bytes -= removed
                    self.entries[key] = (result, weight)
                    self.bytes += weight
                return result

            def cache_clear():
                nonlocal hits, misses, generation
                with self.lock:
                    generation += 1
                    for key in list(self.entries):
                        if key[0] is token:
                            self.bytes -= self.entries.pop(key)[1]
                    hits = misses = 0

            def cache_info():
                with self.lock:
                    return CacheInfo(
                        hits, misses, maxsize, sum(k[0] is token for k in self.entries)
                    )

            def cache_budget_info():
                with self.lock:
                    return {
                        "shared_bytes": self.bytes,
                        "max_bytes": self.max_bytes,
                        "owned_bytes": sum(v[1] for k, v in self.entries.items() if k[0] is token),
                    }

            wrapper.cache_clear = cache_clear
            wrapper.cache_info = cache_info
            wrapper.cache_budget_info = cache_budget_info
            return wrapper

        return decorate


playback_frame_budget = FrameCacheBudget(384 * 1024 * 1024)
