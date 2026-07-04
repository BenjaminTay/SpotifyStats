"""AI-assisted artist genre backfill task service."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from typing import Any

from backend.core.db import get_db
from backend.domains.ai_tasks.repository import AiTaskRepository
from backend.domains.metadata.artist_genres import (
    normalize_genres,
    resolve_artist_genres_map,
    upsert_genre_source,
)
from backend.providers.lastfm.client import LastFMProvider
from backend.providers.musicbrainz.client import MusicBrainzProvider
from backend.providers.wikidata.client import WikidataProvider
from backend.services.ai_insights_service import _llm_chat

TERMINAL_STATUSES = {"done", "error", "cancelled"}
BACKFILL_STAGE_PROGRESS = {
    "selecting_artists": 0.15,
    "fetching_external_data": 0.4,
    "calling_llm": 0.65,
    "saving_suggestions": 0.85,
}
EXTERNAL_APPROVAL_MIN_CONFIDENCE = 0.8
_PROVIDER_RATE_LIMIT_LOCK = threading.Lock()
_PROVIDER_LAST_CALL_AT: dict[str, float] = {}

GENRE_LLM_SYSTEM = """你是一个保守的音乐元数据审核助手。根据外部证据为艺人建议 broad artist genres。
只输出 JSON，不要添加解释。若证据不足，返回空 genres。"""


def select_missing_genre_artists(
    conn: sqlite3.Connection,
    *,
    limit: int = 50,
    min_hours: float = 1.0,
) -> list[dict[str, Any]]:
    rows = _load_artist_play_hours(conn, min_hours=min_hours)
    resolved = resolve_artist_genres_map(conn, [row["artist_name"] for row in rows])
    selected = []
    for row in rows:
        artist_name = row["artist_name"]
        if resolved.get(artist_name) and resolved[artist_name].genres:
            continue
        selected.append({"artist_name": artist_name, "hours": round(float(row["hours"]), 1)})
        if len(selected) >= limit:
            break
    return selected


def gather_genre_evidence(artist_name: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "lastfm": [],
        "musicbrainz": [],
        "wikidata": [],
        "wikipedia_summary": "",
    }
    providers = (
        ("lastfm", LastFMProvider()),
        ("musicbrainz", MusicBrainzProvider()),
        ("wikidata", WikidataProvider()),
    )
    for key, provider in providers:
        try:
            _respect_provider_rate_limit(provider)
            evidence[key] = provider.get_artist_genres(artist_name)
        except Exception:
            evidence[key] = []
    return evidence


def _respect_provider_rate_limit(provider: Any) -> None:
    config = getattr(provider, "config", None)
    provider_name = str(getattr(config, "name", "") or provider.__class__.__name__)
    try:
        rate_limit_rps = float(getattr(config, "rate_limit_rps", 0.0) or 0.0)
    except (TypeError, ValueError):
        rate_limit_rps = 0.0
    if rate_limit_rps <= 0:
        return

    min_interval = 1.0 / rate_limit_rps
    with _PROVIDER_RATE_LIMIT_LOCK:
        now = time.monotonic()
        last_call_at = _PROVIDER_LAST_CALL_AT.get(provider_name)
        if last_call_at is not None:
            wait_seconds = min_interval - (now - last_call_at)
            if wait_seconds > 0:
                time.sleep(wait_seconds)
                now = time.monotonic()
        _PROVIDER_LAST_CALL_AT[provider_name] = now


def parse_llm_genre_suggestion(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    payload = _parse_json_payload(raw)
    if not isinstance(payload, dict):
        return None
    genres = normalize_genres(
        payload.get("genres") if isinstance(payload.get("genres"), list) else []
    )
    if not genres:
        return None
    try:
        confidence = float(payload.get("confidence", 0))
    except (TypeError, ValueError):
        return None
    if confidence < 0.6:
        return None
    evidence_summary = str(payload.get("evidence_summary") or "").strip()
    if not evidence_summary:
        return None
    primary = str(payload.get("primary_genre") or genres[0]).strip().lower() or genres[0]
    if primary not in genres:
        primary = genres[0]
    return {
        "genres": genres,
        "primary_genre": primary,
        "language": _optional_text(payload.get("language")),
        "region": _optional_text(payload.get("region")),
        "confidence": round(confidence, 3),
        "evidence_summary": evidence_summary,
    }


def run_artist_genre_backfill_task(task_id: str, request: dict[str, Any]) -> None:
    conn = get_db(readonly=False)
    try:
        repo = AiTaskRepository(conn)
        limit = int(request.get("limit", 50))
        min_hours = float(request.get("min_hours", 1.0))
        include_ai = bool(request.get("include_ai", True))
        approve_external = bool(request.get("approve_high_confidence_external", True))

        if not _set_stage(
            repo,
            task_id=task_id,
            stage="selecting_artists",
            message="正在选择缺失流派的高播放艺人",
        ):
            return
        selected = select_missing_genre_artists(conn, limit=limit, min_hours=min_hours)
        skipped_existing = _count_existing_genre_artists(conn, min_hours=min_hours)

        if not _set_stage(
            repo,
            task_id=task_id,
            stage="fetching_external_data",
            message="正在收集外部流派证据",
        ):
            return
        evidence_by_artist = {}
        for artist in selected:
            artist_name = artist["artist_name"]
            if not _task_is_active(repo, task_id):
                return
            evidence = gather_genre_evidence(artist_name)
            if not _task_is_active(repo, task_id):
                return
            evidence_by_artist[artist_name] = evidence
            repo.add_tool_call_if_not_terminal(
                task_id=task_id,
                tool_name="artist_genre_external_evidence",
                status="done",
                params_summary=json.dumps({"artist_name": artist_name}, ensure_ascii=False),
                result_summary=_evidence_summary(evidence),
            )

        llm_suggestions: dict[str, dict[str, Any]] = {}
        if include_ai and selected:
            if not _set_stage(
                repo,
                task_id=task_id,
                stage="calling_llm",
                message="正在调用 LLM 生成待审核流派建议",
            ):
                return
            for artist in selected:
                artist_name = artist["artist_name"]
                if not _task_is_active(repo, task_id):
                    return
                raw = _llm_chat(
                    GENRE_LLM_SYSTEM,
                    _llm_user_payload(artist_name, evidence_by_artist[artist_name]),
                    temperature=0.1,
                )
                parsed = parse_llm_genre_suggestion(raw)
                if not _task_is_active(repo, task_id):
                    return
                status = "done" if parsed else "skipped"
                repo.add_tool_call_if_not_terminal(
                    task_id=task_id,
                    tool_name="artist_genre_llm_suggestion",
                    status=status,
                    params_summary=json.dumps({"artist_name": artist_name}, ensure_ascii=False),
                    result_summary=(parsed or {}).get("evidence_summary", "No valid suggestion"),
                )
                if parsed:
                    llm_suggestions[artist_name] = parsed

        if not _set_stage(
            repo,
            task_id=task_id,
            stage="saving_suggestions",
            message="正在保存艺人流派建议",
        ):
            return

        selected_hours = {row["artist_name"]: float(row["hours"]) for row in selected}
        source_writes = []
        for artist in selected:
            artist_name = artist["artist_name"]
            if not _task_is_active(repo, task_id):
                return
            evidence = evidence_by_artist.get(artist_name, {})
            if approve_external:
                consensus = _external_consensus_suggestion(artist_name, evidence)
                if consensus:
                    source_writes.append(
                        {
                            "artist_name": artist_name,
                            "source": "external_consensus",
                            "source_key": f"external:{artist_name}",
                            "suggestion": consensus,
                            "evidence_url": consensus.get("evidence_url"),
                            "status": "approved",
                            "review": None,
                        }
                    )
            if artist_name in llm_suggestions:
                source_writes.append(
                    {
                        "artist_name": artist_name,
                        "source": "llm",
                        "source_key": f"llm:{artist_name}",
                        "suggestion": llm_suggestions[artist_name],
                        "evidence_url": None,
                        "status": "suggested",
                        "review": {
                            "artist_name": artist_name,
                            "play_hours": selected_hours.get(artist_name, 0.0),
                            "reason": "llm_artist_genre_suggestion",
                        },
                    }
                )
        approved_count = sum(1 for item in source_writes if item["status"] == "approved")
        suggested_count = sum(1 for item in source_writes if item["status"] == "suggested")

        result = {
            "selected_count": len(selected),
            "suggested_count": suggested_count,
            "approved_count": approved_count,
            "skipped_existing_count": skipped_existing,
            "artists": selected,
        }

        def write_suggestions(active_conn: sqlite3.Connection) -> None:
            for item in source_writes:
                source_id = _save_genre_source(
                    active_conn,
                    artist_name=item["artist_name"],
                    source=item["source"],
                    source_key=item["source_key"],
                    suggestion=item["suggestion"],
                    evidence_url=item["evidence_url"],
                    status=item["status"],
                )
                if item["review"] is not None:
                    _enqueue_review(
                        active_conn,
                        suggested_source_id=source_id,
                        **item["review"],
                    )

        updated = repo.update_run_if_not_terminal_with_write(
            task_id=task_id,
            status="done",
            stage="done",
            progress_pct=1.0,
            message="艺人流派补全建议已生成",
            result=result,
            write=write_suggestions,
        )
        if not updated:
            return
        repo.add_event(
            task_id=task_id,
            event_type="result_ready",
            stage="done",
            message="艺人流派补全建议已生成",
            payload=result,
        )
    except Exception as exc:
        conn.rollback()
        _mark_error(
            AiTaskRepository(conn), task_id=task_id, message=str(exc) or exc.__class__.__name__
        )
    finally:
        conn.close()


def _load_artist_play_hours(conn: sqlite3.Connection, *, min_hours: float) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT a.artist_name AS artist_name,
                  SUM(p.ms_played) / 3600000.0 AS hours
           FROM plays p
           JOIN tracks t ON p.track_id = t.track_id
           JOIN artists a ON t.artist_id = a.artist_id
           WHERE p.track_id IS NOT NULL
             AND a.artist_name IS NOT NULL
             AND a.artist_name != ''
             AND COALESCE(p.content_type, 'audio') = 'audio'
           GROUP BY a.artist_name
           HAVING hours >= ?
           ORDER BY hours DESC""",
        (float(min_hours),),
    ).fetchall()


def _count_existing_genre_artists(conn: sqlite3.Connection, *, min_hours: float) -> int:
    rows = _load_artist_play_hours(conn, min_hours=min_hours)
    resolved = resolve_artist_genres_map(conn, [row["artist_name"] for row in rows])
    return sum(
        1
        for row in rows
        if resolved.get(row["artist_name"]) and resolved[row["artist_name"]].genres
    )


def _parse_json_payload(raw: str) -> Any:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*\n?(.+?)\n?```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _evidence_records(evidence: dict[str, Any]) -> list[tuple[str, dict[str, Any], list[str]]]:
    records = []
    for source in ("musicbrainz", "lastfm", "wikidata"):
        source_rows = evidence.get(source)
        if not isinstance(source_rows, list):
            continue
        for row in source_rows:
            if not isinstance(row, dict):
                continue
            genres = normalize_genres(
                row.get("normalized_genres")
                if isinstance(row.get("normalized_genres"), list)
                else []
            )
            if genres:
                records.append((source, row, genres))
    return records


def _external_consensus_suggestion(
    artist_name: str,
    evidence: dict[str, Any],
) -> dict[str, Any] | None:
    records = _evidence_records(evidence)
    genre_sources: dict[str, set[str]] = {}
    genre_confidences: dict[str, list[float]] = {}
    genre_order = []
    summaries = []
    evidence_url = None
    for source, row, genres in records:
        confidence = row.get("confidence")
        if not isinstance(confidence, (int, float)):
            continue
        confidence = float(confidence)
        if confidence < EXTERNAL_APPROVAL_MIN_CONFIDENCE:
            continue
        if row.get("evidence_summary"):
            summaries.append(str(row["evidence_summary"]))
        if evidence_url is None and row.get("evidence_url"):
            evidence_url = str(row["evidence_url"])
        for genre in genres:
            genre_sources.setdefault(genre, set()).add(source)
            genre_confidences.setdefault(genre, []).append(confidence)
            if genre not in genre_order:
                genre_order.append(genre)
    consensus_genres = [genre for genre in genre_order if len(genre_sources.get(genre, set())) >= 2]
    if not consensus_genres:
        return None
    consensus_confidences = [
        confidence for genre in consensus_genres for confidence in genre_confidences.get(genre, [])
    ]
    confidence = round(
        min(0.95, sum(consensus_confidences) / len(consensus_confidences)),
        3,
    )
    return {
        "genres": consensus_genres,
        "primary_genre": consensus_genres[0],
        "language": None,
        "region": None,
        "confidence": confidence,
        "evidence_url": evidence_url,
        "evidence_summary": (f"External consensus for {artist_name}: " + "; ".join(summaries[:3])),
    }


def _save_genre_source(
    conn: sqlite3.Connection,
    *,
    artist_name: str,
    source: str,
    source_key: str,
    suggestion: dict[str, Any],
    evidence_url: str | None,
    status: str,
) -> int:
    genres = normalize_genres(suggestion["genres"])
    upsert_genre_source(
        conn,
        artist_name=artist_name,
        spotify_artist_id=None,
        source=source,
        source_key=source_key,
        raw_genres=genres,
        normalized_genres=genres,
        primary_genre=suggestion.get("primary_genre") or genres[0],
        language=suggestion.get("language"),
        region=suggestion.get("region"),
        confidence=float(suggestion.get("confidence") or 0),
        evidence_url=evidence_url,
        evidence_summary=str(suggestion.get("evidence_summary") or ""),
        status=status,
    )
    row = conn.execute(
        """SELECT source_id FROM artist_genre_sources
           WHERE artist_name = ? AND source = ? AND source_key = ?""",
        (artist_name, source, source_key),
    ).fetchone()
    return int(row["source_id"])


def _enqueue_review(
    conn: sqlite3.Connection,
    *,
    artist_name: str,
    play_hours: float,
    suggested_source_id: int,
    reason: str,
) -> None:
    conn.execute(
        """INSERT INTO artist_genre_review_queue(
               artist_name, play_hours, reason, suggested_source_id, status, updated_at
           )
           SELECT ?, ?, ?, ?, 'open', datetime('now')
           WHERE NOT EXISTS (
               SELECT 1 FROM artist_genre_review_queue
               WHERE suggested_source_id = ? AND status = 'open'
           )""",
        (
            artist_name,
            float(play_hours),
            reason,
            suggested_source_id,
            suggested_source_id,
        ),
    )


def _llm_user_payload(artist_name: str, evidence: dict[str, Any]) -> str:
    return json.dumps(
        {
            "artist_name": artist_name,
            "evidence": evidence,
            "output_schema": {
                "genres": ["pop", "singer-songwriter"],
                "primary_genre": "pop",
                "language": "english",
                "region": "美国",
                "confidence": 0.82,
                "evidence_summary": "short evidence explanation",
            },
        },
        ensure_ascii=False,
    )


def _evidence_summary(evidence: dict[str, Any]) -> str:
    counts = {
        key: len(value)
        for key, value in evidence.items()
        if key != "wikipedia_summary" and isinstance(value, list)
    }
    return json.dumps(counts, ensure_ascii=False, sort_keys=True)


def _set_stage(
    repo: AiTaskRepository,
    *,
    task_id: str,
    stage: str,
    message: str,
) -> bool:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="running",
        stage=stage,
        progress_pct=BACKFILL_STAGE_PROGRESS.get(stage, 0.5),
        message=message,
    )
    if not updated:
        return False
    repo.add_event(
        task_id=task_id,
        event_type="stage_started",
        stage=stage,
        message=message,
        payload=None,
    )
    return True


def _task_is_active(repo: AiTaskRepository, task_id: str) -> bool:
    task = repo.get_run(task_id)
    return task is not None and task.get("status") not in TERMINAL_STATUSES


def _mark_done(
    repo: AiTaskRepository,
    *,
    task_id: str,
    message: str,
    result: dict[str, Any],
) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="done",
        stage="done",
        progress_pct=1.0,
        message=message,
        result=result,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="result_ready",
        stage="done",
        message=message,
        payload=result,
    )


def _mark_error(repo: AiTaskRepository, *, task_id: str, message: str) -> None:
    updated = repo.update_run_if_not_terminal(
        task_id=task_id,
        status="error",
        stage="error",
        progress_pct=1.0,
        message=f"任务执行失败：{message}",
        result=None,
        error=message,
    )
    if not updated:
        return
    repo.add_event(
        task_id=task_id,
        event_type="stage_failed",
        stage="error",
        message=f"任务执行失败：{message}",
        payload={"error": message},
    )
