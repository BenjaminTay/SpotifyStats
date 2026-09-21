from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.core import db as db_module
from backend.domains.imports.write_coordinator import exclusive_publication
from scripts import (
    approve_artist_language_long_tail_batch,
    approve_artist_language_second_pass,
    review_high_impact_metadata_batch,
)

pytestmark = pytest.mark.unit

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATHS = (
    "scripts/cleanup_historical_fk_debt.py",
    "scripts/fetch_track_durations.py",
    "scripts/fetch_covers.py",
    "scripts/approve_artist_language_second_pass.py",
    "scripts/approve_artist_language_long_tail_batch.py",
    "scripts/review_high_impact_metadata_batch.py",
    "scripts/apply_l2_governance.py",
)
BACKUP_MODULES = (
    approve_artist_language_second_pass,
    approve_artist_language_long_tail_batch,
    review_high_impact_metadata_batch,
)


def _direct_sqlite_connects(tree: ast.AST) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "sqlite3"
        and node.func.attr == "connect"
    ]


def _is_readonly_uri(call: ast.Call) -> bool:
    return any(
        keyword.arg == "uri"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is True
        for keyword in call.keywords
    )


def _is_memory_database(call: ast.Call) -> bool:
    return bool(
        call.args and isinstance(call.args[0], ast.Constant) and call.args[0].value == ":memory:"
    )


def test_maintenance_script_writers_use_the_shared_publication_lease() -> None:
    for relative_path in SCRIPT_PATHS:
        path = PROJECT_ROOT / relative_path
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        coordinated_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "coordinated_sqlite_connect"
        ]
        assert coordinated_calls, f"{relative_path} has no coordinated writer connection"

        unexpected = []
        for call in _direct_sqlite_connects(tree):
            if _is_readonly_uri(call) or _is_memory_database(call):
                continue
            unexpected.append(call.lineno)
        assert not unexpected, (
            f"{relative_path} bypasses coordinated_sqlite_connect at lines {unexpected}"
        )


@pytest.mark.parametrize("module", BACKUP_MODULES)
def test_metadata_backup_releases_the_active_database_lease(
    module, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "active.db"
    target = tmp_path / "backup.db"
    source.touch()
    monkeypatch.setattr(db_module, "DB_PATH", str(source))

    module._backup_database(source, target)

    with exclusive_publication(db_path=str(source), blocking=False):
        pass
