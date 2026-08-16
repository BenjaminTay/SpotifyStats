#!/usr/bin/env python3
"""Fail a container build when application payload contains SQLite files."""

from __future__ import annotations

import sys
from pathlib import Path

SQLITE_MAGIC = b"SQLite format 3\x00"
SQLITE_SUFFIXES = (
    ".db",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".sqlite",
    ".sqlite-journal",
    ".sqlite-shm",
    ".sqlite-wal",
    ".sqlite3",
    ".sqlite3-journal",
    ".sqlite3-shm",
    ".sqlite3-wal",
)


def sqlite_payloads(root: Path) -> list[Path]:
    matches: set[Path] = set()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if name.endswith(SQLITE_SUFFIXES) or any(
            marker in name for marker in (".db.pre-", ".sqlite.pre-", ".sqlite3.pre-")
        ):
            matches.add(path)
            continue
        try:
            with path.open("rb") as handle:
                if handle.read(len(SQLITE_MAGIC)) == SQLITE_MAGIC:
                    matches.add(path)
        except OSError:
            continue
    return sorted(matches)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} ROOT", file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"container payload root is not a directory: {root}", file=sys.stderr)
        return 2
    matches = sqlite_payloads(root)
    if matches:
        print("container payload contains forbidden SQLite files:", file=sys.stderr)
        for path in matches:
            print(path.relative_to(root), file=sys.stderr)
        return 1
    print(f"container SQLite payload check passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
