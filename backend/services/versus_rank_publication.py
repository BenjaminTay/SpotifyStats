"""Portable, bounded personal rank publications with read-only source fences."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from backend.core.access_surface import public_readonly_db_guard_active
from backend.services import analysis_snapshot_store as store
from backend.services import versus_rank_context_service as ranks

MANIFEST_VERSION = "versus_rank_publication_v1"
FILTER_TYPES = {
    "min_ms": int,
    "music_only": bool,
    "merge_enabled": bool,
    "dynamic_threshold": bool,
    "max_merge_gap_minutes": int,
    "merge_level": int,
    "include_compilations": bool,
}
METADATA_KEYS = {"source_revision", "filter_fingerprint", "statistics_contract_version"}
PUBLICATION_KEYS = {
    "family",
    "builder_version",
    "filters",
    "origin_request_key",
    "payload_digest",
    "payload",
    *METADATA_KEYS,
}


def validate_payload(payload, metadata):
    if not ranks._valid_payload(payload, metadata) or set(payload) != METADATA_KEYS | {
        "periods",
        "ranks",
    }:
        raise ValueError("Invalid personal rank payload contract")
    if set(payload["periods"]) != set(ranks.PERIODS) or set(payload["ranks"]) != set(ranks.KINDS):
        raise ValueError("Invalid personal rank period or entity inventory")
    for period, bounds in payload["periods"].items():
        if (
            set(bounds) != {"period", "label", "start_date", "end_date"}
            or not isinstance(bounds["label"], str)
            or not bounds["label"]
        ):
            raise ValueError("Invalid personal rank date boundaries")
        start, end = bounds["start_date"], bounds["end_date"]
        if (start is None) != (end is None):
            raise ValueError("Incomplete personal rank date boundaries")
        if start is not None:
            if (
                not isinstance(start, str)
                or not isinstance(end, str)
                or date.fromisoformat(start).isoformat() != start
                or date.fromisoformat(end).isoformat() != end
                or start > end
            ):
                raise ValueError("Invalid personal rank date boundaries")
        for kind in ranks.KINDS:
            if set(payload["ranks"][kind]) != set(ranks.PERIODS):
                raise ValueError("Incomplete personal rank windows")
            mapping = payload["ranks"][kind][period]
            if len(set(mapping.values())) != len(mapping):
                raise ValueError("Duplicate personal rank ordinal")
            if any(
                not key
                or (
                    kind != "artist"
                    and (not key.isdecimal() or int(key) <= 0 or str(int(key)) != key)
                )
                for key in mapping
            ):
                raise ValueError("Invalid personal rank entity key")


def export_bundle(conn, filters=None, *, release_sha=None):
    variants = [filters] if filters is not None else ranks.default_configurations(conn)
    publications = [ranks.export_publication(conn, variant) for variant in variants]
    # Export is a single coherent source revision even when maintenance commits
    # while the four files are being read.
    if len({item["source_revision"] for item in publications}) != 1:
        raise ValueError("Personal rank source changed during export")
    for item in publications:
        validate_payload(item["payload"], {name: item[name] for name in METADATA_KEYS})
    bundle = {
        "manifest_version": MANIFEST_VERSION,
        "builder_version": ranks.VERSION,
        "publications": publications,
    }
    if release_sha is not None:
        if (
            not isinstance(release_sha, str)
            or not 7 <= len(release_sha) <= 64
            or any(c not in "0123456789abcdef" for c in release_sha)
        ):
            raise ValueError("Invalid personal rank release SHA")
        bundle["release_sha"] = release_sha
    return bundle


def _validated_publications(conn, bundle, *, expected_release_sha=None, require_defaults=False):
    if conn.in_transaction:
        raise ValueError("Personal rank source fence requires a committed read-only connection")
    if (
        not isinstance(bundle, dict)
        or set(bundle)
        not in (
            {"manifest_version", "builder_version", "publications"},
            {"manifest_version", "builder_version", "publications", "release_sha"},
        )
        or bundle["manifest_version"] != MANIFEST_VERSION
        or bundle["builder_version"] != ranks.VERSION
    ):
        raise ValueError("Unsupported personal rank manifest")
    if expected_release_sha is not None and bundle.get("release_sha") != expected_release_sha:
        raise ValueError("Personal rank manifest is not bound to the target release SHA")
    publications = bundle["publications"]
    if not isinstance(publications, list) or not 1 <= len(publications) <= 4:
        raise ValueError("Personal rank installation requires one to four publications")
    entries = []
    for item in publications:
        if not isinstance(item, dict) or set(item) != PUBLICATION_KEYS:
            raise ValueError("Invalid personal rank publication manifest")
        if (
            item["family"] not in (ranks.FAMILY, ranks.CUSTOM_FAMILY)
            or item["builder_version"] != ranks.VERSION
        ):
            raise ValueError(
                "Personal rank installer accepts only its declared families and version"
            )
        filters = item["filters"]
        if (
            not isinstance(filters, dict)
            or set(filters) != set(FILTER_TYPES)
            or any(type(filters[name]) is not expected for name, expected in FILTER_TYPES.items())
        ):
            raise ValueError("Personal rank manifest filters are not normalized")
        params, key, metadata, family = ranks.request_context(conn, filters)
        if (
            filters != params
            or item["family"] != family
            or any(item.get(name) != value for name, value in metadata.items())
        ):
            raise ValueError("Personal rank manifest source or filters differ from target")
        if (
            not isinstance(item["origin_request_key"], str)
            or len(item["origin_request_key"]) != 64
            or any(character not in "0123456789abcdef" for character in item["origin_request_key"])
        ):
            raise ValueError("Invalid personal rank origin key")
        validate_payload(item["payload"], metadata)
        if item["payload_digest"] != store.digest(item["payload"]):
            raise ValueError("Personal rank payload digest mismatch")
        entries.append((family, key, metadata["source_revision"], ranks.VERSION, item["payload"]))
    if len({entry[1] for entry in entries}) != len(entries):
        raise ValueError("Duplicate personal rank manifest configuration")
    if len({entry[2] for entry in entries}) != 1:
        raise ValueError("Personal rank manifest mixes source revisions")
    if require_defaults:
        expected_filters = {store.digest(params) for params in ranks.default_configurations(conn)}
        actual_filters = {store.digest(item["filters"]) for item in publications}
        if actual_filters != expected_filters or any(
            item["family"] != ranks.FAMILY for item in publications
        ):
            raise ValueError(
                "Deployment requires all four current default personal rank configurations"
            )
    return entries


def install_bundle(
    conn, bundle, *, expected_release_sha=None, require_defaults=False, source_fence=None
):
    """Rebase lineage keys, writing only the Analysis sidecar in one transaction."""
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot install personal rank publications")
    source_path = Path(conn.execute("PRAGMA database_list").fetchone()[2]).resolve()
    destination = store.path().resolve()
    if destination == source_path or (destination.exists() and source_path.samefile(destination)):
        raise ValueError("Personal rank sidecar must be separate from its source database")
    entries = _validated_publications(
        conn, bundle, expected_release_sha=expected_release_sha, require_defaults=require_defaults
    )
    expected = [(row[0], row[1], row[2], row[3]) for row in entries]

    def fence():
        if source_fence is not None:
            source_fence()
        current = _validated_publications(
            conn,
            bundle,
            expected_release_sha=expected_release_sha,
            require_defaults=require_defaults,
        )
        if [(row[0], row[1], row[2], row[3]) for row in current] != expected:
            raise ValueError("Personal rank source changed during installation")

    store.publish_many(entries, before_commit=fence)
    ranks._read_cached.cache_clear()
    return {
        "installed": len(entries),
        "builder_version": ranks.VERSION,
        "source_revision": entries[0][2],
        "request_keys": [row[1] for row in entries],
    }
