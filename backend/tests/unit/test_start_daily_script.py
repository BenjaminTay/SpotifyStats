from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from scripts import start_daily

pytestmark = pytest.mark.unit


def test_build_freshness_tracks_frontend_sources(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "dist").mkdir()
    source = frontend / "src" / "main.tsx"
    output = frontend / "dist" / "index.html"
    source.write_text("source")
    output.write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)

    os.utime(output, ns=(source.stat().st_mtime_ns + 1, source.stat().st_mtime_ns + 1))
    start_daily.write_build_manifest()
    assert start_daily.build_is_stale() is False

    os.utime(source, ns=(output.stat().st_mtime_ns + 1, output.stat().st_mtime_ns + 1))
    assert start_daily.build_is_stale() is True


@pytest.mark.parametrize(
    "relative_path",
    [
        "index.html",
        "public/icon.svg",
        "tsconfig.app.json",
        "tsconfig.node.json",
    ],
)
def test_build_freshness_tracks_all_vite_inputs(tmp_path, monkeypatch, relative_path):
    frontend = tmp_path / "frontend"
    output = frontend / "dist" / "index.html"
    output.parent.mkdir(parents=True)
    output.write_text("built")
    changed = frontend / relative_path
    changed.parent.mkdir(parents=True, exist_ok=True)
    changed.write_text("input")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)

    os.utime(output, ns=(changed.stat().st_mtime_ns + 1, changed.stat().st_mtime_ns + 1))
    start_daily.write_build_manifest()
    assert start_daily.build_is_stale() is False
    os.utime(changed, ns=(output.stat().st_mtime_ns + 1, output.stat().st_mtime_ns + 1))
    assert start_daily.build_is_stale() is True


def test_build_freshness_detects_deleted_tracked_input(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "dist").mkdir()
    source = frontend / "src" / "main.tsx"
    output = frontend / "dist" / "index.html"
    source.write_text("source")
    output.write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)

    start_daily.write_build_manifest()
    assert start_daily.build_is_stale() is False
    source.unlink()

    assert start_daily.build_is_stale() is True


def test_build_freshness_requires_manifest_for_existing_old_build(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    source = frontend / "src" / "main.tsx"
    output = frontend / "dist" / "index.html"
    source.parent.mkdir(parents=True)
    output.parent.mkdir(parents=True)
    source.write_text("source")
    output.write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)

    os.utime(output, ns=(source.stat().st_mtime_ns + 1, source.stat().st_mtime_ns + 1))

    assert start_daily.build_is_stale() is True


def test_build_freshness_detects_added_input(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    source = frontend / "src" / "main.tsx"
    output = frontend / "dist" / "index.html"
    source.parent.mkdir(parents=True)
    output.parent.mkdir(parents=True)
    source.write_text("source")
    output.write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)

    start_daily.write_build_manifest()
    assert start_daily.build_is_stale() is False
    (frontend / "src" / "added.ts").write_text("added")

    assert start_daily.build_is_stale() is True


def test_second_spawn_failure_cleans_up_first_owned_process(monkeypatch):
    first = SimpleNamespace(pid=101, returncode=None, poll=lambda: None)
    cleanup: list[list[object]] = []
    monkeypatch.setattr(start_daily, "build_is_stale", lambda: False)
    monkeypatch.setattr(start_daily, "_require_free_port", lambda _port: None)
    calls = iter([first, FileNotFoundError("npm unavailable")])

    def popen(*_args, **_kwargs):
        result = next(calls)
        if isinstance(result, BaseException):
            raise result
        return result

    monkeypatch.setattr(start_daily.subprocess, "Popen", popen)
    monkeypatch.setattr(
        start_daily, "_terminate_owned", lambda processes: cleanup.append(list(processes))
    )

    with pytest.raises(FileNotFoundError, match="npm unavailable"):
        start_daily.main([])

    assert cleanup == [[first]]


def test_child_early_exit_cleans_up_both_owned_processes(monkeypatch):
    backend = SimpleNamespace(pid=101, returncode=7, poll=lambda: 7)
    frontend = SimpleNamespace(pid=102, returncode=None, poll=lambda: None)
    children = iter([backend, frontend])
    cleanup: list[list[object]] = []
    monkeypatch.setattr(start_daily, "build_is_stale", lambda: False)
    monkeypatch.setattr(start_daily, "_require_free_port", lambda _port: None)
    monkeypatch.setattr(start_daily.subprocess, "Popen", lambda *_args, **_kwargs: next(children))
    monkeypatch.setattr(start_daily, "_terminate_owned", lambda items: cleanup.append(list(items)))

    assert start_daily.main([]) == 7
    assert cleanup == [[backend, frontend]]


def test_build_option_writes_manifest_and_becomes_fresh(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "src" / "main.tsx").write_text("source")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)
    monkeypatch.setattr(start_daily, "_require_free_port", lambda _port: None)

    def build(*_args, **_kwargs):
        (frontend / "dist").mkdir()
        (frontend / "dist" / "index.html").write_text("built")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(start_daily.subprocess, "run", build)

    assert start_daily.main(["--build", "--check"]) == 0
    assert start_daily.build_is_stale() is False
    assert (frontend / "dist" / start_daily.BUILD_MANIFEST_NAME).is_file()


def test_build_option_does_not_rebuild_unchanged_inputs(tmp_path, monkeypatch):
    frontend = tmp_path / "frontend"
    source = frontend / "src" / "main.tsx"
    output = frontend / "dist" / "index.html"
    source.parent.mkdir(parents=True)
    output.parent.mkdir(parents=True)
    source.write_text("source")
    output.write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)
    monkeypatch.setattr(start_daily, "_require_free_port", lambda _port: None)
    start_daily.write_build_manifest()
    monkeypatch.setattr(
        start_daily.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("unchanged inputs must not rebuild"),
    )

    assert start_daily.main(["--build", "--check"]) == 0


def test_daily_preflight_does_not_start_processes(tmp_path, monkeypatch, capsys):
    frontend = tmp_path / "frontend"
    (frontend / "dist").mkdir(parents=True)
    (frontend / "dist" / "index.html").write_text("built")
    monkeypatch.setattr(start_daily, "FRONTEND", frontend)
    monkeypatch.setattr(start_daily, "build_is_stale", lambda: False)
    monkeypatch.setattr(
        start_daily.subprocess,
        "Popen",
        lambda *_args, **_kwargs: pytest.fail("--check must not start child processes"),
    )

    assert start_daily.main(["--check", "--backend-port", "0", "--frontend-port", "0"]) == 0
    assert "ready" in capsys.readouterr().out
