from __future__ import annotations

import gzip
import json
import sqlite3
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
import pytest

from scripts import performance_contract as c
from scripts.benchmark_api import measure
from scripts.performance_catalog import endpoint_catalog
from scripts.runtime_resource_probe import series_peaks

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[3]


def test_catalog_keeps_static_consumers_and_rejects_only_unresolved_parameters():
    rows = endpoint_catalog()
    assert next(row for row in rows if row["endpoint"] == "/api/home/overview")["configured"]
    context = next(row for row in rows if row["endpoint"] == "/api/music/search/context")
    assert not context["configured"]
    configured = endpoint_catalog(entity_key="track:1")
    assert next(row for row in configured if row["endpoint"] == context["endpoint"])["configured"]
    candidates = next(row for row in rows if row["endpoint"] == "/api/artist-identities/candidates")
    assert candidates["params"]["q"]


def test_snapshot_classification_never_infers_rebuilding_from_lkg():
    assert c.snapshot_state({"snapshot": {"freshness": "current"}})["state"] == "exact"
    assert (
        c.snapshot_state({"snapshot": {"freshness": "last_known_good", "status": "warming"}})[
            "state"
        ]
        == "LKG"
    )
    assert c.snapshot_state({"status": "warming"})["state"] == "unknown"
    assert c.snapshot_state({"detail": {"error": "snapshot_unavailable"}})["state"] == "missing"
    assert c.snapshot_state(applicable=False)["state"] == "not_applicable"


def test_p95_minimum_and_independent_process_count():
    records = []
    for i in range(20):
        r = c.sample({}, "/test", process={"state": "warm", "id": "1", "evidence": "test"})
        r["success"] = True
        r["timing"]["total_ms"] = i
        records.append(r)
    assert c.summarize(records[:19])["p95_ms"] is None
    assert c.summarize(records)["p95_ms"] == 18
    records[-1]["success"] = False
    assert c.summarize(records)["failure_count"] == 1
    assert c.summarize(records)["p95_ms"] is None
    for i, r in enumerate(records[:3]):
        r["process"] = {"state": "cold", "id": str(i), "evidence": "owned"}
    assert c.summarize(records[:3])["cold_minimum_met"]
    assert c.summarize(records[:3])["p95_ms"] is None
    records[2]["process"]["id"] = "1"
    assert not c.summarize(records[:3])["cold_minimum_met"]


@pytest.fixture
def server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler callback
            raw = b'{"ok":true,"value":"' + b"x" * 300 + b'"}'
            body = gzip.compress(raw, compresslevel=1)
            status = 404 if self.path == "/missing" else 200
            self.send_response(status)
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    instance = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{instance.server_port}"
    finally:
        instance.shutdown()
        thread.join()
        instance.server_close()


def test_real_wire_bytes_and_first_failure_retained(server):
    context = c.metadata(ROOT / "backend/tests/fixtures/seed.db", "seed")
    with httpx.Client(base_url=server, trust_env=False) as client:
        failed, _ = c.request(client, "/missing", context=context)
        ok, _ = c.request(client, "/ok", context=context, attempt=2)
    assert failed["http"]["error_type"] == "HTTP404" and not failed["success"]
    assert ok["http"]["raw_bytes"] > ok["http"]["compressed_bytes"]
    assert ok["http"]["compressed_bytes"] == len(
        gzip.compress(b'{"ok":true,"value":"' + b"x" * 300 + b'"}', compresslevel=1)
    )
    report = c.report("test", context, [failed, ok])
    assert len(report["samples"]) == 2 and report["statistics"][0]["failure_count"] == 1
    schema = json.loads((ROOT / "scripts/performance-report.schema.json").read_text())
    assert set(schema["required"]) <= report.keys()
    for record in report["samples"]:
        assert set(schema["$defs"]["sample"]["required"]) <= record.keys()
    measured = measure("/ok", runs=2, base_url=server, context=context)
    assert [r["process"]["state"] for r in measured["samples"]] == ["unknown", "warm"]
    assert measured["hot_p95"] is None


def test_unexpected_http_exits_nonzero_and_writes_report(server, tmp_path):
    target = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/benchmark_api.py"),
            "--endpoint",
            "/missing",
            "--base-url",
            server,
            "--runs",
            "1",
            "--json-output",
            str(target),
        ],
        capture_output=True,
    )
    assert result.returncode == 1
    assert json.loads(target.read_text())["samples"][0]["http"]["status"] == 404


def test_database_identity_is_read_only_and_contains_no_raw_facts(tmp_path):
    copy = tmp_path / "seed.db"
    with (
        sqlite3.connect(
            f"file:{ROOT}/backend/tests/fixtures/seed.db?mode=ro&immutable=1", uri=True
        ) as src,
        sqlite3.connect(copy) as dst,
    ):
        src.backup(dst)
        dst.execute("PRAGMA journal_mode=DELETE")
    before = copy.read_bytes()
    meta = c.metadata(copy, "seed")
    assert meta["database"]["plays"] > 0 and meta["database"]["dataset"] == "seed"
    assert copy.read_bytes() == before
    assert str(copy) not in json.dumps(meta)


def test_resource_peak_is_from_whole_window():
    series = [
        {
            "services": [
                {
                    "label": "backend",
                    "rss_mb": rss,
                    "cpu_percent": cpu,
                    "read_delta": 10,
                    "write_delta": 3,
                }
            ]
        }
        for rss, cpu in [(2, 1), (80, 45), (3, 2)]
    ]
    assert series_peaks(series)["backend"] == {
        "peak_rss_mb": 80,
        "peak_cpu_percent": 45,
        "read_bytes": 30,
        "write_bytes": 9,
    }


def test_resource_command_retains_phase_and_failure(tmp_path):
    label = tmp_path / "phase"
    label.write_text("cold-operation")
    output = tmp_path / "resources.json"
    ready = tmp_path / "ready"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/runtime_resource_probe.py"),
            "--phase-file",
            str(label),
            "--json-output",
            str(output),
            "--interval",
            ".01",
            "--watch-file",
            str(label),
            "--ready-file",
            str(ready),
            "--command",
            sys.executable,
            "-c",
            f"from pathlib import Path; assert Path({str(ready)!r}).exists(); Path({str(label)!r}).write_text('done'); raise SystemExit(7)",
        ],
        capture_output=True,
    )
    assert result.returncode == 1
    report = json.loads(output.read_text())
    assert len(report["time_series"]) >= 2
    assert report["time_series"][0]["phase"] == "cold-operation"
    assert report["time_series"][-1]["phase"] == "done"
    assert report["operation_exit"] == 7
    assert "probe" in report["peaks"]


def test_p95_never_pools_different_snapshot_states():
    records = []
    for i in range(20):
        r = c.sample(
            {}, "/api/home/overview", process={"state": "warm", "id": "1", "evidence": "test"}
        )
        r["success"] = True
        r["timing"]["total_ms"] = i
        r["snapshot"]["state"] = "exact" if i < 10 else "LKG"
        records.append(r)
    assert c.summarize(records)["p95_ms"] is None
    assert all(group["p95_ms"] is None for group in c.grouped_statistics(records))


def test_cold_failed_attempts_are_counted_without_becoming_successes():
    records = []
    for i in range(3):
        r = c.sample(
            {}, "/api/home/overview", process={"state": "cold", "id": str(i), "evidence": "owned"}
        )
        r["http"]["status"] = 503
        r["timing"]["total_ms"] = 10
        records.append(r)
    summary = c.summarize(records)
    assert summary["independent_cold_processes"] == 3
    assert summary["success_count"] == 0 and summary["failure_count"] == 3
    assert summary["failed_observed_values_ms"] == [10, 10, 10]
    assert summary["p95_ms"] is None


def test_http_200_unavailable_is_not_a_performance_success():
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, stream=httpx.ByteStream(b'{"snapshot_status":"unavailable","total":0}')
        )
    )
    with httpx.Client(transport=transport, base_url="http://localhost") as client:
        record, _ = c.request(client, "/api/music/search", context={})
    assert not record["success"]
    assert record["http"]["error_type"] == "SnapshotUnavailable"
    assert record["snapshot"]["state"] == "missing"
