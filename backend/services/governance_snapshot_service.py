"""Explicit governance maintenance and side-effect-free result reads."""

from __future__ import annotations

import fcntl
import json
import logging
from datetime import datetime, timezone

from backend.core.access_surface import public_readonly_db_guard_active, snapshot_unavailable
from backend.core.cache import singleflight
from backend.core.db import get_db
from backend.core.job_queue import Job, get_job_queue, queue_targets_connection
from backend.domains.metadata import governance_store as store
from backend.domains.metadata.governance_revision import FAMILIES, revision_vector
from backend.domains.settings.repository import SETTINGS_DEFAULTS, SettingsRepository
from backend.services.analysis_snapshot_revision import database_identity
from backend.services.analysis_snapshot_store import digest

logger = logging.getLogger(__name__)
JOB_TYPE = "governance_snapshot_rebuild"
BUILDER_VERSION = "governance_shared_duration_v1"
PUBLICATION_VERSION = "governance_result_v1"
RULE_VERSION = "governance_health_coverage_v1"
RESULT_FAMILIES = tuple(f for f in FAMILIES if f != "primary_artist_ms") + ("import_health",)
FILTER_KEYS = (
    "min_ms",
    "music_only",
    "merge_enabled",
    "dynamic_threshold",
    "max_merge_gap_minutes",
)


def parameters(conn, filters=None):
    settings = SettingsRepository(conn).load_all()
    supplied = (
        vars(filters) if filters is not None and not isinstance(filters, dict) else filters or {}
    )
    values = {
        k: supplied.get(k, settings.get(k, SETTINGS_DEFAULTS.get(k, True))) for k in FILTER_KEYS
    }
    for k in ("min_ms", "max_merge_gap_minutes"):
        values[k] = int(values[k])
    for k in ("music_only", "merge_enabled", "dynamic_threshold"):
        values[k] = str(values[k]).lower() in ("true", "1", "yes", "on")
    if values["min_ms"] < 0 or not 1 <= values["max_merge_gap_minutes"] <= 240:
        raise ValueError("Invalid governance filters")
    return values


def request_key(conn, family, params):
    return digest(
        {
            "namespace": database_identity(conn),
            "family": family,
            "filters": {} if family == "import_health" else params,
            "rules": RULE_VERSION,
            "builder": BUILDER_VERSION,
            "publication": PUBLICATION_VERSION,
        }
    )


def target(conn, family, params):
    vector = revision_vector(conn, family)
    return (family, request_key(conn, family, params), digest(vector)), vector


def unavailable(family, revision=None, failed=False):
    error = snapshot_unavailable("governance", revision)
    error.detail.update(
        family=family,
        build_status="failed" if failed else "unavailable",
        message=("本次治理检查构建失败。" if failed else "治理检查尚未发布。")
        + "请在本机运行 scripts/rebuild_governance.py --db <数据库路径> --install-revisions，然后重新读取。",
    )
    return error


def read(conn, family, filters=None):
    revision = None
    try:
        if not store.path().is_file():
            raise unavailable(family)
        params = parameters(conn, filters)
        (family, key, revision), _ = target(conn, family, params)
        loaded = store.read(family, key)
        if loaded is None:
            raise unavailable(family, revision, store.failed_revision(family, key) == revision)
        saved, row = loaded
        exact = row["revision"] == revision and not row["fallback"]
        failed = row["failed_revision"] == revision
        payload = saved["result"]
        if family == "import_health":
            payload = live_import_health(conn, payload)
        return {
            **payload,
            "checked_at": saved["checked_at"],
            "snapshot": {
                **saved["metadata"],
                "status": "ready" if exact else "warming",
                "freshness": "current" if exact else "last_known_good",
                "source_revision": row["revision"],
                "target_revision": revision,
                "checked_revision": row["revision"],
                "checked_at": saved["checked_at"],
                "build_status": "failed" if failed else ("ready" if exact else "pending"),
            },
        }
    except (OSError, ValueError, store.sqlite3.Error):
        logger.exception("Governance publication unavailable")
        raise unavailable(family, revision) from None


def live_import_health(conn, payload):
    from backend.domains.metadata.import_health import (
        _setting_bool,
        _state_snapshot,
        format_import_health,
    )
    from backend.domains.playback.l3_album_attribution import (
        L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
        get_l3_album_attribution_state,
    )

    derived = dict(payload["derived"])
    derived["rebuild_pending"] = _setting_bool(conn, "rebuild_pending")
    derived["artist_identity"] = _state_snapshot(conn, "artist_identity_state")
    derived["track_credits"] = _state_snapshot(conn, "track_credit_state")
    state = get_l3_album_attribution_state(conn)
    reconciled = int(state.get("scanned_count", 0)) == sum(
        int(state.get(k, 0))
        for k in ("attributed_count", "excluded_count", "conflict_count", "uncovered_count")
    )
    derived["l3_album_attribution"] = {
        **state,
        "expected_policy_version": L3_ALBUM_ATTRIBUTION_POLICY_VERSION,
        "coverage_reconciled": reconciled,
        "healthy": bool(
            state["status"] == "ready"
            and state["policy_version"] == L3_ALBUM_ATTRIBUTION_POLICY_VERSION
            and reconciled
            and not int(state["conflict_count"])
            and not int(state["uncovered_count"])
        ),
    }
    derived["stale_revision_count"] = sum(
        s["current_revision"] != s["active_aggregate_revision"] or s["rebuild_status"] != "ready"
        for s in (derived["artist_identity"], derived["track_credits"])
    )
    result = format_import_health(
        payload["database"], payload["relationships"], payload["metadata"], derived
    )
    # Runtime errors are read now, never frozen into a previously green check.
    errors = [
        s["last_error"]
        for s in (derived["artist_identity"], derived["track_credits"])
        if s["last_error"]
    ]
    from pathlib import Path

    from backend.core.import_account_data import ACCOUNT_DATA_DIR
    from backend.core.import_data import DATA_DIR

    runtime = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "streaming_directory_exists": Path(DATA_DIR).is_dir(),
        "account_directory_exists": Path(ACCOUNT_DATA_DIR).is_dir(),
    }
    from backend.domains.metadata.import_health import _table_exists

    if _table_exists(conn, "playback_import_runs"):
        row = conn.execute(
            "SELECT run_id,status,error_code FROM playback_import_runs ORDER BY started_at DESC,rowid DESC LIMIT 1"
        ).fetchone()
        if row:
            runtime["persisted_import"] = dict(row)
            if row["status"] in {"failed", "error", "recovery_blocked", "blocked"}:
                errors.append(row["error_code"] or "导入维护失败")
    if state.get("last_error"):
        errors.append(state["last_error"])
    if errors:
        result["status"] = "failed"
        result["summary"] = {
            **result["summary"],
            "safe_to_use": False,
            "headline": "当前治理任务失败，请检查任务错误",
        }
    result["runtime"] = runtime
    return result


def _pending(conn, params, families):
    targets = []
    for family in families:
        identity, vector = target(conn, family, params)
        loaded = store.read(*identity[:2])
        if loaded is None or loaded[1]["revision"] != identity[2] or loaded[1]["fallback"]:
            targets.append((identity, vector))
    return targets


def ensure(conn, filters=None, families=None):
    if public_readonly_db_guard_active():
        raise PermissionError("Public requests cannot build governance facts")
    if conn.in_transaction:
        raise ValueError("Commit source writes before governance maintenance")
    families = tuple(families or RESULT_FAMILIES)
    if not set(families).issubset(RESULT_FAMILIES):
        raise ValueError("Unknown governance family")
    lock_path = store.path().with_suffix(".build.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        # Keep all reads from an injected connection inside the build lock;
        # sqlite3 connections are not safe for overlapping execute calls even
        # when ``check_same_thread`` is disabled.
        params = parameters(conn, filters)
        return _ensure_once(
            digest(database_identity(conn)), json.dumps(params, sort_keys=True), families
        )


@singleflight
def _ensure_once(namespace, params_json, families):
    conn = get_db(readonly=True)
    try:
        if digest(database_identity(conn)) != namespace:
            raise ValueError("Governance source namespace changed")
        params = json.loads(params_json)
        pending = _pending(conn, params, families)
        if not pending:
            return {"published": [], "primary_artist_ms_builds": 0}
        from backend.domains.metadata.artist_genres import (
            AXIS_ORDER,
            compute_genre_axis_gaps,
            compute_genre_coverage,
            compute_genre_taxonomy_audit,
        )
        from backend.domains.metadata.artist_languages import compute_artist_language_distribution
        from backend.domains.metadata.governance_facts import artist_hours, build_facts
        from backend.domains.metadata.import_health import build_import_health_report

        results = []
        fact_builds = 0
        facts = None
        if any(t[0][0] != "import_health" for t in pending):
            fact_target, fact_vector = target(conn, "primary_artist_ms", params)
            loaded = store.read(*fact_target[:2])
            if loaded and loaded[1]["revision"] == fact_target[2] and not loaded[1]["fallback"]:
                facts = loaded[0]["result"]
            else:
                pending.insert(0, (fact_target, fact_vector))
        settings = parameters(conn)
        try:
            for identity, vector in pending:
                family, key, revision = identity
                if family == "primary_artist_ms":
                    facts = build_facts(conn, params)
                    fact_builds += 1
                    payload = facts
                elif family == "import_health":
                    payload = build_import_health_report(conn)
                elif family == "language_coverage":
                    payload = compute_artist_language_distribution(
                        conn,
                        {int(k): v for k, v in facts["artist_ms"].items()},
                        excluded_ms=facts["excluded_ms"],
                    )
                else:
                    hours, excluded = artist_hours(conn, facts)
                    if family == "genre_coverage":
                        payload = compute_genre_coverage(conn, hours)
                        payload.update(
                            artist_count=len(hours),
                            total_hours=round(sum(hours.values()), 1),
                            excluded_unattributed_hours=excluded,
                        )
                    elif family == "genre_taxonomy":
                        payload = compute_genre_taxonomy_audit(conn, hours)
                    else:
                        payload = {
                            "axes": {
                                a: compute_genre_axis_gaps(conn, hours, axis=a) for a in AXIS_ORDER
                            }
                        }
                saved = {
                    "result": payload,
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "metadata": {
                        "family": family,
                        "filter_fingerprint": digest({} if family == "import_health" else params),
                        "source_revision_vector": vector,
                        "rule_version": RULE_VERSION,
                        "builder_version": BUILDER_VERSION,
                        "publication_version": PUBLICATION_VERSION,
                    },
                }
                results.append((*identity, saved))

            def fence():
                if (
                    any(target(conn, t[0][0], params)[0] != t[0] for t in pending)
                    or parameters(conn) != settings
                ):
                    raise ValueError("Governance source/config changed during build")

            store.publish(results, fence)
            return {"published": [r[0] for r in results], "primary_artist_ms_builds": fact_builds}
        except Exception:
            store.mark_failed([t[0] for t in pending])
            raise
    finally:
        conn.close()


def enqueue_defaults(reason, *, queue=None):
    if public_readonly_db_guard_active():
        return []
    queue = queue or get_job_queue()
    conn = get_db(readonly=True)
    try:
        if not queue_targets_connection(queue, conn):
            return []
        params = parameters(conn)
        if not _pending(conn, params, RESULT_FAMILIES):
            return []
        key = digest({"namespace": database_identity(conn), "filters": params})
        job = queue.enqueue_if_not_pending(Job.create(JOB_TYPE, "governance", key, reason=reason))
        return [job] if job else []
    finally:
        conn.close()


def handle_rebuild(job):
    conn = get_db(readonly=True)
    try:
        return ensure(conn)
    finally:
        conn.close()
