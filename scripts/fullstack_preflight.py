#!/usr/bin/env python3
"""Run cheap, read-only checks before the expensive full-stack stages."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", ".venv", "node_modules", "dist", ".pytest_cache"}


def _paths(pattern: str, roots: tuple[str, ...]) -> list[Path]:
    result: list[Path] = []
    for root_name in roots:
        root = ROOT / root_name
        if not root.exists():
            continue
        result.extend(
            path
            for path in root.rglob(pattern)
            if not any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts)
        )
    return sorted(result)


def check_migration_registry() -> None:
    sys.path.insert(0, str(ROOT))
    from backend.core.migrations import LATEST_SCHEMA_VERSION, MIGRATIONS

    versions = [version for version, _name, _migration in MIGRATIONS]
    expected = list(range(1, LATEST_SCHEMA_VERSION + 1))
    if versions != expected:
        raise RuntimeError(
            "migration registry must contain each version from 1 through "
            f"LATEST_SCHEMA_VERSION={LATEST_SCHEMA_VERSION}; got {versions}"
        )


def check_python_syntax() -> None:
    for path in _paths("*.py", ("scripts",)):
        compile(path.read_bytes(), str(path.relative_to(ROOT)), "exec")


def _run_syntax_check(command: list[str], paths: list[Path]) -> None:
    for path in paths:
        subprocess.run(
            [*command, str(path)],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )


def check_shell_syntax() -> None:
    for path in _paths("*.sh", ("scripts", "deploy")):
        first_line = path.read_text(encoding="utf-8").splitlines()[0]
        interpreter = "bash" if "bash" in first_line else "sh"
        _run_syntax_check([interpreter, "-n"], [path])


def run_preflight() -> None:
    check_migration_registry()
    check_python_syntax()
    check_shell_syntax()
    _run_syntax_check(["node", "--check"], _paths("*.mjs", ("scripts",)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate migration registration and script syntax without running services."
    )
    parser.parse_args()
    run_preflight()
    print("Full-stack static preflight passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
