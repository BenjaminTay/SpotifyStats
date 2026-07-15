#!/usr/bin/env python3
"""Account for every FastAPI OpenAPI operation.

This probe does not execute endpoints. It classifies the current OpenAPI
surface into evidence buckets so newly added operations cannot silently sit
outside smoke tests, contract tests, or an explicit stateful/external exclusion.
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

from scripts.api_smoke_probe import (  # noqa: E402
    DEFAULT_EXCLUDED_GET_PATHS,
    DEFAULT_SAFE_GET_CASES,
    _covered_openapi_get_paths,
)

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}


@dataclass(frozen=True)
class OperationEvidence:
    category: str
    evidence: str
    rationale: str


@dataclass(frozen=True)
class OperationAuditRow:
    method: str
    path: str
    operation_id: str
    tags: tuple[str, ...]
    category: str
    evidence: str
    rationale: str


@dataclass(frozen=True)
class OperationAudit:
    operation_count: int
    operations: tuple[OperationAuditRow, ...]
    unaccounted_operations: tuple[OperationAuditRow, ...]
    category_counts: dict[str, int]

    @property
    def operations_by_key(self) -> dict[tuple[str, str], OperationAuditRow]:
        return {(row.method, row.path): row for row in self.operations}


TARGETED_CONTRACT_OPERATIONS: dict[tuple[str, str], OperationEvidence] = {
    ("GET", "/api/metadata/artist-languages/coverage"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_language_metadata_api.py",
        "Artist language coverage and playback-filter behavior are covered by isolated contracts.",
    ),
    ("GET", "/api/metadata/artist-languages/reviews"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_language_metadata_api.py",
        "Artist language review listing and query validation are covered by isolated contracts.",
    ),
    ("POST", "/api/metadata/artist-languages/reviews"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_language_metadata_api.py",
        "Artist language review creation and idempotency are covered by isolated contracts.",
    ),
    ("PUT", "/api/metadata/artist-languages/reviews/{review_id}/source"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_language_metadata_api.py",
        "Artist language evidence validation and source replacement are covered by isolated contracts.",
    ),
    ("PATCH", "/api/metadata/artist-languages/reviews/{review_id}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_language_metadata_api.py",
        "Artist language review decisions and conflict handling are covered by isolated contracts.",
    ),
    ("GET", "/api/ai-insights/monthly-personality"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_insights_contract.py",
        "LLM-generating report path is monkeypatched in contract tests instead of called live.",
    ),
    ("GET", "/api/ai-insights/weekly-digest"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_insights_contract.py",
        "LLM-generating report path is monkeypatched in contract tests instead of called live.",
    ),
    ("GET", "/api/ai-insights/yearly-story"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_insights_contract.py",
        "LLM-generating report path is monkeypatched in contract tests instead of called live.",
    ),
    ("POST", "/api/ai-insights/ask"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_insights_contract.py",
        "LLM question path is monkeypatched in contract tests to avoid external generation.",
    ),
    ("POST", "/api/ai/tasks/report"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_task_api.py",
        "AI report task creation and request validation are covered by contract tests.",
    ),
    ("POST", "/api/ai/tasks/chat"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_agent_task_contract.py",
        "AI chat agent task creation and deterministic runner paths are covered by contract tests.",
    ),
    ("POST", "/api/ai/tasks/enrichment/artist"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_enrichment_tasks.py",
        "Artist enrichment task creation, progress events, result, and validation are covered.",
    ),
    ("POST", "/api/ai/tasks/enrichment/album"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_enrichment_tasks.py",
        "Album enrichment task creation, nullable wiki result, and validation are covered.",
    ),
    ("POST", "/api/ai/tasks/metadata/artist-genres"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_backfill_task.py",
        "Artist genre backfill task creation, suggestions, tool calls, and validation are covered.",
    ),
    ("GET", "/api/metadata/artist-genres/coverage"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre coverage report is covered by isolated contract data.",
    ),
    ("GET", "/api/metadata/artist-genres/taxonomy"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre taxonomy audit and canonical labels are covered by isolated contract data.",
    ),
    ("GET", "/api/metadata/artist-genres/reviews"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre review queue listing is covered by isolated contract data.",
    ),
    (
        "PATCH",
        "/api/metadata/artist-genres/reviews/{review_id}/evidence",
    ): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre evidence editing and HTTPS validation are covered by contract tests.",
    ),
    ("POST", "/api/metadata/artist-genres/reviews/{review_id}/approve"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre review approval and resolver effect are covered by contract tests.",
    ),
    ("POST", "/api/metadata/artist-genres/reviews/{review_id}/reject"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_artist_genre_metadata_api.py",
        "Artist genre review rejection and stale review behavior are covered by contract tests.",
    ),
    ("POST", "/api/ai/tasks/{task_id}/cancel"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_ai_task_api.py",
        "AI task cancellation state transitions are covered by contract tests.",
    ),
    ("GET", "/api/billboard/enrichment/album/{album_name}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_billboard_enrichment_contract.py",
        "External Wikipedia enrichment is covered by offline degradation contracts.",
    ),
    ("GET", "/api/billboard/enrichment/artist/{artist_name}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_billboard_enrichment_contract.py",
        "External Wikipedia enrichment is covered by offline degradation contracts.",
    ),
    ("GET", "/api/billboard/enrichment/track/{track_name}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_billboard_enrichment_contract.py",
        "External Wikipedia enrichment is covered by offline degradation contracts.",
    ),
    ("POST", "/api/billboard/release-cycle/compare"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_remaining_json_response_models.py",
        "Request-body JSON route has response-model/OpenAPI contract coverage.",
    ),
    ("PUT", "/api/settings"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "Settings mutation is exercised against an isolated contract database.",
    ),
    ("POST", "/api/settings/rebuild-agg"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "Settings mutation route has response-model contract coverage.",
    ),
    ("POST", "/api/settings/clear-translation-cache"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "Settings maintenance mutation is exercised against contract data.",
    ),
    ("POST", "/api/settings/llm-profiles"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "LLM profile create is covered by CRUD and redaction contract tests.",
    ),
    ("PUT", "/api/settings/llm-profiles/{profile_id}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "LLM profile update is covered by CRUD and redaction contract tests.",
    ),
    ("DELETE", "/api/settings/llm-profiles/{profile_id}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "LLM profile delete is covered by CRUD contract tests.",
    ),
    ("POST", "/api/settings/llm-profiles/{profile_id}/apply"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_settings_api_mutations.py",
        "LLM profile apply is covered by settings mutation contract tests.",
    ),
    ("POST", "/api/version-merge/groups"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_version_merge_confirm_workflow.py",
        "Release group creation is exercised against an isolated seed database.",
    ),
    ("POST", "/api/version-merge/track-groups/confirm"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_version_merge_confirm_workflow.py",
        "Track group confirmation is exercised against an isolated seed database.",
    ),
    ("POST", "/api/version-merge/album-relations/confirm"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_version_merge_confirm_workflow.py",
        "Album relation confirmation is exercised against an isolated seed database.",
    ),
    ("POST", "/api/import/streaming"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_import_api_jobs.py",
        "Import job scheduling is monkeypatched to run deterministically in contract tests.",
    ),
    ("POST", "/api/import/account"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_import_api_jobs.py",
        "Account import job scheduling is monkeypatched in contract tests.",
    ),
    ("POST", "/api/chat/sessions"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_chat_api_crud.py",
        "Chat create is covered by contract CRUD workflow.",
    ),
    ("PATCH", "/api/chat/sessions/{session_id}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_chat_api_crud.py",
        "Chat title update is covered by contract CRUD workflow.",
    ),
    ("DELETE", "/api/chat/sessions/{session_id}"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_chat_api_crud.py",
        "Chat delete is covered by contract CRUD workflow.",
    ),
    ("POST", "/api/chat/sessions/{session_id}/messages"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_chat_api_crud.py",
        "Chat message create is covered by contract CRUD workflow.",
    ),
    ("GET", "/api/spotify/auth/login"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_spotify_auth_contract.py",
        "OAuth login is covered with missing-config and PKCE state contracts.",
    ),
    ("GET", "/api/spotify/auth/callback"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_spotify_auth_contract.py",
        "OAuth callback is covered with token exchange, encryption, redirect, and invalid state.",
    ),
    ("GET", "/api/spotify/auth/playing"): OperationEvidence(
        "targeted_contract",
        "backend/tests/unit/test_spotify_auth_api.py",
        "Live playback depends on Spotify state; token refresh write boundary has unit coverage.",
    ),
    ("DELETE", "/api/spotify/auth/disconnect"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_spotify_auth_contract.py",
        "Spotify auth JSON route has response-model contract coverage.",
    ),
    ("POST", "/api/spotify/auth/sync"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_spotify_auth_contract.py",
        "Spotify auth JSON route has response-model contract coverage.",
    ),
    ("POST", "/api/spotify/auth/sync-all"): OperationEvidence(
        "targeted_contract",
        "backend/tests/contract/test_spotify_auth_contract.py",
        "Spotify full sync is covered through callback monkeypatch and response-model contracts.",
    ),
}

CONTROLLED_EXTERNAL_OR_STATEFUL_OPERATIONS: dict[tuple[str, str], OperationEvidence] = {
    ("POST", "/api/billboard/versus/track"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + legacy GET versus smoke",
        "request-body read path is not part of the default local GET smoke probe",
    ),
    ("POST", "/api/billboard/versus/album"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + legacy GET versus smoke",
        "request-body read path is not part of the default local GET smoke probe",
    ),
    ("POST", "/api/billboard/versus/artist"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + legacy GET versus smoke",
        "request-body read path is not part of the default local GET smoke probe",
    ),
    ("PUT", "/api/version-merge/groups/{group_id}/members"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + isolated version-merge contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
    ("PUT", "/api/version-merge/groups/{group_id}/primary"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + isolated version-merge contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
    ("DELETE", "/api/version-merge/groups/{group_id}"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + isolated version-merge contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
    ("POST", "/api/version-merge/album-projects/rebuild"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + album-project rebuild contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
    ("POST", "/api/version-merge/detect"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + version-merge service contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
    ("POST", "/api/version-merge/apply"): OperationEvidence(
        "controlled_external_or_stateful",
        "OpenAPI response_model + version-merge service contracts",
        "stateful local data mutation is not executed against the user's development database",
    ),
}


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="openapi_operation_audit.py",
        description="Classify every OpenAPI operation by automated evidence or explicit exclusion.",
    )
    parser.add_argument("--json-output", default=None, help="Write audit details as JSON.")
    return parser.parse_args(argv)


def _operation_rows(schema: dict) -> list[tuple[str, str, dict]]:
    rows = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method.lower() in HTTP_METHODS:
                rows.append((method.upper(), path, operation))
    return rows


def _safe_get_evidence(path: str, covered_get_paths: set[str]) -> Optional[OperationEvidence]:
    if path not in covered_get_paths:
        return None
    return OperationEvidence(
        "safe_get_smoke",
        "scripts/api_smoke_probe.py DEFAULT_SAFE_GET_CASES",
        "non-mutating GET is executed by the reusable local smoke probe",
    )


def _classify_operation(
    method: str,
    path: str,
    covered_get_paths: set[str],
) -> OperationEvidence:
    targeted = TARGETED_CONTRACT_OPERATIONS.get((method, path))
    if targeted is not None:
        return targeted

    if method == "GET":
        safe = _safe_get_evidence(path, covered_get_paths)
        if safe is not None:
            return safe
        if path in DEFAULT_EXCLUDED_GET_PATHS:
            return TARGETED_CONTRACT_OPERATIONS.get(
                (method, path),
                OperationEvidence(
                    "controlled_external_or_stateful",
                    "scripts/api_smoke_probe.py DEFAULT_EXCLUDED_GET_PATHS",
                    "GET path depends on external/browser/live state and is excluded from local smoke",
                ),
            )

    controlled = CONTROLLED_EXTERNAL_OR_STATEFUL_OPERATIONS.get((method, path))
    if controlled is not None:
        return controlled

    return OperationEvidence(
        "unaccounted",
        "",
        "operation is not covered by safe smoke, targeted contract evidence, or explicit exclusion",
    )


def build_operation_audit(app) -> OperationAudit:
    schema = app.openapi()
    get_paths = {path for path, operations in schema["paths"].items() if "get" in operations}
    covered_get_paths = _covered_openapi_get_paths(DEFAULT_SAFE_GET_CASES, get_paths)
    rows: list[OperationAuditRow] = []

    for method, path, operation in sorted(_operation_rows(schema)):
        evidence = _classify_operation(method, path, covered_get_paths)
        rows.append(
            OperationAuditRow(
                method=method,
                path=path,
                operation_id=operation.get("operationId", ""),
                tags=tuple(operation.get("tags") or ()),
                category=evidence.category,
                evidence=evidence.evidence,
                rationale=evidence.rationale,
            )
        )

    unaccounted = tuple(row for row in rows if row.category == "unaccounted")
    category_counts = dict(Counter(row.category for row in rows))
    return OperationAudit(
        operation_count=len(rows),
        operations=tuple(rows),
        unaccounted_operations=unaccounted,
        category_counts=category_counts,
    )


def assert_operation_audit(audit: OperationAudit) -> None:
    if audit.unaccounted_operations:
        lines = [
            f"- {row.method} {row.path} ({row.operation_id})"
            for row in audit.unaccounted_operations
        ]
        raise AssertionError("Unaccounted OpenAPI operations:\n" + "\n".join(lines))


def render_markdown_report(audit: OperationAudit) -> str:
    lines = [
        "# OpenAPI operation audit",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total operations | {audit.operation_count} |",
        f"| Unaccounted operations | {len(audit.unaccounted_operations)} |",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    for category, count in sorted(audit.category_counts.items()):
        lines.append(f"| {category} | {count} |")
    lines.extend(["", "| Method | Path | Category | Evidence |", "| --- | --- | --- | --- |"])
    for row in audit.operations:
        lines.append(f"| {row.method} | `{row.path}` | {row.category} | {row.evidence} |")
    return "\n".join(lines)


def audit_to_json_dict(audit: OperationAudit) -> dict:
    return {
        "operation_count": audit.operation_count,
        "category_counts": audit.category_counts,
        "unaccounted_operations": [asdict(row) for row in audit.unaccounted_operations],
        "operations": [asdict(row) for row in audit.operations],
    }


def write_json_report(audit: OperationAudit, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(audit_to_json_dict(audit), handle, ensure_ascii=False, indent=2)


def main(argv: Optional[Sequence[str]] = None) -> int:
    from backend.main import app

    args = parse_args(argv)
    audit = build_operation_audit(app)
    print(render_markdown_report(audit))
    if args.json_output:
        write_json_report(audit, Path(args.json_output))
        print(f"\nOpenAPI operation audit JSON written to {args.json_output}")
    assert_operation_audit(audit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
