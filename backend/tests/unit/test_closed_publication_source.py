"""Actual SQLite files exercise the offline read boundary, not a mocked opener."""

import hashlib
import sqlite3
from pathlib import Path

import pytest

from backend.core import db
from scripts.closed_publication_source import publication_reads

pytestmark = pytest.mark.unit


def wal_file(path, *, closed=False):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL").close()
    conn.execute("CREATE TABLE facts(value INTEGER)").close()
    conn.execute("INSERT INTO facts VALUES (7)").close()
    conn.commit()
    if closed:
        cursor = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        assert cursor.fetchone() == (0, 0, 0)
        cursor.close()
        conn.close()
        wal = Path(str(path) + "-wal")
        if wal.exists():
            assert wal.stat().st_size == 0
            wal.unlink()
        Path(str(path) + "-shm").unlink(missing_ok=True)
        return None
    return conn


def test_closed_wal_header_reads_without_sidefiles_or_byte_changes(tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    wal_file(path, closed=True)
    assert path.read_bytes()[18:20] == b"\x02\x02"
    assert not Path(str(path) + "-wal").exists()
    original = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(db, "DB_PATH", str(path))
    tmp_path.chmod(0o500)
    try:
        with publication_reads(path, closed=True):
            conn = db.get_db(readonly=True)
            assert conn.execute("SELECT value FROM facts").fetchone()[0] == 7
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                conn.execute("UPDATE facts SET value=8")
            conn.close()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == original
        assert set(tmp_path.iterdir()) == {path}
    finally:
        tmp_path.chmod(0o700)


@pytest.mark.parametrize("nonempty", [False, True])
def test_closed_source_rejects_even_empty_wal(tmp_path, nonempty):
    path = tmp_path / "source.db"
    wal_file(path, closed=True)
    Path(str(path) + "-wal").write_bytes(b"unfinished" if nonempty else b"")
    with pytest.raises(RuntimeError, match="no WAL"):
        with publication_reads(path, closed=True):
            pytest.fail("must reject before opening")


def test_live_reader_observes_committed_wal_and_never_uses_immutable(tmp_path, monkeypatch):
    path = tmp_path / "source.db"
    writer = wal_file(path)
    monkeypatch.setattr(db, "DB_PATH", str(path))
    try:
        with publication_reads(path):
            conn = db.get_db(readonly=True)
            assert conn.execute("SELECT value FROM facts").fetchone()[0] == 7
            with pytest.raises(sqlite3.OperationalError, match="readonly"):
                conn.execute("UPDATE facts SET value=8")
            conn.close()
    finally:
        writer.close()


def test_closed_source_rejects_replacement_and_restores_connection_factory(tmp_path):
    path = tmp_path / "source.db"
    wal_file(path, closed=True)
    original = sqlite3.connect
    replacement = tmp_path / "replacement.db"
    wal_file(replacement, closed=True)
    with pytest.raises(RuntimeError, match="changed"):
        with publication_reads(path, closed=True):
            replacement.replace(path)
    assert sqlite3.connect is original


def test_sidecar_import_keeps_writer_then_seals_exact_read(tmp_path):
    source = tmp_path / "source.db"
    wal_file(source, closed=True)
    sidecar = tmp_path / "cache.db"
    with publication_reads(source, closed=True, sidecars=(sidecar,)):
        wal_file(sidecar, closed=True)
        reader = sqlite3.connect(sidecar.as_uri() + "?mode=ro", uri=True)
        assert reader.execute("SELECT value FROM facts").fetchone()[0] == 7
        reader.close()
    assert not Path(str(sidecar) + "-wal").exists()


def test_readonly_sidecar_rejects_active_wal(tmp_path):
    source = tmp_path / "source.db"
    wal_file(source, closed=True)
    sidecar = tmp_path / "cache.db"
    writer = wal_file(sidecar)
    try:
        with publication_reads(source, closed=True, sidecars=(sidecar,)):
            with pytest.raises(RuntimeError, match="no WAL"):
                sqlite3.connect(sidecar.as_uri() + "?mode=ro", uri=True)
    finally:
        writer.close()


@pytest.mark.parametrize("operation", ["--build-on-copy", "--import-manifest"])
def test_detail_closed_mode_cannot_enter_writing_operations(tmp_path, monkeypatch, operation):
    import sys

    from scripts import prepare_music_detail_projection as maintenance

    args = ["prepare", "--db-path", str(tmp_path / "absent.db"), "--closed-source", operation]
    if operation == "--import-manifest":
        args.append(str(tmp_path / "absent.json"))
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as error:
        maintenance.main()
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())


def test_billboard_closed_mode_cannot_build(tmp_path, monkeypatch):
    import sys

    from scripts import prepare_billboard_publications as maintenance

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare",
            "--db-path",
            str(tmp_path / "absent.db"),
            "--cache-path",
            str(tmp_path / "cache.db"),
            "--closed-source",
            "--build-on-copy",
        ],
    )
    with pytest.raises(SystemExit) as error:
        maintenance.main()
    assert error.value.code == 2
    assert not list(tmp_path.iterdir())
