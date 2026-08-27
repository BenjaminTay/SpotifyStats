from __future__ import annotations

import sqlite3

import pytest

from backend.domains.chat.repository import ChatRepository

pytestmark = pytest.mark.unit


def test_delete_session_removes_messages_when_foreign_keys_are_off() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE chat_sessions(id INTEGER PRIMARY KEY, title TEXT NOT NULL);
        CREATE TABLE chat_messages(
            id INTEGER PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
            content TEXT NOT NULL
        );
        INSERT INTO chat_sessions VALUES (1, 'session');
        INSERT INTO chat_messages VALUES (1, 1, 'message');
        """
    )
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0

    assert ChatRepository(conn).delete_session(1) is True
    assert conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0] == 0
