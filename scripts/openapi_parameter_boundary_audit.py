#!/usr/bin/env python3
"""Account for OpenAPI parameter boundary coverage.

This probe does not execute endpoints. It audits bounded/pattern query
parameters and integer path parameters against the reusable non-mutating
boundary probe so request parameter validation cannot silently drift outside
the verification matrix.
"""

from __future__ import annotations

# ruff: noqa: UP045
import argparse
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_boundary_probe import DEFAULT_BOUNDARY_CASES  # noqa: E402

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}
BOUNDARY_SCHEMA_KEYS = (
    "maximum",
    "minimum",
    "exclusiveMaximum",
    "exclusiveMinimum",
    "maxLength",
    "minLength",
    "pattern",
    "enum",
)


@dataclass(frozen=True)
class ParameterEvidence:
    category: str
    case_names: tuple[str, ...]
    rationale: str

    @property
    def evidence(self) -> str:
        return ", ".join(self.case_names)


@dataclass(frozen=True)
class ParameterBoundaryObligation:
    location: str
    name: str
    signature: str
    occurrence_count: int
    examples: tuple[str, ...]
    category: str
    evidence: str
    rationale: str


@dataclass(frozen=True)
class ParameterBoundaryAudit:
    obligation_count: int
    obligations: tuple[ParameterBoundaryObligation, ...]
    unaccounted_obligations: tuple[ParameterBoundaryObligation, ...]
    category_counts: dict[str, int]

    @property
    def obligations_by_key(self) -> dict[tuple[str, str, str], ParameterBoundaryObligation]:
        return {(row.location, row.name, row.signature): row for row in self.obligations}


BOUNDARY_EVIDENCE_BY_KEY: dict[tuple[str, str, str], ParameterEvidence] = {
    ("query", "artist_limit", "integer|maximum=20|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("community_trending_artist_limit_low", "community_trending_artist_limit_high"),
        "community trending artist limit is validated at both bounds",
    ),
    ("query", "bb_album_top_n", "integer|maximum=100|minimum=5"): ParameterEvidence(
        "boundary_probe",
        ("billboard_album_top_n_low", "billboard_album_top_n_high"),
        "Billboard album top-N bound is validated on the shared filter dependency",
    ),
    ("query", "bb_artist_top_n", "integer|maximum=100|minimum=5"): ParameterEvidence(
        "boundary_probe",
        ("billboard_artist_top_n_low", "billboard_artist_top_n_high"),
        "Billboard artist top-N bound is validated on the shared filter dependency",
    ),
    ("query", "bb_top_n", "integer|maximum=100|minimum=5"): ParameterEvidence(
        "boundary_probe",
        ("billboard_top_n_low", "billboard_top_n_high"),
        "Billboard track top-N bound is validated on the shared filter dependency",
    ),
    ("query", "bb_week_start_dow", "integer|maximum=6|minimum=0"): ParameterEvidence(
        "boundary_probe",
        ("billboard_week_start_dow_low", "billboard_week_start_dow_high"),
        "Billboard week day offset is validated at both bounds",
    ),
    ("query", "bb_week_start_hour", "integer|maximum=23|minimum=0"): ParameterEvidence(
        "boundary_probe",
        ("billboard_week_start_hour_low", "billboard_week_start_hour_high"),
        "Billboard week hour offset is validated at both bounds",
    ),
    ("query", "entity", "string|pattern=^(track|artist|album)$"): ParameterEvidence(
        "boundary_probe",
        ("leaderboard_invalid_entity", "leaderboard_empty_entity"),
        "leaderboard entity pattern rejects invalid and empty values",
    ),
    ("query", "album_id_a", "integer"): ParameterEvidence(
        "boundary_probe",
        ("version_compare_album_id_a_nonint",),
        "version compare album A id rejects non-integers",
    ),
    ("query", "album_id_b", "integer"): ParameterEvidence(
        "boundary_probe",
        ("version_compare_album_id_b_nonint",),
        "version compare album B id rejects non-integers",
    ),
    ("query", "limit", "integer|maximum=200|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("analysis_plays_limit_zero", "analysis_plays_limit_too_high"),
        "pagination limit bound is validated on a representative paginated route",
    ),
    ("query", "limit", "integer|maximum=5000|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("analysis_charts_limit_zero", "analysis_charts_limit_too_high"),
        "large analysis chart limit is validated at both bounds",
    ),
    ("query", "limit", "integer"): ParameterEvidence(
        "boundary_probe",
        ("library_saved_tracks_limit_nonint",),
        "type-only saved-track pagination limit rejects non-integers",
    ),
    ("query", "merge_level", "integer|maximum=3|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("analysis_charts_merge_level_low", "analysis_charts_merge_level_high"),
        "merge-level shared dependency is validated below and above the allowed range",
    ),
    ("query", "max_merge_gap_minutes", "integer|maximum=240|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("analysis_overview_max_merge_gap_low", "analysis_overview_max_merge_gap_high"),
        "shared merge-gap dependency is validated below and above the allowed range",
    ),
    ("query", "metric", "string|pattern=^(plays|hours)$"): ParameterEvidence(
        "boundary_probe",
        ("leaderboard_invalid_metric",),
        "leaderboard metric pattern rejects unsupported metrics",
    ),
    ("query", "min_ms", "integer|minimum=0"): ParameterEvidence(
        "boundary_probe",
        ("analysis_overview_min_ms_negative",),
        "shared play filter minimum duration rejects negative values",
    ),
    ("query", "n", "integer"): ParameterEvidence(
        "boundary_probe",
        ("dashboard_top_tracks_n_nonint",),
        "dashboard top-track count rejects non-integers",
    ),
    ("query", "offset", "integer|minimum=0"): ParameterEvidence(
        "boundary_probe",
        ("analysis_plays_offset_negative",),
        "pagination offset rejects negative values on a representative route",
    ),
    ("query", "page", "integer"): ParameterEvidence(
        "boundary_probe",
        ("library_saved_tracks_page_nonint",),
        "saved-track page rejects non-integers",
    ),
    ("query", "overlap_threshold", "number|maximum=1.0|minimum=0.1"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("OpenAPI schema + version-merge service contracts",),
        "version-merge detection is a POST workflow outside the default non-mutating boundary probe",
    ),
    ("query", "significance_min", "number|maximum=1.0|minimum=0.0"): ParameterEvidence(
        "boundary_probe",
        ("community_significance_low", "community_significance_high"),
        "community feed significance threshold is validated below and above range",
    ),
    (
        "query",
        "time_range",
        "string|pattern=^(all|this_year|this_month|custom)$",
    ): ParameterEvidence(
        "boundary_probe",
        ("leaderboard_invalid_time_range",),
        "leaderboard time range pattern rejects unsupported ranges",
    ),
    ("query", "top_n", "integer|maximum=100|minimum=5"): ParameterEvidence(
        "boundary_probe",
        ("leaderboard_top_n_low", "leaderboard_top_n_high"),
        "leaderboard top-N bound is validated at both bounds",
    ),
    ("query", "track_limit", "integer|maximum=20|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("community_trending_track_limit_low", "community_trending_track_limit_high"),
        "community trending track limit is validated at both bounds",
    ),
    ("query", "track_id_a", "integer"): ParameterEvidence(
        "boundary_probe",
        ("billboard_versus_track_id_a_nonint",),
        "Billboard versus track A id rejects non-integers",
    ),
    ("query", "track_id_b", "integer"): ParameterEvidence(
        "boundary_probe",
        ("billboard_versus_track_id_b_nonint",),
        "Billboard versus track B id rejects non-integers",
    ),
    ("query", "weeks_after", "integer|maximum=104|minimum=4"): ParameterEvidence(
        "boundary_probe",
        ("release_cycle_album_weeks_after_low", "release_cycle_weeks_after_high"),
        "release-cycle album window after bound is validated at both bounds",
    ),
    ("query", "weeks_after", "integer|maximum=52|minimum=4"): ParameterEvidence(
        "boundary_probe",
        ("release_cycle_artist_weeks_after_low", "release_cycle_artist_weeks_after_high"),
        "release-cycle artist window after bound is validated at both bounds",
    ),
    ("query", "weeks_before", "integer|maximum=24|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("release_cycle_artist_weeks_before_low", "release_cycle_artist_weeks_before_high"),
        "release-cycle artist window before bound is validated at both bounds",
    ),
    ("query", "weeks_before", "integer|maximum=52|minimum=1"): ParameterEvidence(
        "boundary_probe",
        ("release_cycle_weeks_before_low", "release_cycle_album_weeks_before_high"),
        "release-cycle album window before bound is validated at both bounds",
    ),
    ("query", "year", "integer"): ParameterEvidence(
        "boundary_probe",
        ("ai_insights_year_nonint",),
        "AI insights report year rejects non-integers before any generation work",
    ),
    ("path", "entity_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("covers_entity_id_nonint",),
        "cover path integer conversion rejects non-integers",
    ),
    ("path", "group_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("version_group_path_nonint",),
        "version group path integer conversion rejects non-integers",
    ),
    ("path", "playlist_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("library_playlist_path_nonint",),
        "playlist path integer conversion rejects non-integers",
    ),
    ("path", "profile_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("settings_llm_profile_path_nonint",),
        "settings profile path integer conversion rejects non-integers",
    ),
    ("path", "session_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("chat_session_path_nonint",),
        "chat session path integer conversion rejects non-integers",
    ),
    ("path", "track_id", "integer"): ParameterEvidence(
        "boundary_probe",
        ("music_track_path_nonint", "billboard_track_path_nonint", "lyrics_path_nonint"),
        "track-id path conversion is validated across music, Billboard, and lyrics surfaces",
    ),
    ("path", "year", "integer"): ParameterEvidence(
        "boundary_probe",
        ("wrapped_year_path_nonint",),
        "wrapped year path integer conversion rejects non-integers",
    ),
    ("path", "album_name", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_album_long_name", "music_album_long_name"),
        "album-name path strings accept overlong not-found values without server errors",
    ),
    ("path", "artist_name", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_artist_long_name", "music_artist_long_name"),
        "artist-name path strings accept overlong not-found values without server errors",
    ),
    ("path", "cover_type", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("cover_type_long",),
        "cover type path string accepts overlong unknown values as a controlled 404",
    ),
    ("path", "job_id", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("job_status_long_missing", "import_status_long_missing"),
        "job id path strings accept overlong missing IDs without server errors",
    ),
    ("path", "name", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("artist_deep_dive_long_name",),
        "artist deep-dive path strings accept overlong not-found values without server errors",
    ),
    ("path", "post_id", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("community_post_long_missing",),
        "community post id path strings accept overlong missing IDs as a controlled 404",
    ),
    ("path", "track_name", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("OpenAPI schema + Billboard enrichment degradation contracts",),
        "track-name string path belongs to optional external enrichment outside local boundary probe",
    ),
    ("query", "album_a", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_versus_album_a_empty", "billboard_versus_album_a_long"),
        "album-versus album A query handles empty and overlong strings without server errors",
    ),
    ("query", "album_b", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_versus_album_b_empty",),
        "album-versus album B query handles empty strings without server errors",
    ),
    ("query", "album_ids", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("version_album_types_album_ids_empty", "version_album_types_album_ids_long"),
        "album id list query handles empty and long lists without server errors",
    ),
    ("query", "artist_a", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_versus_artist_a_empty", "billboard_versus_artist_a_long"),
        "versus artist A query handles empty and overlong strings without server errors",
    ),
    ("query", "artist_b", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_versus_artist_a_empty",),
        "versus artist B participates in the safe empty-string versus probe",
    ),
    ("query", "artist_name", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("billboard_album_artist_name_empty", "billboard_album_artist_name_long"),
        "artist-name query handles empty and overlong filters without server errors",
    ),
    ("query", "code", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("backend/tests/contract/test_spotify_auth_contract.py",),
        "OAuth callback code depends on browser-auth state and is covered by PKCE contracts",
    ),
    ("query", "entity", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("analysis_charts_entity_empty", "analysis_charts_entity_long"),
        "analysis chart entity query handles empty and overlong strings without server errors",
    ),
    ("query", "metric", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("analysis_charts_metric_empty", "analysis_charts_metric_long"),
        "analysis chart metric query handles empty and overlong strings without server errors",
    ),
    ("query", "month", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("backend/tests/contract/test_ai_insights_contract.py",),
        "AI monthly report string date input belongs to LLM-generating contract coverage",
    ),
    ("query", "period", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("analysis_stats_period_empty", "analysis_stats_period_long"),
        "shared period query handles empty and overlong strings without server errors",
    ),
    ("query", "search", "string"): ParameterEvidence(
        "string_resilience_probe",
        ("library_saved_tracks_search_empty", "library_saved_tracks_search_long"),
        "saved-track search handles empty and overlong strings without server errors",
    ),
    ("query", "state", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("backend/tests/contract/test_spotify_auth_contract.py",),
        "OAuth callback state depends on browser-auth state and is covered by PKCE contracts",
    ),
    ("query", "week_end", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("backend/tests/contract/test_ai_insights_contract.py",),
        "AI weekly report date input belongs to LLM-generating contract coverage",
    ),
    ("query", "week_start", "string"): ParameterEvidence(
        "controlled_stateful_or_external",
        ("backend/tests/contract/test_ai_insights_contract.py",),
        "AI weekly report date input belongs to LLM-generating contract coverage",
    ),
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="openapi_parameter_boundary_audit.py",
        description="Classify OpenAPI parameter boundary obligations by validation evidence.",
    )
    parser.add_argument("--json-output", default=None, help="Write audit details as JSON.")
    return parser.parse_args(argv)


def _effective_schema(schema: dict) -> dict:
    """Return the validating branch for nullable OpenAPI parameter schemas."""
    for key in ("anyOf", "oneOf"):
        variants = schema.get(key)
        if not isinstance(variants, list):
            continue
        non_null = [
            variant
            for variant in variants
            if isinstance(variant, dict) and variant.get("type") != "null"
        ]
        if len(non_null) == 1:
            merged = {k: v for k, v in schema.items() if k not in {"anyOf", "oneOf"}}
            merged.update(non_null[0])
            return merged
    return schema


def _schema_signature(schema: dict) -> str:
    schema = _effective_schema(schema)
    schema_type = str(schema.get("type") or "any")
    parts = [schema_type]
    for key in BOUNDARY_SCHEMA_KEYS:
        if key not in schema:
            continue
        value = schema[key]
        if isinstance(value, list):
            value = ",".join(str(item) for item in value)
        parts.append(f"{key}={value}")
    return "|".join(parts)


def _has_boundary_constraints(schema: dict) -> bool:
    schema = _effective_schema(schema)
    return any(key in schema for key in BOUNDARY_SCHEMA_KEYS)


def _is_obligation(location: str, schema: dict) -> bool:
    raw_type = schema.get("type")
    effective = _effective_schema(schema)
    if location == "path" and effective.get("type") == "integer":
        return True
    if location == "path" and effective.get("type") == "string":
        return True
    if location == "query" and raw_type == "integer":
        return True
    if location == "query" and raw_type == "string":
        return True
    if location == "query" and _has_boundary_constraints(effective):
        return True
    return False


def _iter_parameter_obligations(schema: dict) -> dict[tuple[str, str, str], list[str]]:
    groups: dict[tuple[str, str, str], list[str]] = {}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in HTTP_METHODS:
                continue
            for parameter in operation.get("parameters") or ():
                location = parameter.get("in") or ""
                param_schema = parameter.get("schema") or {}
                if not _is_obligation(location, param_schema):
                    continue
                key = (location, parameter.get("name", ""), _schema_signature(param_schema))
                groups.setdefault(key, []).append(f"{method.upper()} {path}")
    return groups


def _classify_obligation(
    key: tuple[str, str, str],
    boundary_case_names: set[str],
) -> ParameterEvidence:
    evidence = BOUNDARY_EVIDENCE_BY_KEY.get(key)
    if evidence is None:
        return ParameterEvidence(
            "unaccounted",
            (),
            "parameter boundary is not tied to api_boundary_probe or an explicit exclusion",
        )
    if evidence.category in {"boundary_probe", "string_resilience_probe"}:
        missing = tuple(
            case_name for case_name in evidence.case_names if case_name not in boundary_case_names
        )
        if missing:
            return ParameterEvidence(
                "unaccounted",
                missing,
                "declared boundary evidence does not exist in DEFAULT_BOUNDARY_CASES",
            )
    return evidence


def build_parameter_boundary_audit(app) -> ParameterBoundaryAudit:
    schema = app.openapi()
    boundary_case_names = {case.name for case in DEFAULT_BOUNDARY_CASES}
    obligations: list[ParameterBoundaryObligation] = []

    for key, examples in sorted(_iter_parameter_obligations(schema).items()):
        evidence = _classify_obligation(key, boundary_case_names)
        location, name, signature = key
        obligations.append(
            ParameterBoundaryObligation(
                location=location,
                name=name,
                signature=signature,
                occurrence_count=len(examples),
                examples=tuple(examples[:5]),
                category=evidence.category,
                evidence=evidence.evidence,
                rationale=evidence.rationale,
            )
        )

    unaccounted = tuple(row for row in obligations if row.category == "unaccounted")
    category_counts = dict(Counter(row.category for row in obligations))
    return ParameterBoundaryAudit(
        obligation_count=len(obligations),
        obligations=tuple(obligations),
        unaccounted_obligations=unaccounted,
        category_counts=category_counts,
    )


def assert_parameter_boundary_audit(audit: ParameterBoundaryAudit) -> None:
    if audit.unaccounted_obligations:
        lines = [
            f"- {row.location} {row.name} {row.signature} ({row.occurrence_count} occurrences)"
            for row in audit.unaccounted_obligations
        ]
        raise AssertionError(
            "Unaccounted OpenAPI parameter boundary obligations:\n" + "\n".join(lines)
        )


def render_markdown_report(audit: ParameterBoundaryAudit) -> str:
    lines = [
        "# OpenAPI parameter boundary audit",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total obligations | {audit.obligation_count} |",
        f"| Unaccounted obligations | {len(audit.unaccounted_obligations)} |",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for category, count in sorted(audit.category_counts.items()):
        lines.append(f"| {category} | {count} |")
    lines.extend(
        [
            "",
            "| Location | Name | Signature | Occurrences | Category | Evidence |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in audit.obligations:
        lines.append(
            f"| {row.location} | `{row.name}` | `{row.signature}` | "
            f"{row.occurrence_count} | {row.category} | {row.evidence} |"
        )
    return "\n".join(lines)


def audit_to_json_dict(audit: ParameterBoundaryAudit) -> dict:
    return {
        "obligation_count": audit.obligation_count,
        "category_counts": audit.category_counts,
        "unaccounted_obligations": [asdict(row) for row in audit.unaccounted_obligations],
        "obligations": [asdict(row) for row in audit.obligations],
    }


def write_json_report(audit: ParameterBoundaryAudit, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(audit_to_json_dict(audit), handle, ensure_ascii=False, indent=2)


def main(argv: Optional[Sequence[str]] = None) -> int:
    from backend.main import app

    args = parse_args(argv)
    audit = build_parameter_boundary_audit(app)
    print(render_markdown_report(audit))
    if args.json_output:
        write_json_report(audit, Path(args.json_output))
        print(f"\nOpenAPI parameter boundary audit JSON written to {args.json_output}")
    assert_parameter_boundary_audit(audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
