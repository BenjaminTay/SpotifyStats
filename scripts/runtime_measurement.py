#!/usr/bin/env python3
"""Prepare and serve fully isolated normal-lifespan runtime measurements.

The legacy ``performance_server.py`` remains a lifespan-off read probe. This
entry point is deliberately stricter: it creates SQLite Online Backups, binds
every derived publication to the experiment root, blocks non-loopback network
access, and then runs the real application lifespan.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import socket
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from ipaddress import ip_address
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DEFAULT_LOCK = Path(tempfile.gettempdir()) / "spotify-fullstack-verification.lock"
SQLITE_ARTIFACTS = (
    "spotify_stats.db",
    "billboard_cache.db",
    "analysis_cache.db",
    "yearly_review_cache.db",
    "community_cache.db",
    "account_archive_cache.db",
    "governance_cache.db",
)
PROXY_ENVIRONMENT_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
_NETWORK_GUARD_INSTALLED = False


def _temporary_root(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    roots = {Path(tempfile.gettempdir()).resolve(), Path("/tmp").resolve()}
    if not any(path != root and root in path.parents for root in roots):
        raise ValueError("runtime measurement output must be inside the system temporary root")
    return path


@contextmanager
def _performance_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip()
            raise RuntimeError(
                f"performance lock is busy: {owner or 'owner metadata unavailable'}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "worktree": str(ROOT),
                    "stage": "runtime-measurement-prepare",
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
                ensure_ascii=False,
            )
        )
        handle.flush()
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _online_backup(source: Path, target: Path) -> dict[str, object]:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"{source.as_uri()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=30) as source_db:
        source_schema_version = int(source_db.execute("PRAGMA schema_version").fetchone()[0])
        with sqlite3.connect(target) as target_db:
            source_db.backup(target_db)
            target_schema_version = int(target_db.execute("PRAGMA schema_version").fetchone()[0])
            revision_schema_rebindings: list[str] = []
            governance_schema = target_db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='governance_revision_schema'"
            ).fetchone()
            if governance_schema and source_schema_version != target_schema_version:
                marker = target_db.execute(
                    "SELECT schema_version FROM governance_revision_schema WHERE singleton=1"
                ).fetchone()
                if marker and int(marker[0]) == source_schema_version:
                    # sqlite3_backup creates an equivalent destination whose
                    # local schema cookie may differ.  Rebind only this guard;
                    # epochs, counters and publication target revisions remain
                    # byte-for-byte the copied lineage.
                    target_db.execute(
                        "UPDATE governance_revision_schema SET schema_version=? WHERE singleton=1",
                        (target_schema_version,),
                    )
                    revision_schema_rebindings.append("governance_revision_schema")
                    target_db.commit()
            integrity = target_db.execute("PRAGMA integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RuntimeError(
                    f"Online Backup integrity check failed for {source.name}: {integrity}"
                )
    return {
        "source": str(source),
        "target": str(target),
        "source_bytes": source.stat().st_size,
        "target_bytes": target.stat().st_size,
        "source_schema_version": source_schema_version,
        "target_schema_version": target_schema_version,
        "revision_schema_rebindings": revision_schema_rebindings,
        "integrity": "ok",
    }


def _copy_tree_if_present(source: Path, target: Path) -> dict[str, object]:
    if not source.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        return {"source": str(source), "target": str(target), "status": "missing"}
    shutil.copytree(source, target, dirs_exist_ok=True)
    return {
        "source": str(source),
        "target": str(target),
        "status": "copied",
        "files": sum(1 for item in target.rglob("*") if item.is_file()),
    }


def prepare(args: argparse.Namespace) -> int:
    source_db = Path(args.source_db).expanduser().resolve()
    if not source_db.is_file():
        raise FileNotFoundError(source_db)
    output = _temporary_root(args.output_root)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"measurement root is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    data = output / "data"
    data.mkdir()
    source_data = source_db.parent
    before = source_db.stat()
    artifacts: list[dict[str, object]] = []
    with _performance_lock(Path(args.lock_file).expanduser().resolve()):
        for name in SQLITE_ARTIFACTS:
            source = source_data / name
            if source.is_file():
                artifacts.append(_online_backup(source, data / name))
        control = source_data / "import_control" / "control.sqlite3"
        if control.is_file():
            artifacts.append(_online_backup(control, data / "import_control" / "control.sqlite3"))
        trees = [
            _copy_tree_if_present(
                source_data / "cache" / "home-overview",
                data / "cache" / "home-overview",
            )
        ]
        # Covers are intentionally not copied: the isolated server may read an
        # empty cover root and any recovery write remains inside the run root.
        (data / "covers").mkdir()
        if args.include_import_sources:
            trees.append(
                _copy_tree_if_present(source_data / "import_sources", data / "import_sources")
            )
    after = source_db.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("source database changed while the measurement set was prepared")

    if args.state == "M":
        for path in (
            data / "analysis_cache.db",
            data / "cache" / "home-overview",
        ):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
    elif args.state == "D":
        database = data / "spotify_stats.db"
        with sqlite3.connect(database) as conn:
            current = conn.execute("SELECT value FROM settings WHERE key='bb_top_n'").fetchone()
            value = int(current[0]) if current else 30
            conn.execute(
                "INSERT OR REPLACE INTO settings(key,value) VALUES('bb_top_n',?)",
                (str(31 if value != 31 else 32),),
            )
            conn.commit()

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": args.state,
        "source_db": str(source_db),
        "source_stat_before": {"bytes": before.st_size, "mtime_ns": before.st_mtime_ns},
        "source_stat_after": {"bytes": after.st_size, "mtime_ns": after.st_mtime_ns},
        "output_root": str(output),
        "artifacts": artifacts,
        "trees": trees,
        "path_contract": isolated_environment(data),
        "exact_ready": "must be established by response revision evidence; never inferred from filenames",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(output)
    return 0


def isolated_environment(data: Path) -> dict[str, str]:
    return {
        "SPOTIFY_STATS_DB_PATH": str(data / "spotify_stats.db"),
        "SPOTIFY_STATS_BILLBOARD_CACHE_PATH": str(data / "billboard_cache.db"),
        "SPOTIFY_STATS_ANALYSIS_CACHE_PATH": str(data / "analysis_cache.db"),
        "SPOTIFY_STATS_YEARLY_CACHE_PATH": str(data / "yearly_review_cache.db"),
        "SPOTIFY_STATS_COMMUNITY_CACHE_PATH": str(data / "community_cache.db"),
        "SPOTIFY_STATS_ARCHIVE_CACHE_PATH": str(data / "account_archive_cache.db"),
        "SPOTIFY_STATS_GOVERNANCE_CACHE_PATH": str(data / "governance_cache.db"),
    }


def _loopback_host(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    value = str(host or "").strip().strip("[]").lower()
    if value == "localhost":
        return True
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return False


def _block_external_network() -> None:
    global _NETWORK_GUARD_INSTALLED
    if _NETWORK_GUARD_INSTALLED:
        return
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def loopback_only(sock: socket.socket, address):
        if isinstance(address, tuple) and not _loopback_host(address[0]):
            raise RuntimeError("external network disabled in runtime measurement")
        return original_connect(sock, address)

    def loopback_dns_only(host, *args, **kwargs):
        if host is not None and not _loopback_host(host):
            raise RuntimeError("external DNS disabled in runtime measurement")
        return original_getaddrinfo(host, *args, **kwargs)

    def loopback_only_ex(sock: socket.socket, address):
        if isinstance(address, tuple) and not _loopback_host(address[0]):
            raise RuntimeError("external network disabled in runtime measurement")
        return original_connect_ex(sock, address)

    socket.socket.connect = loopback_only  # type: ignore[assignment]
    socket.socket.connect_ex = loopback_only_ex  # type: ignore[assignment]
    socket.getaddrinfo = loopback_dns_only  # type: ignore[assignment]
    _NETWORK_GUARD_INSTALLED = True


def _clear_proxy_environment() -> None:
    for key in PROXY_ENVIRONMENT_KEYS:
        os.environ.pop(key, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"


def configure_isolated_runtime_from_environment() -> Path:
    root_value = os.environ.get("SPOTIFY_RUNTIME_MEASUREMENT_ROOT")
    if not root_value:
        raise RuntimeError("SPOTIFY_RUNTIME_MEASUREMENT_ROOT is required")
    root = _temporary_root(root_value)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"prepared manifest is missing: {manifest_path}")
    data = root / "data"
    for key, value in isolated_environment(data).items():
        os.environ[key] = value
    warmup_mode = os.environ.get("SPOTIFY_RUNTIME_WARMUP_MODE", "full")
    os.environ["SPOTIFY_STATS_WARMUP"] = "0" if warmup_mode == "off" else "1"
    os.environ["SPOTIFY_STATS_WARMUP_MODE"] = warmup_mode
    os.environ["SPOTIFY_STATS_EXTERNAL_COVERS"] = "0"
    os.environ["FRONTEND_ORIGIN"] = os.environ.get(
        "SPOTIFY_RUNTIME_FRONTEND_ORIGIN", "http://127.0.0.1:4173"
    )
    os.environ["SPOTIFY_RUNTIME_MEASUREMENT"] = "1"
    _clear_proxy_environment()
    _block_external_network()
    return root


def create_isolated_app():
    """ASGI factory imported by every Uvicorn worker, including reload children."""
    configure_isolated_runtime_from_environment()
    from backend.main import app

    if not any(
        getattr(route, "path", None) == "/api/runtime-measurement/isolation" for route in app.routes
    ):

        @app.get("/api/runtime-measurement/isolation", include_in_schema=False)
        def runtime_measurement_isolation() -> dict[str, object]:
            external_blocked = False
            try:
                socket.getaddrinfo("runtime-measurement.invalid", 443)
            except RuntimeError:
                external_blocked = True
            return {
                "pid": os.getpid(),
                "network_guard": "installed" if _NETWORK_GUARD_INSTALLED else "missing",
                "external_blocked": external_blocked,
                "proxy_environment_clear": not any(
                    os.environ.get(key) for key in PROXY_ENVIRONMENT_KEYS
                ),
            }

    return app


def current_publication_readiness() -> dict[str, object]:
    """Inspect startup publication targets without building or enqueueing work."""
    from backend.core.db import get_db
    from backend.domains.account_archive.context import resolve_archive_filters
    from backend.domains.account_archive.snapshot_revision import FAMILIES as ARCHIVE_FAMILIES
    from backend.domains.metadata.artist_identity import get_identity_state
    from backend.domains.metadata.track_credits import get_track_credit_state
    from backend.domains.music_search.index import (
        expected_candidate_index_version,
        get_music_search_index_state,
        music_search_candidate_index_is_current,
    )
    from backend.domains.music_search.variants import build_music_search_variant_contexts
    from backend.domains.music_search.year_end_projection import year_end_projection_set_status
    from backend.domains.playback.l3_album_attribution import (
        l3_album_attribution_dependencies_ready,
    )
    from backend.services import analysis_snapshot_store
    from backend.services.account_archive_snapshot_service import (
        _pending as archive_pending,
    )
    from backend.services.account_archive_snapshot_service import _targets as archive_targets
    from backend.services.analysis_snapshot_service import (
        AUTOMATIC_PERIODS,
        VERSIONS,
        request_context,
    )
    from backend.services.billboard_snapshot_service import billboard_default_snapshots_ready
    from backend.services.community_snapshot_service import context as community_context
    from backend.services.community_snapshot_service import store as community_store
    from backend.services.entity_rank_context_service import FAMILY as RANK_FAMILY
    from backend.services.entity_rank_context_service import VERSION as RANK_VERSION
    from backend.services.entity_rank_context_service import context as rank_context
    from backend.services.governance_snapshot_service import RESULT_FAMILIES
    from backend.services.governance_snapshot_service import _pending as governance_pending
    from backend.services.governance_snapshot_service import parameters as governance_parameters
    from backend.services.music_search_maintenance_service import (
        _current_filter_values,
        _revalidated_snapshot_set_report,
        _search_metadata_dependencies_ready,
    )

    checks: dict[str, dict[str, object]] = {}
    conn = get_db(readonly=True)
    try:
        identity = get_identity_state(conn)
        credits = get_track_credit_state(conn)
        checks["artist_identity"] = {
            "ready": identity.get("rebuild_status") == "ready"
            and int(identity.get("current_revision") or 0)
            == int(identity.get("active_aggregate_revision") or 0),
            "current_revision": identity.get("current_revision"),
            "active_revision": identity.get("active_aggregate_revision"),
        }
        checks["track_credits"] = {
            "ready": credits.get("rebuild_status") == "ready"
            and int(credits.get("current_revision") or 0)
            == int(credits.get("active_aggregate_revision") or 0),
            "current_revision": credits.get("current_revision"),
            "active_revision": credits.get("active_aggregate_revision"),
        }
        checks["l3_album_attribution"] = {"ready": l3_album_attribution_dependencies_ready(conn)}

        analysis_targets = []
        for family in VERSIONS:
            for period in AUTOMATIC_PERIODS:
                _, key, revision, version = request_context(conn, family, {"period": period})
                found = analysis_snapshot_store.read(family, key, revision, version)
                exact = bool(found and found[1]["source_revision"] == revision)
                analysis_targets.append(
                    {
                        "family": family,
                        "period": period,
                        "request_key": key,
                        "target_revision": revision,
                        "ready": exact,
                    }
                )
        checks["analysis"] = {
            "ready": all(item["ready"] for item in analysis_targets),
            "targets": analysis_targets,
        }

        _, community_key, community_revision = community_context(conn, {})
        community_ready = False
        try:
            with community_store.reader(community_key) as (_, row):
                community_ready = bool(row and row["revision"] == community_revision)
        except (FileNotFoundError, sqlite3.Error):
            pass
        checks["community"] = {
            "ready": community_ready,
            "request_key": community_key,
            "target_revision": community_revision,
        }

        archive_params = resolve_archive_filters(conn, {})
        archive_targets_current = archive_targets(conn, archive_params, ARCHIVE_FAMILIES)
        archive_missing = archive_pending(archive_targets_current)
        checks["account_archive"] = {
            "ready": not archive_missing,
            "targets": [
                {"family": family, "request_key": key, "target_revision": revision}
                for family, key, revision in archive_targets_current
            ],
            "missing": [family for family, _, _ in archive_missing],
        }

        governance_params = governance_parameters(conn)
        governance_missing = governance_pending(conn, governance_params, RESULT_FAMILIES)
        checks["governance"] = {
            "ready": not governance_missing,
            "missing": [target[0][0] for target in governance_missing],
        }

        _, rank_key, rank_revision = rank_context(conn)
        rank_found = analysis_snapshot_store.read(
            RANK_FAMILY, rank_key, rank_revision, RANK_VERSION
        )
        checks["artist_rank_context"] = {
            "ready": bool(rank_found and rank_found[1]["source_revision"] == rank_revision),
            "request_key": rank_key,
            "target_revision": rank_revision,
        }

        search_contexts = build_music_search_variant_contexts(conn, _current_filter_values(conn))
        search_report = _revalidated_snapshot_set_report(conn, search_contexts)
        search_state = get_music_search_index_state(conn)
        projection_state = year_end_projection_set_status(conn, search_contexts)
        checks["music_search"] = {
            "ready": bool(
                _search_metadata_dependencies_ready(conn)
                and music_search_candidate_index_is_current(conn)
                and search_state.get("candidate_index_version")
                == expected_candidate_index_version(conn)
                and search_report
                and search_report.get("status") == "ready"
                and projection_state.get("status") == "ready"
            ),
            "source_revision": search_state.get("source_revision"),
            "candidate_index_version": search_state.get("candidate_index_version"),
            "snapshot_status": search_report.get("status") if search_report else "missing",
            "year_end_status": projection_state.get("status"),
        }
    finally:
        conn.close()

    try:
        billboard_ready = billboard_default_snapshots_ready()
    except Exception as exc:
        checks["billboard"] = {"ready": False, "error": f"{type(exc).__name__}: {exc}"}
    else:
        checks["billboard"] = {"ready": billboard_ready}
    return {
        "ready": all(bool(value.get("ready")) for value in checks.values()),
        "checks": checks,
    }


def validate(args: argparse.Namespace) -> int:
    os.environ["SPOTIFY_RUNTIME_MEASUREMENT_ROOT"] = str(_temporary_root(args.root))
    os.environ.setdefault("SPOTIFY_RUNTIME_WARMUP_MODE", "minimal")
    configure_isolated_runtime_from_environment()
    result = current_publication_readiness()
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if result["ready"] else 4


def serve(args: argparse.Namespace) -> int:
    root = _temporary_root(args.root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"prepared manifest is missing: {manifest_path}")
    os.environ["SPOTIFY_RUNTIME_MEASUREMENT_ROOT"] = str(root)
    os.environ["SPOTIFY_RUNTIME_WARMUP_MODE"] = args.warmup_mode
    os.environ["SPOTIFY_RUNTIME_FRONTEND_ORIGIN"] = args.frontend_origin
    _clear_proxy_environment()

    import uvicorn

    uvicorn.run(
        "scripts.runtime_measurement:create_isolated_app",
        factory=True,
        host="127.0.0.1",
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(Path(args.reload_dir).resolve())] if args.reload else None,
        lifespan="on",
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--source-db", required=True)
    prepare_parser.add_argument("--output-root", required=True)
    prepare_parser.add_argument("--state", choices=("E", "M", "D"), default="E")
    prepare_parser.add_argument("--include-import-sources", action="store_true")
    prepare_parser.add_argument("--lock-file", default=str(DEFAULT_LOCK))
    prepare_parser.set_defaults(func=prepare)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--root", required=True)
    serve_parser.add_argument("--port", type=int, required=True)
    serve_parser.add_argument("--warmup-mode", choices=("full", "minimal", "off"), default="full")
    serve_parser.add_argument("--frontend-origin", default="http://127.0.0.1:4173")
    serve_parser.add_argument("--reload", action="store_true")
    serve_parser.add_argument("--reload-dir", default=str(ROOT / "backend"))
    serve_parser.set_defaults(func=serve)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--root", required=True)
    validate_parser.add_argument("--output")
    validate_parser.set_defaults(func=validate)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
