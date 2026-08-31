from backend.domains.agent_runtime.context_compaction import compact_session_events


def test_compaction_retains_facts_range_revision_and_evidence_reference() -> None:
    events = [
        {
            "event_id": 1,
            "turn_id": "turn-1",
            "event_type": "model_message",
            "payload": {"message": {"role": "user", "content": "比较两个艺人"}},
        },
        {
            "event_id": 2,
            "turn_id": "turn-1",
            "event_type": "tool_result",
            "payload": {
                "call_id": "call-1",
                "outcome": {
                    "status": "ok",
                    "tool_name": "compare_entities",
                    "result_summary": "A 比 B 多播放 12 次",
                    "source_range": "2026-01-01 至 2026-08-31",
                    "data": {"cache_revision": 42, "large_rows": list(range(100))},
                },
            },
        },
        {
            "event_id": 3,
            "turn_id": "turn-1",
            "event_type": "model_message",
            "payload": {"message": {"role": "assistant", "content": "A 更高。"}},
        },
    ]

    compacted = compact_session_events(events)

    assert compacted["facts"] == [
        {
            "tool_name": "compare_entities",
            "status": "ok",
            "summary": "A 比 B 多播放 12 次",
            "source_range": "2026-01-01 至 2026-08-31",
            "evidence_ref": {
                "turn_id": "turn-1",
                "event_id": 2,
                "call_id": "call-1",
            },
        }
    ]
    assert compacted["time_ranges"] == ["2026-01-01 至 2026-08-31"]
    assert compacted["revisions"] == {"cache_revision": 42}
    assert [item["role"] for item in compacted["recent_messages"]] == [
        "user",
        "assistant",
    ]


def test_compaction_is_bounded_and_drops_raw_tool_data() -> None:
    events = []
    for index in range(20):
        events.append(
            {
                "event_id": index + 1,
                "turn_id": f"turn-{index // 2}",
                "event_type": "tool_result",
                "payload": {
                    "call_id": f"call-{index}",
                    "outcome": {
                        "status": "ok",
                        "tool_name": "statistics",
                        "result_summary": "事实" * 80,
                        "source_range": "lifetime",
                        "data": {"rows": ["secret-sized-payload"] * 1000},
                    },
                },
            }
        )

    compacted = compact_session_events(events, max_facts=5, max_chars=1600)

    assert len(compacted["facts"]) <= 5
    assert "secret-sized-payload" not in str(compacted)
    assert len(str(compacted)) < 1800
