from __future__ import annotations

from pathlib import Path

import pytest

from scripts import phase_e_real_db_acceptance as acceptance

pytestmark = pytest.mark.unit


def test_validate_workdir_rejects_source_and_repository_trees(tmp_path: Path) -> None:
    project = tmp_path / "project"
    source_dir = project / "data"
    source_dir.mkdir(parents=True)
    source = source_dir / "live.db"
    source.touch()
    original_root = acceptance.PROJECT_ROOT
    acceptance.PROJECT_ROOT = project.resolve()
    try:
        with pytest.raises(acceptance.AcceptanceError):
            acceptance.validate_workdir(source, source_dir / "work")
        with pytest.raises(acceptance.AcceptanceError):
            acceptance.validate_workdir(source, project / "work")
        resolved_source, resolved_target = acceptance.validate_workdir(
            source,
            tmp_path / "safe-work",
        )
    finally:
        acceptance.PROJECT_ROOT = original_root
    assert resolved_source == source.resolve()
    assert resolved_target == (tmp_path / "safe-work").resolve()


def test_managed_workdir_cleans_private_copies_by_default(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "live.db"
    source.touch()
    target = tmp_path / "work"
    with acceptance.managed_workdir(source, target, keep=False) as workdir:
        (workdir / "copy.db").touch()
    assert not target.exists()
