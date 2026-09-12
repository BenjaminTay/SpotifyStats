from backend.domains.ai_agent.tool_evidence import (
    TOOL_EVIDENCE_SCHEMA_VERSION,
    build_tool_evidence_envelopes,
    constraint_fingerprint,
)


def test_constraint_fingerprint_is_stable_and_order_independent():
    left = constraint_fingerprint({"metrics": ["plays"], "year": 2026})
    right = constraint_fingerprint({"year": 2026, "metrics": ["plays"]})

    assert left == right
    assert len(left) == 20


def test_build_tool_evidence_envelope_projects_ranges_facts_and_timing():
    envelopes = build_tool_evidence_envelopes(
        [
            {
                "call_id": "call-1",
                "tool_name": "analysis_charts",
                "status": "done",
                "params": {"year": 2025},
                "source_range": "2025-01-01..2025-12-31",
                "elapsed_ms": 321,
                "result_size_bytes": 2048,
                "cache_hit": True,
                "data": {"top_artists": []},
            }
        ],
        fact_catalog=[
            {
                "fact_id": "fact-1",
                "tool_name": "analysis_charts",
                "evidence_ref": "card-1",
                "metric_name": "rank",
                "label": "排名",
                "value": 1,
                "entity_name": "Olivia Rodrigo",
                "source_range": "2025-01-01..2025-12-31",
            }
        ],
        constraint_state={"year": 2025},
    )

    assert len(envelopes) == 1
    envelope = envelopes[0]
    assert envelope["schema_version"] == TOOL_EVIDENCE_SCHEMA_VERSION
    assert envelope["status"] == "ok"
    assert envelope["completeness"] == "complete"
    assert envelope["requested_range"] == {
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
    }
    assert envelope["effective_range"] == {
        "start_date": "2025-01-01",
        "end_date": "2025-12-31",
    }
    assert envelope["data_cutoff"] == "2025-12-31"
    assert envelope["facts"][0]["subject"] == "Olivia Rodrigo"
    assert envelope["facts"][0]["rank"] == 1
    assert envelope["timing"] == {
        "elapsed_ms": 321,
        "result_size_bytes": 2048,
        "cache_hit": True,
        "duplicate": False,
    }


def test_build_tool_evidence_envelope_marks_partial_and_error_limitations():
    envelopes = build_tool_evidence_envelopes(
        [
            {"tool_name": "analysis_stats", "status": "partial", "data": {}},
            {
                "tool_name": "community_feed_search",
                "status": "error",
                "error": "timeout",
                "data": {},
            },
        ]
    )

    assert envelopes[0]["completeness"] == "partial"
    assert envelopes[0]["limitations"] == ["tool_result_partial"]
    assert envelopes[1]["completeness"] == "error"
    assert envelopes[1]["limitations"] == ["timeout"]
