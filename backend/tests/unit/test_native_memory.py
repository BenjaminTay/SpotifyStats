"""Native cleanup compatibility and failure boundaries (no actual trim)."""

from functools import lru_cache
from types import SimpleNamespace

import pytest

from backend.core import cache_manager, native_memory

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("platform", ["darwin", "win32"])
def test_unsupported_platform_never_loads_native_allocator(monkeypatch, platform):
    monkeypatch.setattr(native_memory.sys, "platform", platform)
    monkeypatch.setattr(native_memory.ctypes, "CDLL", lambda *a: pytest.fail("native load"))
    assert native_memory.trim_unused_native_memory() is False


@pytest.mark.parametrize("has_glibc,has_trim", [(False, True), (True, False)])
def test_missing_glibc_or_symbol_is_noop(monkeypatch, has_glibc, has_trim):
    monkeypatch.setattr(native_memory.sys, "platform", "linux")
    libc = SimpleNamespace()
    if has_glibc:
        libc.gnu_get_libc_version = object()
    if has_trim:
        libc.malloc_trim = lambda pad: pytest.fail("non-glibc native call")
    monkeypatch.setattr(native_memory.ctypes, "CDLL", lambda name: libc)
    assert native_memory.trim_unused_native_memory() is False


@pytest.mark.parametrize("native_result", [0, 1])
def test_supported_trim_uses_zero_pad_without_invalidating_ready_cache(monkeypatch, native_result):
    monkeypatch.setattr(native_memory.sys, "platform", "linux")
    calls = []

    @lru_cache(maxsize=1)
    def ready_fact():
        return {"year": 2026}

    monkeypatch.setitem(cache_manager._lru_registry["analysis"], "trim_test", ready_fact)
    original = ready_fact()

    def trim(pad):
        calls.append(pad)
        return native_result

    monkeypatch.setattr(
        native_memory.ctypes,
        "CDLL",
        lambda name: SimpleNamespace(gnu_get_libc_version=object(), malloc_trim=trim),
    )
    assert native_memory.trim_unused_native_memory() is (native_result == 1)
    assert calls == [0]
    assert ready_fact.cache_info().currsize == 1
    assert ready_fact() is original


@pytest.mark.parametrize("failure_stage", ["load", "call"])
def test_native_os_failure_does_not_escape(monkeypatch, caplog, failure_stage):
    monkeypatch.setattr(native_memory.sys, "platform", "linux")

    def fail(*args):
        raise OSError("native unavailable")

    libc = SimpleNamespace(gnu_get_libc_version=object(), malloc_trim=fail)
    monkeypatch.setattr(
        native_memory.ctypes, "CDLL", fail if failure_stage == "load" else lambda name: libc
    )
    assert native_memory.trim_unused_native_memory() is False
    assert "Native memory trim unavailable" in caplog.text
