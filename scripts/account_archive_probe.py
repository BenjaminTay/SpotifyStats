#!/usr/bin/env python3
"""Read-only evidence probe for account archive coverage and overview budgets."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.domains.account_archive.cohorts import build_collection_cohorts  # noqa: E402
from backend.domains.account_archive.context import build_archive_filter_context  # noqa: E402
from backend.domains.account_archive.discovery import build_archive_discovery  # noqa: E402
from backend.domains.account_archive.journey import build_collection_journey  # noqa: E402
from backend.domains.account_archive.library import build_archive_library_page  # noqa: E402
from backend.domains.account_archive.other_media import build_archive_other_media  # noqa: E402
from backend.domains.account_archive.overview import build_archive_overview  # noqa: E402
from backend.domains.account_archive.returns import build_archive_returns  # noqa: E402
from backend.models.account_archive import (  # noqa: E402
    ArchiveCohortsResponse,
    ArchiveDiscoveryResponse,
    ArchiveJourneyResponse,
    ArchiveLibraryPageResponse,
    ArchiveOtherMediaResponse,
    ArchiveOverviewResponse,
    ArchiveReturnsResponse,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, required=True)
    parser.add_argument("--expect-saved-tracks", type=int)
    parser.add_argument("--expect-dated-tracks", type=int)
    args = parser.parse_args()

    if not args.db_path.is_file():
        parser.error(f"database not found: {args.db_path}")

    uri = args.db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    total_started = time.perf_counter()
    try:
        started = time.perf_counter()
        context = build_archive_filter_context(
            conn,
            {
                "min_ms": None,
                "merge_enabled": None,
                "dynamic_threshold": True,
                "max_merge_gap_minutes": 5,
                "merge_level": 2,
            },
        )
        context_ms = round((time.perf_counter() - started) * 1000, 2)

        started = time.perf_counter()
        overview = build_archive_overview(conn)
        overview_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_overview = ArchiveOverviewResponse.model_validate(overview).model_dump(
            mode="json"
        )

        started = time.perf_counter()
        journey = build_collection_journey(conn, context)
        journey_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_journey = ArchiveJourneyResponse.model_validate(journey).model_dump(mode="json")

        started = time.perf_counter()
        cohorts = build_collection_cohorts(conn, context)
        cohorts_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_cohorts = ArchiveCohortsResponse.model_validate(cohorts).model_dump(mode="json")

        started = time.perf_counter()
        returns = build_archive_returns(conn, context)
        returns_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_returns = ArchiveReturnsResponse.model_validate(returns).model_dump(mode="json")

        started = time.perf_counter()
        discovery = build_archive_discovery(conn, context)
        discovery_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_discovery = ArchiveDiscoveryResponse.model_validate(discovery).model_dump(
            mode="json"
        )

        started = time.perf_counter()
        validated_library = {
            entity_type: ArchiveLibraryPageResponse.model_validate(
                build_archive_library_page(
                    conn,
                    entity_type,
                    page=1,
                    limit=20,
                )
            ).model_dump(mode="json")
            for entity_type in ("tracks", "albums", "artists", "playlists")
        }
        library_ms = round((time.perf_counter() - started) * 1000, 2)

        started = time.perf_counter()
        other_media = build_archive_other_media(conn, context)
        other_media_ms = round((time.perf_counter() - started) * 1000, 2)
        validated_other_media = ArchiveOtherMediaResponse.model_validate(other_media).model_dump(
            mode="json"
        )
    finally:
        conn.close()
    elapsed_ms = round((time.perf_counter() - total_started) * 1000, 2)
    raw_bytes = {
        "overview": len(
            json.dumps(validated_overview, ensure_ascii=False, separators=(",", ":")).encode()
        ),
        "journey": len(
            json.dumps(validated_journey, ensure_ascii=False, separators=(",", ":")).encode()
        ),
        "cohorts": len(
            json.dumps(validated_cohorts, ensure_ascii=False, separators=(",", ":")).encode()
        ),
        "returns": len(
            json.dumps(validated_returns, ensure_ascii=False, separators=(",", ":")).encode()
        ),
        "discovery": len(
            json.dumps(validated_discovery, ensure_ascii=False, separators=(",", ":")).encode()
        ),
        **{
            f"library_{entity_type}": len(
                json.dumps(page, ensure_ascii=False, separators=(",", ":")).encode()
            )
            for entity_type, page in validated_library.items()
        },
        "other_media": len(
            json.dumps(validated_other_media, ensure_ascii=False, separators=(",", ":")).encode()
        ),
    }

    output = {
        "probe_version": "account_archive_probe_v5",
        "database": str(args.db_path.resolve()),
        "elapsed_ms": elapsed_ms,
        "stage_ms": {
            "context": context_ms,
            "overview": overview_ms,
            "journey": journey_ms,
            "cohorts": cohorts_ms,
            "returns": returns_ms,
            "discovery": discovery_ms,
            "library": library_ms,
            "other_media": other_media_ms,
        },
        "raw_bytes": raw_bytes,
        "overview": validated_overview,
        "journey": validated_journey,
        "cohorts": validated_cohorts,
        "returns": validated_returns,
        "discovery": validated_discovery,
        "library": validated_library,
        "other_media": validated_other_media,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    failures: list[str] = []
    if (
        args.expect_saved_tracks is not None
        and validated_overview["counts"]["saved_tracks"] != args.expect_saved_tracks
    ):
        failures.append(
            f"saved_tracks expected {args.expect_saved_tracks}, "
            f"got {validated_overview['counts']['saved_tracks']}"
        )
    if (
        args.expect_dated_tracks is not None
        and validated_overview["coverage"]["saved_tracks_with_date"] != args.expect_dated_tracks
    ):
        failures.append(
            f"dated tracks expected {args.expect_dated_tracks}, "
            f"got {validated_overview['coverage']['saved_tracks_with_date']}"
        )
    if raw_bytes["overview"] > 40_000:
        failures.append(f"archive-overview raw size {raw_bytes['overview']} exceeds 40000 bytes")
    if raw_bytes["cohorts"] > 120_000:
        failures.append(f"collection-cohorts raw size {raw_bytes['cohorts']} exceeds 120000 bytes")
    if raw_bytes["returns"] > 80_000:
        failures.append(f"returns raw size {raw_bytes['returns']} exceeds 80000 bytes")
    if raw_bytes["discovery"] > 80_000:
        failures.append(f"discovery raw size {raw_bytes['discovery']} exceeds 80000 bytes")
    for entity_type in ("tracks", "albums", "artists", "playlists"):
        library_bytes = raw_bytes[f"library_{entity_type}"]
        if library_bytes > 80_000:
            failures.append(f"library {entity_type} raw size {library_bytes} exceeds 80000 bytes")
    if raw_bytes["other_media"] > 80_000:
        failures.append(f"other-media raw size {raw_bytes['other_media']} exceeds 80000 bytes")
    if context_ms + cohorts_ms > 1_500:
        failures.append(
            f"collection-cohorts cold build {context_ms + cohorts_ms:.2f}ms exceeds 1500ms"
        )
    if context_ms + returns_ms > 1_500:
        failures.append(f"returns cold build {context_ms + returns_ms:.2f}ms exceeds 1500ms")
    if context_ms + discovery_ms > 1_500:
        failures.append(f"discovery cold build {context_ms + discovery_ms:.2f}ms exceeds 1500ms")
    if library_ms > 500:
        failures.append(f"library four-page cold build {library_ms:.2f}ms exceeds 500ms")
    if context_ms + other_media_ms > 1_500:
        failures.append(
            f"other-media cold build {context_ms + other_media_ms:.2f}ms exceeds 1500ms"
        )
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
