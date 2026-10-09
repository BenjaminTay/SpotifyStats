#!/usr/bin/env python3
"""Explicit copy preparation and source-fenced transfer of Billboard publications."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.core import db  # noqa: E402
from backend.core.access_surface import (  # noqa: E402
    public_readonly_db_guard_active,
    reset_public_readonly_db_guard,
    set_public_readonly_db_guard,
)
from backend.domains.billboard import persistent_cache as cache  # noqa: E402
from backend.domains.music_search.snapshot_lineage import (  # noqa: E402
    active_playback_lineage,
    music_search_snapshot_dependency_digest,
)
from backend.services.billboard_snapshot_service import (  # noqa: E402
    _year_end_snapshot_params,
    configured_billboard_filters,
)

FAMILIES = ("weekly", "all_time", "full_data", "records", "power_scores", "summaries")


def _assert_private():
    if public_readonly_db_guard_active():
        raise RuntimeError("public requests cannot enter Billboard maintenance")


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def _variants(conn):
    default = configured_billboard_filters(conn)
    return [
        {**default, "merge_level": level, "dynamic_threshold": dynamic}
        for level in (2, 3)
        for dynamic in (False, True)
    ]


def source_fence(conn):
    return {
        "playback_lineage": list(active_playback_lineage(conn)),
        "governance_digest": music_search_snapshot_dependency_digest(conn),
        "default_filters": configured_billboard_filters(conn),
    }


def _dependencies(family, params):
    dependencies = cache._dependency_state(family, params)
    # Namespace relocation is allowed; no factual dependency is excluded.
    dependencies.pop("database_path")
    if "billboard_revision_state" in dependencies:
        state = list(dependencies["billboard_revision_state"])
        # The last revision includes file device/inode inside an opaque digest.
        # Preserve its complete factual vector while rebinding only namespace.
        state[-1] = {"analysis_records_dependencies": _analysis_dependencies()}
        dependencies["billboard_revision_state"] = state
    return json.loads(json.dumps(dependencies, sort_keys=True, ensure_ascii=True))


def _analysis_dependencies():
    from backend.domains.metadata.release_dates import RELEASE_DATE_POLICY_VERSION
    from backend.domains.metadata.track_credits import TRACK_CREDIT_POLICY_VERSION
    from backend.services.analysis_snapshot_revision import COMMON, RECORDS, _revision_vector

    conn = db.get_db(readonly=True)
    try:
        dependencies = _revision_vector(conn, COMMON + RECORDS)
        dependencies["track_credit_policy"] = TRACK_CREDIT_POLICY_VERSION
        dependencies["release_date_policy"] = RELEASE_DATE_POLICY_VERSION
        return dependencies
    finally:
        conn.close()


def _years(payload):
    years = payload.get("meta", {}).get("available_years")
    if (
        not isinstance(years, list)
        or any(type(year) is not int or not 1 <= year <= 9999 for year in years)
        or len(set(years)) != len(years)
    ):
        raise RuntimeError("invalid published Billboard year range")
    return years


def _read_exact(family, params):
    token = set_public_readonly_db_guard(True)
    try:
        context = cache.build_cache_context(family, params)
        payload = cache.load_persisted_snapshot(context, allow_lkg=False)
    finally:
        reset_public_readonly_db_guard(token)
    if payload is None:
        raise RuntimeError(f"exact Billboard publication unavailable: {family}")
    return payload


def _targets(conn, latest):
    targets = []
    for filters in _variants(conn):
        targets.extend((family, filters) for family in FAMILIES)
        params = _year_end_snapshot_params(filters, year=None)
        payload = latest(params)
        targets.append(("year_end", params))
        targets.extend(
            ("year_end", _year_end_snapshot_params(filters, year=year)) for year in _years(payload)
        )
    if len(targets) > cache.DEFAULT_MAX_ENTRIES:
        raise RuntimeError("Billboard maintenance target set exceeds sidecar capacity")
    return targets


def prepare_publications(conn):
    """Build four exact variants using existing invocation-local maintenance facts."""
    _assert_private()
    from backend.core.cache_manager import invalidate
    from backend.domains.billboard.build_context import BillboardBuildContext
    from backend.services.billboard_service import (
        compute_all_time_staged,
        compute_billboard_data,
        compute_power_scores_staged,
        compute_records_staged,
        compute_summaries_staged,
        compute_weekly_data,
        compute_year_end_staged,
    )

    captured = source_fence(conn)
    builders = dict(
        zip(
            FAMILIES,
            (
                compute_weekly_data,
                compute_all_time_staged,
                compute_billboard_data,
                compute_records_staged,
                compute_power_scores_staged,
                compute_summaries_staged,
            ),
        )
    )
    prepared = []
    for filters in _variants(conn):
        with BillboardBuildContext(filters) as facts:
            for builder in builders.values():
                builder(**filters, force_rebuild=True, _build_context=facts)
            params = _year_end_snapshot_params(filters, year=None)
            latest = compute_year_end_staged(**params, force_rebuild=True, _build_context=facts)
            years = _years(latest)
            for year in years:
                compute_year_end_staged(
                    **{**params, "year": year}, force_rebuild=True, _build_context=facts
                )
            prepared.append(
                {
                    "merge_level": filters["merge_level"],
                    "dynamic_threshold": filters["dynamic_threshold"],
                    "years": years,
                }
            )
        invalidate("billboard")
        invalidate("db")
    if captured != source_fence(conn):
        raise RuntimeError("Billboard source changed during copy preparation")
    return {**verify_publications(conn), "prepared": prepared}


def verify_publications(conn):
    _assert_private()
    captured = source_fence(conn)
    targets = _targets(conn, lambda params: _read_exact("year_end", params))
    for family, params in targets:
        _read_exact(family, params)
    if captured != source_fence(conn):
        raise RuntimeError("Billboard source changed during verification")
    return {
        "status": "ready",
        "targets": len(targets),
        "builder_version": cache.BILLBOARD_CACHE_BUILDER_VERSION,
    }


def export_manifest(conn, path):
    _assert_private()
    captured = source_fence(conn)
    targets = _targets(conn, lambda params: _read_exact("year_end", params))
    entries = []
    for family, params in targets:
        payload = _read_exact(family, params)
        entries.append(
            {
                "family": family,
                "params": params,
                "dependencies": _dependencies(family, params),
                "payload": payload,
                "payload_digest": _digest(payload),
            }
        )
    if captured != source_fence(conn):
        raise RuntimeError("Billboard export source fence changed")
    payload = {
        "builder_version": cache.BILLBOARD_CACHE_BUILDER_VERSION,
        "source_fence": captured,
        "entries": entries,
    }
    manifest = {"digest": _digest(payload), "payload": payload}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=True, separators=(",", ":")) + "\n")
    path.chmod(0o600)
    return {"status": "exported", "targets": len(entries), "manifest_digest": manifest["digest"]}


def validate_manifest(conn, path):
    """Validate a relocation without building or publishing any facts."""
    _assert_private()
    manifest = json.loads(Path(path).read_text())
    payload = manifest["payload"]
    if (
        manifest["digest"] != _digest(payload)
        or payload["builder_version"] != cache.BILLBOARD_CACHE_BUILDER_VERSION
    ):
        raise RuntimeError("Billboard manifest digest/builder mismatch")
    if payload["source_fence"] != source_fence(conn):
        raise RuntimeError("Billboard manifest source/governance fence mismatch")
    entries = payload["entries"]
    if not isinstance(entries, list) or len(entries) > cache.DEFAULT_MAX_ENTRIES:
        raise RuntimeError("invalid Billboard manifest target count")
    by_key = {}
    for entry in entries:
        key = _digest([entry["family"], entry["params"]])
        if key in by_key:
            raise RuntimeError("duplicate Billboard manifest target")
        if entry["payload_digest"] != _digest(entry["payload"]):
            raise RuntimeError("Billboard payload checksum mismatch")
        if entry["dependencies"] != _dependencies(entry["family"], entry["params"]):
            raise RuntimeError("Billboard manifest factual dependency mismatch")
        cache._encode_payload(entry["payload"])
        by_key[key] = entry

    def latest(params):
        key = _digest(["year_end", params])
        if key not in by_key:
            raise RuntimeError("Billboard latest-year target missing")
        return by_key[key]["payload"]

    targets = _targets(conn, latest)
    if set(by_key) != {_digest([family, params]) for family, params in targets}:
        raise RuntimeError("Billboard manifest target set mismatch")
    return manifest, entries


def import_manifest(conn, path):
    """Rebind exact contexts and atomically publish only the target sidecar."""
    _assert_private()
    manifest, entries = validate_manifest(conn, path)
    captured = source_fence(conn)
    sidecar = cache._connect()
    try:
        sidecar.execute("BEGIN IMMEDIATE")
        for entry in entries:
            context = cache.build_cache_context(entry["family"], entry["params"])
            compressed, size, checksum = cache._encode_payload(entry["payload"])
            sidecar.execute(
                """INSERT OR REPLACE INTO billboard_snapshots(
                       cache_key,request_key,family,source_revision,builder_version,
                       payload,uncompressed_bytes,payload_sha256,created_at,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,datetime('now'),datetime('now'))""",
                (
                    context["cache_key"],
                    context["request_key"],
                    context["family"],
                    context["source_revision"],
                    context["builder_version"],
                    compressed,
                    size,
                    checksum,
                ),
            )
        # Every dependency is checked again before the one publication commit.
        confirmed, _ = validate_manifest(conn, path)
        if confirmed["digest"] != manifest["digest"]:
            raise RuntimeError("Billboard manifest changed during import")
        if captured != source_fence(conn):
            raise RuntimeError("Billboard source changed during import")
        sidecar.commit()
    except BaseException:
        sidecar.rollback()
        raise
    finally:
        sidecar.close()
    result = verify_publications(conn)
    return {**result, "status": "imported", "manifest_digest": manifest["digest"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--cache-path", type=Path, required=True)
    parser.add_argument("--owned-copy", action="store_true")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--build-on-copy", action="store_true")
    mode.add_argument("--export", type=Path)
    mode.add_argument("--import-manifest", type=Path)
    mode.add_argument("--validate-manifest", type=Path)
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    _assert_private()
    requested = args.db_path.resolve()
    sidecar = args.cache_path.resolve()
    if not requested.is_file() or requested == sidecar:
        raise RuntimeError("Billboard preparation requires separate existing source DB and sidecar")
    if args.build_on_copy and (
        requested.is_relative_to(PROJECT_ROOT / "data")
        or sidecar.is_relative_to(PROJECT_ROOT / "data")
        or (requested == Path(db.DB_PATH).resolve() and not args.owned_copy)
        or (sidecar == Path(cache.BILLBOARD_CACHE_PATH).resolve() and not args.owned_copy)
    ):
        raise RuntimeError("Billboard build requires owned copies outside formal data paths")
    db.DB_PATH = str(requested)
    cache.BILLBOARD_CACHE_PATH = str(sidecar)
    conn = db.get_db(readonly=True)
    try:
        if args.build_on_copy:
            result = prepare_publications(conn)
        elif args.export:
            result = export_manifest(conn, args.export)
        elif args.import_manifest:
            result = import_manifest(conn, args.import_manifest)
        elif args.validate_manifest:
            manifest, entries = validate_manifest(conn, args.validate_manifest)
            result = {
                "status": "validated",
                "targets": len(entries),
                "manifest_digest": manifest["digest"],
            }
        else:
            result = verify_publications(conn)
        print(json.dumps(result, ensure_ascii=True))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
