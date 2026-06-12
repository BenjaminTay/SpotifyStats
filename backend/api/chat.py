"""Chat history API — session & message CRUD."""

# ruff: noqa: UP045

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.core.db import get_db
from backend.dependencies import get_conn
from backend.services import chat_service

router = APIRouter(prefix="/chat", tags=["Chat"])


class CreateSessionRequest(BaseModel):
    title: str = "新对话"


class AddMessageRequest(BaseModel):
    role: Literal["user", "assistant", "error"]
    content: str = Field(..., min_length=1)
    meta_json: str | None = None


class UpdateTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


# ── Response models ──────────────────────────────────────────────────────────


class ChatMessageRecord(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    meta_json: Optional[str] = None
    created_at: str


class ChatSessionData(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int
    last_message: Optional[str] = None


class ChatSessionWithMessages(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    messages: list[ChatMessageRecord] = []


class SessionListResponse(BaseModel):
    success: bool
    data: list[ChatSessionData]
    error: Optional[str] = None


class SessionDetailResponse(BaseModel):
    success: bool
    data: Optional[ChatSessionWithMessages] = None
    error: Optional[str] = None


class SessionCreateResponse(BaseModel):
    success: bool
    data: Optional[ChatSessionWithMessages] = None
    error: Optional[str] = None


class MessageAddResponse(BaseModel):
    success: bool
    data: None = None
    error: Optional[str] = None


class SessionDeleteResponse(BaseModel):
    success: bool
    data: None = None
    error: Optional[str] = None


class SessionUpdateResponse(BaseModel):
    success: bool
    data: None = None
    error: Optional[str] = None


@router.get("/sessions", response_model=SessionListResponse)
def list_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    conn=Depends(get_conn),
):
    return chat_service.list_chat_sessions(conn, limit, offset)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_session(session_id: int, conn=Depends(get_conn)):
    return chat_service.get_chat_session(conn, session_id)


@router.post("/sessions", response_model=SessionCreateResponse)
def create_session(body: CreateSessionRequest = CreateSessionRequest()):
    conn = get_db(readonly=False)
    try:
        return chat_service.create_chat_session(conn, body.title)
    finally:
        conn.close()


@router.post("/sessions/{session_id}/messages", response_model=MessageAddResponse)
def add_message(session_id: int, body: AddMessageRequest):
    conn = get_db(readonly=False)
    try:
        return chat_service.add_message_to_session(
            conn, session_id, body.role, body.content, body.meta_json
        )
    finally:
        conn.close()


@router.patch("/sessions/{session_id}", response_model=SessionUpdateResponse)
def update_title(session_id: int, body: UpdateTitleRequest):
    conn = get_db(readonly=False)
    try:
        return chat_service.update_session_title(conn, session_id, body.title)
    finally:
        conn.close()


@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
def delete_session(session_id: int):
    conn = get_db(readonly=False)
    try:
        return chat_service.delete_chat_session(conn, session_id)
    finally:
        conn.close()
