"""Provider-neutral evidence envelopes for Agent tool observations.

The runtime keeps the original tool payload for deterministic builders, while
this module exposes a compact, versioned contract shared by chat, reports and
offline evaluation.  It deliberately contains no executable capability.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Literal

from pydantic import BaseModel, Field

TOOL_EVIDENCE_SCHEMA_VERSION = "tool_evidence_v2"
_ISO_DATE_RE = re.compile(r"20\d{2}-\d{2}-\d{2}")


class ToolEvidenceFact(BaseModel):
    fact_id: str
    subject: str | None = None
    predicate: str
    value: Any
    unit: str | None = None
    rank: int | None = None
    time_range: str = ""
    source_field: str = ""
    comparability: str | None = None


class ToolEvidenceTiming(BaseModel):
    elapsed_ms: int = 0
    result_size_bytes: int = 0
    cache_hit: bool = False
    duplicate: bool = False


class ToolEvidenceEnvelope(BaseModel):
    schema_version: str = TOOL_EVIDENCE_SCHEMA_VERSION
    status: Literal["ok", "empty", "partial", "error"]
    tool_name: str
    tool_call_id: str
    normalized_params: dict[str, Any] = Field(default_factory=dict)
    requested_range: dict[str, str] = Field(default_factory=dict)
    effective_range: dict[str, str] = Field(default_factory=dict)
    data_cutoff: str | None = None
    source_revision: str | None = None
    constraint_fingerprint: str = ""
    facts: list[ToolEvidenceFact] = Field(default_factory=list)
    completeness: Literal["complete", "partial", "empty", "error"]
    limitations: list[str] = Field(default_factory=list)
    source_range: str = ""
    timing: ToolEvidenceTiming = Field(default_factory=ToolEvidenceTiming)


def constraint_fingerprint(payload: dict[str, Any] | None) -> str:
    """Return a stable public fingerprint without persisting raw user text."""

    normalized = _json_safe(payload or {})
    rendered = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:20]


def build_tool_evidence_envelopes(
    tool_results: list[dict[str, Any]],
    *,
    fact_catalog: list[dict[str, Any]] | None = None,
    constraint_state: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Project legacy tool results into a compact, versioned evidence contract."""

    facts_by_tool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for fact in fact_catalog or []:
        if isinstance(fact, dict):
            facts_by_tool[str(fact.get("tool_name") or "")].append(fact)

    fingerprint = constraint_fingerprint(constraint_state)
    envelopes: list[dict[str, Any]] = []
    for index, result in enumerate(tool_results):
        if not isinstance(result, dict):
            continue
        tool_name = str(result.get("tool_name") or "")
        if not tool_name:
            continue
        status = _status(result)
        source_range = str(result.get("source_range") or "")
        params = result.get("params") if isinstance(result.get("params"), dict) else {}
        facts = [
            _fact_from_catalog(item)
            for item in facts_by_tool.get(tool_name, [])[:20]
            if item.get("value") is not None
        ]
        dates = list(dict.fromkeys(_ISO_DATE_RE.findall(source_range)))
        requested_range = _range_from_params(params)
        effective_range = _range_from_source(dates)
        limitations = _limitations(result, status)
        envelope = ToolEvidenceEnvelope(
            status=status,
            tool_name=tool_name,
            tool_call_id=str(result.get("call_id") or f"legacy:{index}:{tool_name}"),
            normalized_params=_json_safe(params),
            requested_range=requested_range,
            effective_range=effective_range,
            data_cutoff=dates[-1] if dates else None,
            source_revision=(
                str(result["source_revision"]) if result.get("source_revision") else None
            ),
            constraint_fingerprint=fingerprint,
            facts=facts,
            completeness=_completeness(status),
            limitations=limitations,
            source_range=source_range,
            timing=ToolEvidenceTiming(
                elapsed_ms=max(0, int(result.get("elapsed_ms") or 0)),
                result_size_bytes=max(0, int(result.get("result_size_bytes") or 0)),
                cache_hit=bool(result.get("cache_hit")),
                duplicate=bool(result.get("duplicate")),
            ),
        )
        envelopes.append(envelope.model_dump(exclude_none=True))
    return envelopes


def _status(result: dict[str, Any]) -> Literal["ok", "empty", "partial", "error"]:
    value = str(result.get("status") or "ok")
    if value == "done":
        return "ok"
    if value in {"ok", "empty", "partial", "error"}:
        return value  # type: ignore[return-value]
    return "error" if result.get("error") else "ok"


def _completeness(
    status: Literal["ok", "empty", "partial", "error"],
) -> Literal["complete", "partial", "empty", "error"]:
    return "complete" if status == "ok" else status


def _range_from_params(params: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for source, target in (
        ("start_date", "start_date"),
        ("date_from", "start_date"),
        ("end_date", "end_date"),
        ("date_to", "end_date"),
    ):
        if source in params and params[source] is not None and target not in result:
            result[target] = str(params[source])
    if params.get("year") is not None:
        year = int(params["year"])
        result.setdefault("start_date", f"{year:04d}-01-01")
        result.setdefault("end_date", f"{year:04d}-12-31")
    return result


def _range_from_source(dates: list[str]) -> dict[str, str]:
    if not dates:
        return {}
    if len(dates) == 1:
        return {"end_date": dates[0]}
    return {"start_date": dates[0], "end_date": dates[-1]}


def _fact_from_catalog(fact: dict[str, Any]) -> ToolEvidenceFact:
    rank = fact.get("rank")
    if rank is None and str(fact.get("metric_name") or "").endswith("rank"):
        rank = fact.get("value")
    return ToolEvidenceFact(
        fact_id=str(fact.get("fact_id") or ""),
        subject=str(fact["entity_name"]) if fact.get("entity_name") else None,
        predicate=str(fact.get("metric_name") or fact.get("label") or "fact"),
        value=fact.get("value"),
        unit=str(fact["unit"]) if fact.get("unit") else None,
        rank=int(rank) if isinstance(rank, int) and not isinstance(rank, bool) else None,
        time_range=str(fact.get("source_range") or ""),
        source_field=str(fact.get("evidence_ref") or ""),
        comparability=(str(fact["comparability"]) if fact.get("comparability") else None),
    )


def _limitations(result: dict[str, Any], status: str) -> list[str]:
    limitations: list[str] = []
    raw = result.get("limitations")
    if isinstance(raw, list):
        limitations.extend(str(item) for item in raw if str(item).strip())
    if status == "partial":
        limitations.append("tool_result_partial")
    elif status == "empty":
        limitations.append("tool_result_empty")
    elif status == "error":
        limitations.append(str(result.get("error") or "tool_result_error"))
    return list(dict.fromkeys(limitations))


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
