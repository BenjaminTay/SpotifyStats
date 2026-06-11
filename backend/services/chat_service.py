"""Chat service — thin orchestration layer over ChatRepository."""

from __future__ import annotations

import sqlite3

from backend.domains.chat.repository import ChatRepository


def list_chat_sessions(conn: sqlite3.Connection, limit: int = 50, offset: int = 0) -> dict:
    repo = ChatRepository(conn)
    sessions = repo.list_sessions(limit, offset)
    return {"success": True, "data": sessions, "error": None}


def get_chat_session(conn: sqlite3.Connection, session_id: int) -> dict:
    repo = ChatRepository(conn)
    session = repo.get_session_with_messages(session_id)
    if session is None:
        return {"success": False, "data": None, "error": "会话不存在"}
    return {"success": True, "data": session, "error": None}


def create_chat_session(conn: sqlite3.Connection, title: str = "新对话") -> dict:
    repo = ChatRepository(conn)
    sid = repo.create_session(title)
    session = repo.get_session_with_messages(sid)
    return {"success": True, "data": session, "error": None}


def add_message_to_session(
    conn: sqlite3.Connection,
    session_id: int,
    role: str,
    content: str,
    meta_json: str | None = None,
) -> dict:
    repo = ChatRepository(conn)
    session = repo.get_session(session_id)
    if session is None:
        return {"success": False, "data": None, "error": "会话不存在"}
    repo.add_message(session_id, role, content, meta_json)
    if role == "user" and session["title"] == "新对话":
        new_title = content[:30].replace("\n", " ").strip()
        if new_title:
            repo.update_title(session_id, new_title)
    return {"success": True, "data": None, "error": None}


def delete_chat_session(conn: sqlite3.Connection, session_id: int) -> dict:
    repo = ChatRepository(conn)
    deleted = repo.delete_session(session_id)
    if not deleted:
        return {"success": False, "data": None, "error": "会话不存在"}
    return {"success": True, "data": None, "error": None}


def update_session_title(conn: sqlite3.Connection, session_id: int, title: str) -> dict:
    repo = ChatRepository(conn)
    updated = repo.update_title(session_id, title)
    if not updated:
        return {"success": False, "data": None, "error": "会话不存在"}
    return {"success": True, "data": None, "error": None}
