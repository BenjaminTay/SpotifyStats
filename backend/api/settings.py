"""Settings API endpoints."""

from __future__ import annotations

from sqlite3 import Connection

from fastapi import APIRouter, Depends, HTTPException

from backend.core.auth import require_auth
from backend.core.spotify_utils import get_user_profile, is_user_connected
from backend.dependencies import get_conn
from backend.domains.settings.repository import SettingsRepository
from backend.models.common import (
    LLMProfileCreateRequest,
    LLMProfileDetailResponse,
    LLMProfileResponse,
    LLMProfileUpdateRequest,
    SettingsResponse,
    SettingsUpdateRequest,
)

router = APIRouter(prefix="/settings", tags=["Settings"])

_current: dict | None = None


def _load_settings_from_db() -> dict:
    """Load settings from DB. Falls back to defaults if DB is empty or missing."""
    from backend.core.db import get_db

    conn = get_db()
    try:
        repo = SettingsRepository(conn)
        return repo.load_all()
    finally:
        conn.close()


def _save_setting_to_db(key: str, value) -> None:
    """Persist a single setting to the DB."""
    from backend.core.db import get_db

    conn = get_db(readonly=False)
    try:
        repo = SettingsRepository(conn)
        repo.update(key, value)
    finally:
        conn.close()


def _ensure_current():
    """Lazy-load settings from DB on first access."""
    global _current
    if _current is None:
        _current = _load_settings_from_db()


@router.get("", response_model=SettingsResponse)
def get_settings(conn: Connection = Depends(get_conn)):
    """Get current settings and database status. API key is never returned."""
    _ensure_current()
    db_record_count = 0
    account_data_imported = False
    try:
        db_record_count = conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0]
        sc = conn.execute("SELECT COUNT(*) FROM search_queries").fetchone()[0]
        account_data_imported = sc > 0
    except Exception:
        pass
    resp = {
        **_current,
        "db_record_count": db_record_count,
        "account_data_imported": account_data_imported,
    }
    resp["spotify_connected"] = is_user_connected(conn)
    resp["spotify_profile"] = get_user_profile(conn) if resp["spotify_connected"] else None
    resp["has_llm_key"] = bool(_current.get("llm_api_key", "").strip())
    resp.pop("llm_api_key", None)
    resp.pop("llm_base_url", None)
    return resp


@router.put("")
def update_settings(body: SettingsUpdateRequest, auth: None = Depends(require_auth)):
    """Update settings. Returns updated settings (API key and base_url excluded)."""
    _ensure_current()
    updates = body.dict(exclude_none=True)
    for key in [
        "min_ms",
        "music_only",
        "merge_enabled",
        "bb_top_n",
        "bb_album_top_n",
        "bb_artist_top_n",
        "bb_week_start_dow",
        "bb_week_start_hour",
        "llm_enabled",
        "llm_provider",
        "llm_model",
        "llm_api_key",
        "llm_base_url",
    ]:
        if key in updates:
            _current[key] = updates[key]
            _save_setting_to_db(key, updates[key])
    resp = dict(_current)
    resp["has_llm_key"] = bool(_current.get("llm_api_key", "").strip())
    resp.pop("llm_api_key", None)
    resp.pop("llm_base_url", None)
    return resp


@router.post("/rebuild-agg")
def rebuild_aggregations(conn: Connection = Depends(get_conn), auth: None = Depends(require_auth)):
    """Rebuild pre-aggregated weekly Billboard tables."""
    _ensure_current()
    from backend.core.db import build_aggregations, get_db

    write_conn = get_db(readonly=False)
    try:
        result = build_aggregations(
            min_ms=_current["min_ms"],
            music_only=_current["music_only"],
            week_start_dow=_current["bb_week_start_dow"],
            week_start_hour=_current["bb_week_start_hour"],
        )
        return {"status": "done", **result}
    finally:
        write_conn.close()


@router.post("/clear-translation-cache")
def clear_translation_cache(auth: None = Depends(require_auth)):
    """Clear all cached Wikipedia translations so they are re-translated on next visit."""
    from backend.core.db import get_db

    write_conn = get_db(readonly=False)
    try:
        count = write_conn.execute("SELECT COUNT(*) FROM wikipedia_cache").fetchone()[0]
        write_conn.execute("DELETE FROM wikipedia_cache")
        write_conn.commit()
        return {"status": "done", "deleted_count": count}
    finally:
        write_conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# LLM Profile endpoints
# ═══════════════════════════════════════════════════════════════════════════


@router.get("/llm-profiles", response_model=list[LLMProfileResponse])
def list_llm_profiles(conn: Connection = Depends(get_conn)):
    """List all saved LLM profiles (API keys excluded)."""
    rows = conn.execute(
        "SELECT id, profile_name, llm_provider, llm_model, created_at, updated_at "
        "FROM llm_profiles ORDER BY updated_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


@router.get("/llm-profiles/{profile_id}", response_model=LLMProfileDetailResponse)
def get_llm_profile(profile_id: int, conn: Connection = Depends(get_conn)):
    """Get a single LLM profile. API key is never returned."""
    row = conn.execute(
        "SELECT id, profile_name, llm_provider, llm_model, llm_base_url, "
        "llm_api_key, created_at, updated_at FROM llm_profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    result = dict(row)
    result["has_llm_key"] = bool(result.pop("llm_api_key", "").strip())
    return result


@router.post("/llm-profiles")
def create_llm_profile(body: LLMProfileCreateRequest, auth: None = Depends(require_auth)):
    """Create a new LLM profile."""
    from backend.core.db import get_db

    conn = get_db(readonly=False)
    try:
        cur = conn.execute(
            """INSERT INTO llm_profiles (profile_name, llm_provider, llm_model,
               llm_api_key, llm_base_url) VALUES (?, ?, ?, ?, ?)""",
            (
                body.profile_name,
                body.llm_provider,
                body.llm_model,
                body.llm_api_key,
                body.llm_base_url,
            ),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": "created"}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="Profile name already exists")
        raise
    finally:
        conn.close()


@router.put("/llm-profiles/{profile_id}", response_model=LLMProfileDetailResponse)
def update_llm_profile(
    profile_id: int, body: LLMProfileUpdateRequest, auth: None = Depends(require_auth)
):
    """Update an existing LLM profile."""
    from backend.core.db import get_db

    updates = body.dict(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    set_parts = [f"{k} = ?" for k in updates]
    set_parts.append("updated_at = datetime('now')")
    params = list(updates.values()) + [profile_id]
    conn = get_db(readonly=False)
    try:
        conn.execute(f"UPDATE llm_profiles SET {', '.join(set_parts)} WHERE id = ?", params)
        conn.commit()
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail="Profile name already exists")
        raise
    finally:
        conn.close()
    # Fetch and return updated profile
    read_conn = get_db()
    try:
        row = read_conn.execute(
            "SELECT id, profile_name, llm_provider, llm_model, llm_base_url, "
            "llm_api_key, created_at, updated_at FROM llm_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Profile not found")
        result = dict(row)
        result["has_llm_key"] = bool(result.pop("llm_api_key", "").strip())
        return result
    finally:
        read_conn.close()


@router.post("/llm-profiles/{profile_id}/apply")
def apply_llm_profile(profile_id: int, auth: None = Depends(require_auth)):
    """Apply a saved profile's configuration to current settings.

    Reads provider, model, api_key, and base_url from the profile row
    and writes them into the active settings — all server-side so the
    API key never transits through the frontend.
    """
    _ensure_current()
    from backend.core.db import get_db

    conn = get_db()
    try:
        row = conn.execute(
            "SELECT llm_provider, llm_model, llm_api_key, llm_base_url "
            "FROM llm_profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    updates = {
        "llm_provider": row["llm_provider"],
        "llm_model": row["llm_model"],
        "llm_api_key": row["llm_api_key"],
        "llm_base_url": row["llm_base_url"],
    }
    for key, value in updates.items():
        _current[key] = value
        _save_setting_to_db(key, value)
    return {"status": "applied", "profile_id": profile_id}


@router.delete("/llm-profiles/{profile_id}")
def delete_llm_profile(profile_id: int, auth: None = Depends(require_auth)):
    """Delete an LLM profile."""
    from backend.core.db import get_db

    conn = get_db(readonly=False)
    try:
        conn.execute("DELETE FROM llm_profiles WHERE id = ?", (profile_id,))
        conn.commit()
        if conn.total_changes == 0:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"status": "deleted"}
    finally:
        conn.close()
