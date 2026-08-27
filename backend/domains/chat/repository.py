"""Chat repository — CRUD for chat_sessions and chat_messages tables."""

from __future__ import annotations

import sqlite3


class ChatRepository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        rows = self.conn.execute(
            """SELECT cs.*, (SELECT COUNT(*) FROM chat_messages WHERE session_id = cs.id) AS message_count
               FROM chat_sessions cs
               ORDER BY cs.updated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM chat_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_session_messages(self, session_id: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_session_with_messages(self, session_id: int) -> dict | None:
        session = self.get_session(session_id)
        if session is None:
            return None
        session["messages"] = self.get_session_messages(session_id)
        session["message_count"] = len(session["messages"])
        return session

    def create_session(self, title: str = "新对话") -> int:
        cur = self.conn.execute("INSERT INTO chat_sessions(title) VALUES (?)", (title,))
        self.conn.commit()
        return cur.lastrowid

    def add_message(
        self, session_id: int, role: str, content: str, meta_json: str | None = None
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO chat_messages(session_id, role, content, meta_json)
               VALUES (?, ?, ?, ?)""",
            (session_id, role, content, meta_json),
        )
        self.conn.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_title(self, session_id: int, title: str) -> bool:
        cur = self.conn.execute(
            "UPDATE chat_sessions SET title = ?, updated_at = datetime('now') WHERE id = ?",
            (title, session_id),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def delete_session(self, session_id: int) -> bool:
        # Keep deletion correct even for an injected legacy/test connection
        # where SQLite foreign-key cascades were not enabled.
        self.conn.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
        cur = self.conn.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        self.conn.commit()
        return cur.rowcount > 0
